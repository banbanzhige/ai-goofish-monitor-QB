import asyncio
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

import aiofiles
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from src.logging_config import get_logger
from src.notifier import notifier
from src.prompt_utils import CriteriaGenerationTimeoutError, generate_criteria
from src.scraper import delete_task_stats_file, get_task_stats
from src.storage import get_storage
from src.task import add_task, get_task, update_task
from src.user_file_store import build_virtual_prompt_path, resolve_virtual_task_file
from src.web.auth import get_current_user, is_multi_user_mode
from src.web.models import Task, TaskGenerateRequestWithReference, TaskOrderUpdate, TaskUpdate
from src.web.scheduler import reload_scheduler_jobs

router = APIRouter()
logger = get_logger(__name__, service="web")

CONFIG_FILE = "config.json"
RUNTIME_TASK_CONFIG_DIR = os.path.join("state", "runtime_task_configs")

BOOL_FIELDS = [
    "free_shipping",
    "inspection_service",
    "account_assurance",
    "super_shop",
    "brand_new",
    "strict_selected",
    "resale",
    "auto_switch_on_risk",
]

ACTIVE_AI_GENERATIONS: set[str] = set()


def _get_owner_id(request: Optional[Request] = None) -> Optional[str]:
    """多用户模式下获取当前用户ID。"""
    if not is_multi_user_mode() or request is None:
        return None
    user = get_current_user(request)
    if not user:
        return None
    user_id = user.get("user_id") or user.get("id")
    return str(user_id) if user_id else None


def _normalize_task_dict(task: Dict[str, Any], index: int) -> Dict[str, Any]:
    """补齐任务默认字段，保证前端渲染稳定。"""
    normalized = dict(task or {})
    normalized["id"] = index
    normalized.setdefault("order", index)
    normalized.setdefault("enabled", True)
    normalized.setdefault("is_running", False)
    normalized.setdefault("generating_ai_criteria", False)
    normalized.setdefault("free_shipping", False)
    normalized.setdefault("new_publish_option", None)
    normalized.setdefault("region", None)
    normalized.setdefault("inspection_service", False)
    normalized.setdefault("account_assurance", False)
    normalized.setdefault("super_shop", False)
    normalized.setdefault("brand_new", False)
    normalized.setdefault("strict_selected", False)
    normalized.setdefault("resale", False)
    normalized.setdefault("bound_account", None)
    normalized.setdefault("auto_switch_on_risk", False)
    normalized["bayes_profile"] = _normalize_bayes_profile_value(normalized.get("bayes_profile"))
    return normalized


def _make_process_key(task_id: int, task_name: str, owner_id: Optional[str]) -> Union[int, str]:
    if owner_id:
        return f"{owner_id}:{task_name}"
    return int(task_id)


def _make_generation_key(task_id: int, owner_id: Optional[str]) -> str:
    owner_part = owner_id or "__local__"
    return f"{owner_part}:{int(task_id)}"


def _is_task_generation_active(task_id: int, owner_id: Optional[str]) -> bool:
    return _make_generation_key(task_id, owner_id) in ACTIVE_AI_GENERATIONS


def _parse_process_key(task_id: Union[int, str]) -> tuple[Optional[str], Optional[str]]:
    if not isinstance(task_id, str):
        return None, None
    if ":" not in task_id:
        return None, None
    owner_id, task_name = task_id.split(":", 1)
    if not owner_id or not task_name:
        return None, None
    return owner_id, task_name


def _sanitize_task_name(task_name: str) -> str:
    safe_task_name = "".join(c for c in str(task_name or "").replace(" ", "_") if c.isalnum() or c in "_-")
    return safe_task_name or "task"


def _normalize_bayes_profile_value(value: Any) -> str:
    """统一 Bayes 版本格式，内部仅保存不带 .json 的版本号。"""
    text = str(value or "").strip()
    if text.endswith(".json"):
        text = text[:-5]
    return text or "bayes_v1"


def _parse_bool_for_env(value, default: bool = False) -> bool:
    """解析布尔值并统一用于环境变量写入。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _apply_owner_ai_env_overrides(child_env: Dict[str, str], owner_id: Optional[str]) -> None:
    """为采集子进程注入当前用户私有 AI 配置，避免回退到全局 .env。"""
    if not owner_id or not is_multi_user_mode():
        return

    try:
        storage = get_storage()
        user_api_config = storage.get_default_api_config(owner_id) or {}
        extra_config = user_api_config.get("extra_config") if isinstance(user_api_config.get("extra_config"), dict) else {}

        api_key = str(user_api_config.get("api_key") or "").strip()
        base_url = str(user_api_config.get("api_base_url") or "").strip()
        model_name = str(user_api_config.get("model") or "").strip()

        if not api_key or not base_url or not model_name:
            raise RuntimeError("当前用户AI配置不完整，无法启动任务。请先配置 API Key、Base URL 和模型名称。")

        # 清理同名全局变量，避免子进程误用 .env 值。
        for key in [
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL_NAME",
            "PROXY_URL",
            "PROXY_AI_ENABLED",
            "AI_MAX_TOKENS_PARAM_NAME",
            "AI_MAX_TOKENS_LIMIT",
        ]:
            child_env.pop(key, None)

        child_env["GOOFISH_OPENAI_API_KEY"] = api_key
        child_env["GOOFISH_OPENAI_BASE_URL"] = base_url
        child_env["GOOFISH_OPENAI_MODEL_NAME"] = model_name
        child_env["GOOFISH_PROXY_URL"] = str(extra_config.get("PROXY_URL") or "").strip()
        child_env["GOOFISH_AI_MAX_TOKENS_PARAM_NAME"] = str(extra_config.get("AI_MAX_TOKENS_PARAM_NAME") or "").strip()
        child_env["GOOFISH_AI_MAX_TOKENS_LIMIT"] = str(extra_config.get("AI_MAX_TOKENS_LIMIT") or "").strip()
        child_env["GOOFISH_PROXY_AI_ENABLED"] = str(
            _parse_bool_for_env(extra_config.get("PROXY_AI_ENABLED"), default=False)
        ).lower()

        logger.info(
            "已为任务子进程注入用户私有AI配置",
            extra={"event": "task_owner_ai_env_applied", "owner_id": owner_id},
        )
    except Exception as exc:
        logger.error(
            f"注入用户私有AI配置失败: {exc}",
            extra={"event": "task_owner_ai_env_apply_failed", "owner_id": owner_id},
        )
        raise


def _make_unique_task_name(existing_names: List[str], desired_name: str) -> str:
    existing = {str(name) for name in existing_names}
    if desired_name not in existing:
        return desired_name
    index = 1
    while True:
        candidate = f"{desired_name} (副本{index})"
        if candidate not in existing:
            return candidate
        index += 1


async def _load_local_tasks() -> List[Dict[str, Any]]:
    try:
        async with aiofiles.open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = await f.read()
            if not content.strip():
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"配置文件格式错误: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {exc}") from exc


async def _save_local_tasks(tasks: List[Dict[str, Any]]) -> None:
    async with aiofiles.open(CONFIG_FILE, "w", encoding="utf-8") as f:
        await f.write(json.dumps(tasks, ensure_ascii=False, indent=2))


async def _build_runtime_task_config(owner_id: str, task_name: str) -> str:
    """按用户生成运行时任务配置，供 collector 子进程加载。"""
    storage = get_storage()
    task = storage.get_task_by_name(task_name, owner_id=owner_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在，无法启动")
    os.makedirs(RUNTIME_TASK_CONFIG_DIR, exist_ok=True)
    safe_owner = re.sub(r"[^0-9a-zA-Z_-]", "_", owner_id)
    safe_task_name = re.sub(r"[^0-9a-zA-Z_-]", "_", str(task_name or "task"))
    timestamp_ms = int(datetime.now().timestamp() * 1000)
    config_path = os.path.join(
        RUNTIME_TASK_CONFIG_DIR,
        f"{safe_owner}_{safe_task_name}_{timestamp_ms}.json",
    )
    async with aiofiles.open(config_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps([task], ensure_ascii=False, indent=2))
    return config_path


async def _update_storage_task_running_status(
    owner_id: str,
    task_name: str,
    is_running: bool,
    process_pid: Optional[int] = None,
) -> None:
    storage = get_storage()
    task = storage.get_task_by_name(task_name, owner_id=owner_id)
    if not task:
        return
    task["is_running"] = bool(is_running)
    if process_pid is not None:
        task["process_pid"] = int(process_pid)
    elif not is_running:
        task["process_pid"] = None
    storage.save_task(task, owner_id=owner_id)


async def update_task_running_status(
    task_id: Union[int, str],
    is_running: bool,
    process_pid: Optional[int] = None,
    owner_id: Optional[str] = None,
    task_name: Optional[str] = None,
):
    """更新任务运行状态，兼容本地模式和多用户模式。"""
    try:
        resolved_owner = owner_id
        resolved_task_name = task_name
        if is_multi_user_mode() and (not resolved_owner or not resolved_task_name):
            key_owner, key_task_name = _parse_process_key(task_id)
            resolved_owner = resolved_owner or key_owner
            resolved_task_name = resolved_task_name or key_task_name

        if is_multi_user_mode() and resolved_owner and resolved_task_name:
            await _update_storage_task_running_status(
                owner_id=resolved_owner,
                task_name=resolved_task_name,
                is_running=is_running,
                process_pid=process_pid,
            )
            return

        if not isinstance(task_id, int):
            return
        tasks = await _load_local_tasks()
        if 0 <= task_id < len(tasks):
            tasks[task_id]["is_running"] = bool(is_running)
            if process_pid is not None:
                tasks[task_id]["process_pid"] = int(process_pid)
            elif not is_running:
                tasks[task_id]["process_pid"] = None
            await _save_local_tasks(tasks)
    except Exception as exc:
        logger.error(
            f"更新任务运行状态失败: {exc}",
            extra={"event": "task_status_update_failed", "task_id": str(task_id)},
        )


def _terminate_pid(pid: int) -> None:
    if not pid:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            return
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        return

async def start_task_process(
    task_id: int,
    task_name: str,
    fetcher_processes: Dict[Union[int, str], asyncio.subprocess.Process],
    owner_id: Optional[str] = None,
):
    """启动任务子进程。"""
    process_key = _make_process_key(task_id, task_name, owner_id)
    existing_process = fetcher_processes.get(process_key)
    if existing_process and existing_process.returncode is None:
        logger.info(
            f"任务已在运行: {task_name}",
            extra={"event": "task_already_running", "task_name": task_name, "owner_id": owner_id},
        )
        return

    runtime_config_path = None
    log_file_handle = None
    try:
        os.makedirs("logs", exist_ok=True)
        log_file_handle = open(os.path.join("logs", "fetcher.log"), "a", encoding="utf-8")

        cmd = [sys.executable, "-u", "collector.py", "--task-name", task_name, "--start-reason", "manual"]
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        if owner_id:
            runtime_config_path = await _build_runtime_task_config(owner_id, task_name)
            cmd.extend(["--config", runtime_config_path])
            child_env["GOOFISH_OWNER_ID"] = owner_id
            child_env["GOOFISH_TASK_NAME"] = task_name
            _apply_owner_ai_env_overrides(child_env, owner_id)
            try:
                storage = get_storage()
                task_data = storage.get_task_by_name(task_name, owner_id=owner_id) or {}
                bound_account = str(task_data.get("bound_account") or "").strip()
                if bound_account:
                    child_env["GOOFISH_BOUND_ACCOUNT"] = bound_account
            except Exception:
                pass

        preexec_fn = os.setsid if sys.platform != "win32" else None
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=log_file_handle,
            stderr=log_file_handle,
            preexec_fn=preexec_fn,
            env=child_env,
        )

        fetcher_processes[process_key] = process
        await update_task_running_status(task_id, True, process.pid, owner_id=owner_id, task_name=task_name)

        logger.info(
            f"任务已启动: {task_name}, PID={process.pid}",
            extra={"event": "task_started", "task_name": task_name, "pid": process.pid, "owner_id": owner_id},
        )

        async def _monitor_process():
            try:
                await process.wait()
                logger.info(
                    f"任务进程结束: {task_name}, returncode={process.returncode}",
                    extra={"event": "task_ended", "task_name": task_name, "owner_id": owner_id},
                )
            finally:
                await update_task_running_status(
                    process_key if owner_id else task_id,
                    False,
                    owner_id=owner_id,
                    task_name=task_name,
                )
                fetcher_processes.pop(process_key, None)
                if runtime_config_path and os.path.exists(runtime_config_path):
                    try:
                        os.remove(runtime_config_path)
                    except Exception:
                        pass

        asyncio.create_task(_monitor_process())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启动任务失败: {exc}") from exc
    finally:
        if log_file_handle:
            try:
                log_file_handle.close()
            except Exception:
                pass


async def stop_task_process(
    task_id: int,
    fetcher_processes: Dict[Union[int, str], asyncio.subprocess.Process],
    owner_id: Optional[str] = None,
    task_name: Optional[str] = None,
):
    """停止任务子进程。"""
    resolved_task_name = task_name
    process_pid = None

    if is_multi_user_mode() and owner_id:
        storage = get_storage()
        if not resolved_task_name:
            tasks = storage.get_tasks(owner_id=owner_id)
            if 0 <= task_id < len(tasks):
                resolved_task_name = tasks[task_id].get("task_name")
        if resolved_task_name:
            task_data = storage.get_task_by_name(resolved_task_name, owner_id=owner_id)
            if task_data:
                process_pid = task_data.get("process_pid")
    else:
        tasks = await _load_local_tasks()
        if 0 <= task_id < len(tasks):
            resolved_task_name = resolved_task_name or tasks[task_id].get("task_name")
            process_pid = tasks[task_id].get("process_pid")

    if not resolved_task_name:
        resolved_task_name = f"任务{task_id}"
    process_key = _make_process_key(task_id, resolved_task_name, owner_id)
    process = fetcher_processes.get(process_key)

    if not process or process.returncode is not None:
        if process_pid:
            _terminate_pid(int(process_pid))
        await update_task_running_status(
            process_key if owner_id else task_id,
            False,
            owner_id=owner_id,
            task_name=resolved_task_name,
        )
        fetcher_processes.pop(process_key, None)
        return

    try:
        if sys.platform == "win32":
            _terminate_pid(process.pid)
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        else:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except Exception:
                process.terminate()

        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning(
                f"停止任务等待超时，已强制终止: {resolved_task_name}",
                extra={"event": "task_stop_timeout", "task_name": resolved_task_name, "owner_id": owner_id},
            )
    except ProcessLookupError:
        pass
    except Exception as exc:
        logger.error(
            f"停止任务失败: {exc}",
            extra={"event": "task_stop_failed", "task_name": resolved_task_name, "owner_id": owner_id},
        )
    finally:
        await update_task_running_status(
            process_key if owner_id else task_id,
            False,
            owner_id=owner_id,
            task_name=resolved_task_name,
        )
        fetcher_processes.pop(process_key, None)

        try:
            processed_count, recommended_count = get_task_stats(resolved_task_name)
            await notifier.send_task_completion_notification(
                resolved_task_name,
                "手动停止-结束原因：用户手动停止任务",
                processed_count,
                recommended_count,
                owner_id=owner_id,
                bound_task=resolved_task_name,
            )
            delete_task_stats_file(resolved_task_name)
        except Exception as exc:
            logger.warning(
                f"任务停止通知发送失败: {exc}",
                extra={"event": "task_stop_notification_failed", "task_name": resolved_task_name},
            )


async def _maybe_copy_criteria_file(
    task_name: str,
    source_file: Optional[str],
    owner_id: Optional[str] = None,
) -> Optional[str]:
    if not source_file:
        return source_file

    source_path = resolve_virtual_task_file(source_file, owner_id=owner_id, for_write=False)
    if not source_path.exists():
        return source_file

    safe_task_name = _sanitize_task_name(task_name.lower())
    source_virtual = str(source_file).replace("\\", "/")
    try:
        if source_virtual.startswith("requirement/"):
            new_file = f"requirement/{safe_task_name}_requirement.txt"
        else:
            new_file = f"criteria/{safe_task_name}_criteria.txt"
        target_path = resolve_virtual_task_file(new_file, owner_id=owner_id, for_write=True)
        async with aiofiles.open(str(source_path), "r", encoding="utf-8") as src:
            content = await src.read()
        async with aiofiles.open(str(target_path), "w", encoding="utf-8") as dst:
            await dst.write(content)
        return new_file
    except Exception as exc:
        logger.warning(
            f"复制任务标准文件失败: {exc}",
            extra={"event": "task_criteria_copy_failed", "task_name": task_name},
        )
        return source_file


def _normalize_update_data(update_data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(update_data)
    # 该字段由后端生成流程维护，前端不应直接写入
    normalized.pop("generating_ai_criteria", None)
    for field in BOOL_FIELDS:
        if field in normalized:
            normalized[field] = bool(normalized[field])
    if "new_publish_option" in normalized:
        normalized["new_publish_option"] = normalized["new_publish_option"] or None
    if "region" in normalized:
        normalized["region"] = normalized["region"] or None
    if "bayes_profile" in normalized:
        normalized["bayes_profile"] = _normalize_bayes_profile_value(normalized.get("bayes_profile"))
    return normalized


async def _set_task_generating_status(task_id: int, is_generating: bool, owner_id: Optional[str]) -> None:
    """设置任务 AI 标准生成中的锁状态。"""
    generation_key = _make_generation_key(task_id, owner_id)
    updated = False
    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if 0 <= task_id < len(tasks):
            task_data = dict(tasks[task_id] or {})
            task_data["generating_ai_criteria"] = bool(is_generating)
            storage.save_task(task_data, owner_id=owner_id)
            updated = True
    else:
        tasks = await _load_local_tasks()
        if 0 <= task_id < len(tasks):
            tasks[task_id]["generating_ai_criteria"] = bool(is_generating)
            await _save_local_tasks(tasks)
            updated = True

    if not updated:
        ACTIVE_AI_GENERATIONS.discard(generation_key)
        return
    if is_generating:
        ACTIVE_AI_GENERATIONS.add(generation_key)
    else:
        ACTIVE_AI_GENERATIONS.discard(generation_key)


async def _clear_stale_generating_flags(tasks: List[Dict[str, Any]], owner_id: Optional[str]) -> List[Dict[str, Any]]:
    """清理历史遗留的生成锁定状态，避免刷新后仍永久锁死。"""
    stale_indices = [
        idx for idx, task in enumerate(tasks)
        if bool((task or {}).get("generating_ai_criteria")) and not _is_task_generation_active(idx, owner_id)
    ]
    if not stale_indices:
        return tasks

    if owner_id:
        storage = get_storage()
        for idx in stale_indices:
            task_data = dict(tasks[idx] or {})
            task_data["generating_ai_criteria"] = False
            storage.save_task(task_data, owner_id=owner_id)
            tasks[idx] = task_data
        return tasks

    for idx in stale_indices:
        tasks[idx]["generating_ai_criteria"] = False
    await _save_local_tasks(tasks)
    return tasks


async def _refresh_local_scheduler() -> None:
    from src.web.main import fetcher_processes, scheduler
    await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)

@router.get("/api/tasks")
async def get_tasks(request: Request):
    owner_id = _get_owner_id(request)
    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        tasks = await _clear_stale_generating_flags(tasks, owner_id=owner_id)
        return [_normalize_task_dict(task, idx) for idx, task in enumerate(tasks)]
    tasks = await _load_local_tasks()
    tasks = await _clear_stale_generating_flags(tasks, owner_id=None)
    return [_normalize_task_dict(task, idx) for idx, task in enumerate(tasks)]


@router.post("/api/tasks/reorder")
async def reorder_tasks(payload: TaskOrderUpdate, request: Request):
    ordered_ids = payload.ordered_ids
    owner_id = _get_owner_id(request)

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if len(ordered_ids) != len(tasks) or len(set(ordered_ids)) != len(ordered_ids):
            raise HTTPException(status_code=400, detail="排序数据不合法")
        if any(not isinstance(task_id, int) or task_id < 0 or task_id >= len(tasks) for task_id in ordered_ids):
            raise HTTPException(status_code=400, detail="排序数据不合法")
        ordered_names = [tasks[task_id].get("task_name") for task_id in ordered_ids]
        storage.update_task_order(ordered_names, owner_id=owner_id)
        await _refresh_local_scheduler()
        return {"message": "任务顺序已更新"}

    tasks = await _load_local_tasks()
    if len(ordered_ids) != len(tasks) or len(set(ordered_ids)) != len(ordered_ids):
        raise HTTPException(status_code=400, detail="排序数据不合法")
    if any(not isinstance(task_id, int) or task_id < 0 or task_id >= len(tasks) for task_id in ordered_ids):
        raise HTTPException(status_code=400, detail="排序数据不合法")

    reordered = [tasks[task_id] for task_id in ordered_ids]
    for idx, task in enumerate(reordered):
        task["order"] = idx
    await _save_local_tasks(reordered)
    await _refresh_local_scheduler()
    return {"message": "任务顺序已更新"}


@router.post("/api/tasks/generate")
async def generate_task(req: TaskGenerateRequestWithReference, request: Request):
    owner_id = _get_owner_id(request)

    if owner_id:
        storage = get_storage()
        existing_tasks = storage.get_tasks(owner_id=owner_id)
    else:
        existing_tasks = await _load_local_tasks()

    task_name = _make_unique_task_name([task.get("task_name") for task in existing_tasks], req.task_name)
    safe_task_name = _sanitize_task_name(task_name)
    requirement_filename = f"requirement/{safe_task_name}_requirement.txt"
    requirement_path = resolve_virtual_task_file(requirement_filename, owner_id=owner_id, for_write=True)
    reference_file = build_virtual_prompt_path(req.reference_file)

    try:
        async with aiofiles.open(str(requirement_path), "w", encoding="utf-8") as f:
            await f.write(req.description or "")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存需求文件失败: {exc}") from exc

    task_data = {
        "task_name": task_name,
        "order": len(existing_tasks),
        "enabled": True,
        "keyword": req.keyword,
        "description": req.description,
        "max_pages": req.max_pages,
        "personal_only": req.personal_only,
        "min_price": req.min_price,
        "max_price": req.max_price,
        "cron": req.cron,
        "ai_prompt_base_file": reference_file,
        "ai_prompt_criteria_file": requirement_filename,
        "bayes_profile": _normalize_bayes_profile_value(req.bayes_profile),
        "is_running": False,
        "generating_ai_criteria": False,
        "bound_account": None,
        "auto_switch_on_risk": False,
        "free_shipping": bool(req.free_shipping),
        "new_publish_option": req.new_publish_option or None,
        "region": req.region or None,
        "inspection_service": bool(req.inspection_service),
        "account_assurance": bool(req.account_assurance),
        "super_shop": bool(req.super_shop),
        "brand_new": bool(req.brand_new),
        "strict_selected": bool(req.strict_selected),
        "resale": bool(req.resale),
    }

    task_model = Task(**task_data)
    if owner_id:
        storage = get_storage()
        created = storage.save_task(task_model.model_dump(), owner_id=owner_id)
        tasks = storage.get_tasks(owner_id=owner_id)
        index = next((idx for idx, t in enumerate(tasks) if t.get("task_name") == created.get("task_name")), 0)
        await _refresh_local_scheduler()
        return {"message": "AI任务创建成功。", "task": _normalize_task_dict(created, index)}

    created_ok = await add_task(task_model)
    if not created_ok:
        raise HTTPException(status_code=500, detail="写入配置文件失败")
    await _refresh_local_scheduler()
    tasks = await _load_local_tasks()
    index = next((idx for idx, t in enumerate(tasks) if t.get("task_name") == task_model.task_name), len(tasks) - 1)
    return {"message": "AI任务创建成功。", "task": _normalize_task_dict(tasks[index], index)}


@router.post("/api/tasks")
async def create_task(task: Task, request: Request):
    owner_id = _get_owner_id(request)
    storage = get_storage() if owner_id else None

    existing_tasks = storage.get_tasks(owner_id=owner_id) if owner_id else await _load_local_tasks()
    task.task_name = _make_unique_task_name([t.get("task_name") for t in existing_tasks], task.task_name)
    if task.order is None:
        task.order = len(existing_tasks)
    task.ai_prompt_base_file = build_virtual_prompt_path(task.ai_prompt_base_file)

    copied_file = await _maybe_copy_criteria_file(task.task_name, task.ai_prompt_criteria_file, owner_id=owner_id)
    task.ai_prompt_criteria_file = copied_file
    normalized_payload = _normalize_update_data(task.model_dump())
    task_model = Task(**normalized_payload)

    if owner_id:
        created = storage.save_task(task_model.model_dump(), owner_id=owner_id)
        tasks = storage.get_tasks(owner_id=owner_id)
        index = next((idx for idx, t in enumerate(tasks) if t.get("task_name") == created.get("task_name")), 0)
        await _refresh_local_scheduler()
        return {"message": "任务创建成功。", "task": _normalize_task_dict(created, index)}

    created_ok = await add_task(task_model)
    if not created_ok:
        raise HTTPException(status_code=500, detail="写入配置文件失败")
    await _refresh_local_scheduler()
    tasks = await _load_local_tasks()
    index = next((idx for idx, t in enumerate(tasks) if t.get("task_name") == task_model.task_name), len(tasks) - 1)
    return {"message": "任务创建成功。", "task": _normalize_task_dict(tasks[index], index)}


@router.post("/api/tasks/{task_id}/duplicate")
async def duplicate_task(task_id: int, request: Request):
    """复制任务并复制其 AI 标准文件。"""
    owner_id = _get_owner_id(request)
    storage = get_storage() if owner_id else None

    source_tasks = storage.get_tasks(owner_id=owner_id) if owner_id else await _load_local_tasks()
    if not (0 <= task_id < len(source_tasks)):
        raise HTTPException(status_code=404, detail="任务未找到。")

    source_task = dict(source_tasks[task_id] or {})
    existing_names = [task.get("task_name") for task in source_tasks]
    new_task_name = _make_unique_task_name(existing_names, source_task.get("task_name") or "任务副本")

    payload = dict(source_task)
    payload.pop("id", None)
    payload.pop("process_pid", None)
    payload["task_name"] = new_task_name
    payload["is_running"] = False
    payload["generating_ai_criteria"] = False
    payload["order"] = len(source_tasks)
    payload["ai_prompt_base_file"] = build_virtual_prompt_path(payload.get("ai_prompt_base_file"))
    payload["ai_prompt_criteria_file"] = await _maybe_copy_criteria_file(
        new_task_name,
        payload.get("ai_prompt_criteria_file"),
        owner_id=owner_id,
    )
    normalized_payload = _normalize_update_data(payload)
    task_model = Task(**normalized_payload)

    if owner_id:
        created = storage.save_task(task_model.model_dump(), owner_id=owner_id)
        tasks = storage.get_tasks(owner_id=owner_id)
        index = next((idx for idx, t in enumerate(tasks) if t.get("task_name") == created.get("task_name")), 0)
        await _refresh_local_scheduler()
        return {"message": "任务复制成功。", "task": _normalize_task_dict(created, index)}

    created_ok = await add_task(task_model)
    if not created_ok:
        raise HTTPException(status_code=500, detail="写入配置文件失败")
    await _refresh_local_scheduler()
    tasks = await _load_local_tasks()
    index = next((idx for idx, t in enumerate(tasks) if t.get("task_name") == task_model.task_name), len(tasks) - 1)
    return {"message": "任务复制成功。", "task": _normalize_task_dict(tasks[index], index)}


@router.patch("/api/tasks/{task_id}")
async def update_task_api(task_id: int, task_update: TaskUpdate, background_tasks: BackgroundTasks, request: Request):
    del background_tasks
    owner_id = _get_owner_id(request)
    update_data = _normalize_update_data(task_update.model_dump(exclude_unset=True))
    if not update_data:
        return JSONResponse(content={"message": "数据无变化，未执行更新。"}, status_code=200)

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")
        task_data = dict(tasks[task_id])
        if task_data.get("generating_ai_criteria") and not _is_task_generation_active(task_id, owner_id):
            await _set_task_generating_status(task_id, False, owner_id=owner_id)
            task_data["generating_ai_criteria"] = False
        if task_data.get("is_running") or task_data.get("generating_ai_criteria"):
            raise HTTPException(status_code=400, detail="运行中或生成中的任务禁止编辑")
    else:
        task_model = await get_task(task_id)
        if not task_model:
            raise HTTPException(status_code=404, detail="任务未找到。")
        if task_model.generating_ai_criteria and not _is_task_generation_active(task_id, owner_id=None):
            await _set_task_generating_status(task_id, False, owner_id=None)
            task_model.generating_ai_criteria = False
        if task_model.is_running or task_model.generating_ai_criteria:
            raise HTTPException(status_code=400, detail="运行中或生成中的任务禁止编辑")
        task_data = task_model.model_dump()

    if "description" in update_data:
        reference_file = build_virtual_prompt_path(
            update_data.pop("reference_file", None) or task_data.get("ai_prompt_base_file") or "prompts/base_prompt.txt"
        )
        reference_file_path = resolve_virtual_task_file(reference_file, owner_id=owner_id, for_write=False)
        criteria_filename = f"criteria/{_sanitize_task_name(task_data.get('task_name'))}_criteria.txt"
        criteria_path = resolve_virtual_task_file(criteria_filename, owner_id=owner_id, for_write=True)
        lock_set = False
        try:
            await _set_task_generating_status(task_id, True, owner_id=owner_id)
            lock_set = True
            generated_criteria = await generate_criteria(
                user_description=update_data["description"],
                reference_file_path=str(reference_file_path),
                owner_id=owner_id,
            )
            if generated_criteria:
                async with aiofiles.open(str(criteria_path), "w", encoding="utf-8") as f:
                    await f.write(generated_criteria)
                update_data["ai_prompt_base_file"] = reference_file
                update_data["ai_prompt_criteria_file"] = criteria_filename
        except Exception as exc:
            if isinstance(exc, CriteriaGenerationTimeoutError):
                raise HTTPException(status_code=504, detail=str(exc)) from exc
            logger.error(
                f"生成AI标准失败: {exc}",
                extra={"event": "task_generate_criteria_failed", "task_id": task_id, "owner_id": owner_id},
            )
        finally:
            if lock_set:
                try:
                    await _set_task_generating_status(task_id, False, owner_id=owner_id)
                except Exception as unlock_exc:
                    logger.warning(
                        f"AI标准生成后解锁任务失败: {unlock_exc}",
                        extra={"event": "task_generate_unlock_failed", "task_id": task_id, "owner_id": owner_id},
                    )

    if "enabled" in update_data and not update_data["enabled"]:
        update_data["is_running"] = False
        from src.web.main import fetcher_processes
        await stop_task_process(task_id, fetcher_processes, owner_id=owner_id, task_name=task_data.get("task_name"))

    task_data.update(update_data)
    task_data = _normalize_task_dict(task_data, task_id)
    task_data.pop("id", None)
    task_model = Task(**task_data)

    if owner_id:
        storage = get_storage()
        updated = storage.save_task(task_model.model_dump(), owner_id=owner_id)
        await _refresh_local_scheduler()
        return {"message": "任务更新成功。", "task": _normalize_task_dict(updated, task_id)}

    saved_ok = await update_task(task_id, task_model)
    if not saved_ok:
        raise HTTPException(status_code=500, detail="写入配置文件失败。")
    await _refresh_local_scheduler()
    return {"message": "任务更新成功。", "task": task_model}


@router.post("/api/tasks/start/{task_id}")
async def start_single_task(task_id: int, request: Request):
    owner_id = _get_owner_id(request)
    from src.web.main import fetcher_processes

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")
        task = tasks[task_id]
        if not task.get("enabled", False):
            raise HTTPException(status_code=400, detail="任务已禁用，无法启动。")
        await start_task_process(task_id, task.get("task_name"), fetcher_processes, owner_id=owner_id)
        return {"message": f"任务 '{task.get('task_name')}' 已启动。"}

    tasks = await _load_local_tasks()
    if not (0 <= task_id < len(tasks)):
        raise HTTPException(status_code=404, detail="任务未找到。")
    task = tasks[task_id]
    if not task.get("enabled", False):
        raise HTTPException(status_code=400, detail="任务已禁用，无法启动。")
    await start_task_process(task_id, task.get("task_name"), fetcher_processes)
    return {"message": f"任务 '{task.get('task_name')}' 已启动。"}


@router.post("/api/tasks/stop/{task_id}")
async def stop_single_task(task_id: int, request: Request):
    owner_id = _get_owner_id(request)
    from src.web.main import fetcher_processes

    task_name = None
    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if 0 <= task_id < len(tasks):
            task_name = tasks[task_id].get("task_name")
    await stop_task_process(task_id, fetcher_processes, owner_id=owner_id, task_name=task_name)
    return {"message": f"任务ID {task_id} 已发送停止信号。"}


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, request: Request):
    owner_id = _get_owner_id(request)
    from src.web.main import fetcher_processes

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")
        deleted_task = dict(tasks[task_id])
        await stop_task_process(task_id, fetcher_processes, owner_id=owner_id, task_name=deleted_task.get("task_name"))
        storage.delete_task(deleted_task.get("task_name"), owner_id=owner_id)
        await _refresh_local_scheduler()
    else:
        tasks = await _load_local_tasks()
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")
        deleted_task = dict(tasks[task_id])
        await stop_task_process(task_id, fetcher_processes, task_name=deleted_task.get("task_name"))
        tasks.pop(task_id)
        await _save_local_tasks(tasks)
        await _refresh_local_scheduler()

    criteria_file = deleted_task.get("ai_prompt_criteria_file")
    criteria_path = None
    if criteria_file:
        criteria_path = resolve_virtual_task_file(
            criteria_file,
            owner_id=owner_id if owner_id else None,
            for_write=True if owner_id else False,
        )
    if criteria_path and criteria_path.exists():
        try:
            os.remove(str(criteria_path))
        except OSError as exc:
            logger.warning(
                f"删除任务标准文件失败: {exc}",
                extra={"event": "task_criteria_delete_failed", "task_name": deleted_task.get("task_name")},
            )
    return {"message": "任务删除成功。", "task_name": deleted_task.get("task_name")}

@router.get("/api/scheduled-jobs")
async def get_scheduled_jobs_api(request: Request):
    owner_id = _get_owner_id(request)
    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        jobs = []
        for idx, task in enumerate(tasks):
            cron = task.get("cron")
            if not cron:
                continue
            jobs.append(
                {
                    "job_id": f"task_{idx}",
                    "task_id": idx,
                    "task_name": task.get("task_name"),
                    "cron": cron,
                    "next_run_time": None,
                    "order": task.get("order", idx),
                }
            )
        jobs.sort(key=lambda item: (item.get("order") is None, item.get("order", 0), item.get("task_name") or ""))
        return {"jobs": jobs}

    from src.web.main import scheduler
    from src.web.scheduler import get_scheduled_jobs
    return {"jobs": get_scheduled_jobs(scheduler)}


@router.post("/api/scheduled-jobs/{job_id}/skip")
async def skip_scheduled_job(job_id: str, request: Request):
    owner_id = _get_owner_id(request)
    if owner_id:
        return {"message": "多用户模式下该任务将等待下次触发", "next_run_time": None}

    from src.web.main import scheduler
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"定时任务 {job_id} 未找到。")

    try:
        current_next_run = getattr(job, "next_run_time", None)
        if not current_next_run and hasattr(job.trigger, "get_next_fire_time"):
            current_next_run = job.trigger.get_next_fire_time(None, datetime.now(timezone.utc))
        if not current_next_run:
            raise HTTPException(status_code=400, detail="无法获取当前执行时间")
        skipped_next_run = job.trigger.get_next_fire_time(current_next_run, current_next_run + timedelta(seconds=1))
        scheduler.modify_job(job_id, next_run_time=skipped_next_run)
        return {"message": "已跳过本次执行", "next_run_time": skipped_next_run.isoformat() if skipped_next_run else None}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"跳过任务执行时出错: {exc}") from exc


@router.post("/api/scheduled-jobs/{job_id}/run-now")
async def run_scheduled_job_now(job_id: str, request: Request):
    owner_id = _get_owner_id(request)
    from src.web.main import fetcher_processes

    if owner_id:
        try:
            task_id = int(job_id.replace("task_", ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="无效的任务ID") from exc
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail=f"定时任务 {job_id} 未找到。")
        task_name = tasks[task_id].get("task_name")
        await start_task_process(task_id, task_name, fetcher_processes, owner_id=owner_id)
        return {"message": f"任务 '{task_name}' 已开始执行"}

    from src.web.main import scheduler
    from src.web.scheduler import run_single_task
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"定时任务 {job_id} 未找到。")
    task_id = int(job_id.replace("task_", ""))
    task_name = job.args[1] if len(job.args) > 1 else job.name.replace("Scheduled: ", "")
    await run_single_task(task_id, task_name, fetcher_processes, update_task_running_status)
    return {"message": f"任务 '{task_name}' 已开始执行"}


@router.patch("/api/scheduled-jobs/{task_id}/cron")
async def update_scheduled_job_cron(task_id: int, cron_data: Dict[str, Any], request: Request):
    owner_id = _get_owner_id(request)
    new_cron = (cron_data.get("cron") or "").strip()
    if new_cron:
        try:
            CronTrigger.from_crontab(new_cron)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效的Cron表达式: {exc}") from exc

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")
        task = dict(tasks[task_id])
        task["cron"] = new_cron
        storage.save_task(task, owner_id=owner_id)
        await _refresh_local_scheduler()
        return {"message": "Cron 表达式已更新", "cron": new_cron}

    tasks = await _load_local_tasks()
    if not (0 <= task_id < len(tasks)):
        raise HTTPException(status_code=404, detail="任务未找到。")
    tasks[task_id]["cron"] = new_cron
    await _save_local_tasks(tasks)
    await _refresh_local_scheduler()
    return {"message": "Cron 表达式已更新", "cron": new_cron}


@router.post("/api/scheduled-jobs/{task_id}/cancel")
async def cancel_scheduled_task(task_id: int, request: Request):
    owner_id = _get_owner_id(request)
    from src.web.main import fetcher_processes

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")
        task = dict(tasks[task_id])
        task_name = task.get("task_name", f"任务 {task_id}")
        task["enabled"] = False
        storage.save_task(task, owner_id=owner_id)
        await stop_task_process(task_id, fetcher_processes, owner_id=owner_id, task_name=task_name)
        await _refresh_local_scheduler()
        return {"message": f"任务 '{task_name}' 已取消", "task_id": task_id}

    tasks = await _load_local_tasks()
    if not (0 <= task_id < len(tasks)):
        raise HTTPException(status_code=404, detail="任务未找到。")
    task_name = tasks[task_id].get("task_name", f"任务 {task_id}")
    tasks[task_id]["enabled"] = False
    await _save_local_tasks(tasks)
    await _refresh_local_scheduler()
    await stop_task_process(task_id, fetcher_processes, task_name=task_name)
    return {"message": f"任务 '{task_name}' 已取消", "task_id": task_id}

