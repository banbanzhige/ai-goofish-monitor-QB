import os
import asyncio
import sys
import re
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import aiofiles
from apscheduler.triggers.cron import CronTrigger

from src.logging_config import get_logger
from src.storage import get_storage
from src.web.auth import is_multi_user_mode


logger = get_logger(__name__, service="scheduler")

CONFIG_FILE = "config.json"
RUNTIME_TASK_CONFIG_DIR = os.path.join("state", "runtime_task_configs")


def _sanitize_identifier(value: str) -> str:
    """清理标识符，避免 job id 和临时文件名包含非法字符。"""
    return re.sub(r"[^0-9a-zA-Z_-]", "_", str(value or ""))


def _make_process_key(task_id: Union[int, str], task_name: str, owner_id: Optional[str]) -> Union[int, str]:
    """生成进程管理键，保证多用户任务唯一。"""
    if owner_id:
        return f"{owner_id}:{task_name}"
    return task_id


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
    """为调度子进程注入当前用户私有 AI 配置，避免回退到全局 .env。"""
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
            raise RuntimeError("当前用户AI配置不完整，无法启动定时任务。请先配置 API Key、Base URL 和模型名称。")

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
            "已为调度子进程注入用户私有AI配置",
            extra={"event": "scheduler_owner_ai_env_applied", "owner_id": owner_id},
        )
    except Exception as exc:
        logger.error(
            f"注入用户私有AI配置失败: {exc}",
            extra={"event": "scheduler_owner_ai_env_apply_failed", "owner_id": owner_id},
        )
        raise


async def _build_runtime_task_config(owner_id: str, task_name: str) -> str:
    """为多用户定时任务生成运行时配置文件，供 collector 子进程使用。"""
    storage = get_storage()
    task = storage.get_task_by_name(task_name, owner_id=owner_id)
    if not task:
        raise RuntimeError(f"任务不存在: owner_id={owner_id}, task_name={task_name}")

    os.makedirs(RUNTIME_TASK_CONFIG_DIR, exist_ok=True)
    safe_owner = _sanitize_identifier(owner_id)
    safe_task = _sanitize_identifier(task_name)
    config_path = os.path.join(
        RUNTIME_TASK_CONFIG_DIR,
        f"{safe_owner}_{safe_task}_{int(datetime.now().timestamp())}.json"
    )

    async with aiofiles.open(config_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps([task], ensure_ascii=False, indent=2))

    return config_path


def _task_has_generated_criteria(task: Dict[str, Any]) -> bool:
    """判断任务是否已经生成可用的 AI 标准。"""
    criteria_file = str(task.get("ai_prompt_criteria_file") or "")
    return bool(criteria_file) and not criteria_file.startswith("requirement/")


def _get_job_next_run_time(job):
    """安全获取 APScheduler job 的下一次执行时间，兼容不同版本。"""
    try:
        if hasattr(job, "next_run_time"):
            return job.next_run_time
    except Exception:
        pass

    try:
        trigger = getattr(job, "trigger", None)
        if trigger and hasattr(trigger, "get_next_fire_time"):
            now = datetime.now(timezone.utc)
            return trigger.get_next_fire_time(None, now)
    except Exception:
        return None

    return None


async def run_single_task(
    task_id: Union[int, str],
    task_name: str,
    fetcher_processes,
    update_task_running_status,
    owner_id: Optional[str] = None,
):
    """由调度器触发的任务执行入口。"""
    logger.info(
        f"定时任务触发: task_name={task_name}",
        extra={"event": "scheduled_task_trigger", "task_id": str(task_id), "task_name": task_name, "owner_id": owner_id}
    )

    log_file_handle = None
    runtime_config_path = None
    process_key = _make_process_key(task_id, task_name, owner_id)

    try:
        os.makedirs("logs", exist_ok=True)
        log_file_handle = open(os.path.join("logs", "fetcher.log"), "a", encoding="utf-8")

        cmd = [
            sys.executable,
            "-u",
            "collector.py",
            "--task-name",
            task_name,
            "--start-reason",
            "scheduled",
        ]

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
        await update_task_running_status(
            process_key if owner_id else task_id,
            True,
            process.pid,
            owner_id=owner_id,
            task_name=task_name,
        )

        logger.info(
            f"定时任务进程已启动: task_name={task_name}, pid={process.pid}",
            extra={"event": "task_started", "task_id": str(task_id), "task_name": task_name, "pid": process.pid, "owner_id": owner_id}
        )

        async def _monitor_process():
            try:
                await process.wait()
                if process.returncode == 0:
                    logger.info(
                        f"定时任务执行成功: task_name={task_name}",
                        extra={"event": "task_success", "task_id": str(task_id), "task_name": task_name, "owner_id": owner_id}
                    )
                else:
                    logger.error(
                        f"定时任务执行失败: task_name={task_name}, returncode={process.returncode}",
                        extra={"event": "task_failed", "task_id": str(task_id), "task_name": task_name, "owner_id": owner_id}
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

    except Exception as e:
        logger.error(
            f"启动定时任务失败: {e}",
            extra={"event": "task_start_error", "task_id": str(task_id), "task_name": task_name, "owner_id": owner_id}
        )
        await update_task_running_status(
            process_key if owner_id else task_id,
            False,
            owner_id=owner_id,
            task_name=task_name,
        )

        if runtime_config_path and os.path.exists(runtime_config_path):
            try:
                os.remove(runtime_config_path)
            except Exception:
                pass
    finally:
        if log_file_handle:
            try:
                log_file_handle.close()
            except Exception:
                pass


async def _set_all_tasks_stopped_in_config():
    """服务启动前统一清理任务运行态（本地/数据库模式）。"""
    try:
        if is_multi_user_mode():
            storage = get_storage()
            tasks = storage.get_tasks()
            changed = 0
            for task in tasks:
                if task.get("is_running") or task.get("generating_ai_criteria") or task.get("process_pid"):
                    task["is_running"] = False
                    task["generating_ai_criteria"] = False
                    task["process_pid"] = None
                    storage.save_task(task, owner_id=task.get("owner_id"))
                    changed += 1
            if changed:
                logger.info(
                    f"数据库模式已重置任务运行状态: {changed} 条",
                    extra={"event": "tasks_reset_storage", "count": changed}
                )
            return

        async with aiofiles.open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = await f.read()
            if not content.strip():
                return
            tasks = json.loads(content)

        needs_update = any(task.get("is_running") or task.get("generating_ai_criteria") for task in tasks)
        if not needs_update:
            return

        for task in tasks:
            task["is_running"] = False
            task["generating_ai_criteria"] = False

        async with aiofiles.open(CONFIG_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(tasks, ensure_ascii=False, indent=2))

        logger.info("本地模式任务状态已重置", extra={"event": "tasks_reset_local"})

    except FileNotFoundError:
        return
    except Exception as e:
        logger.error(f"重置任务状态时出错: {e}", extra={"event": "tasks_reset_error"})


async def _load_local_tasks_for_scheduler() -> List[Dict[str, Any]]:
    """读取本地模式任务配置。"""
    try:
        async with aiofiles.open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = await f.read()
            if not content.strip():
                return []
            tasks = json.loads(content)
            return tasks if isinstance(tasks, list) else []
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.error(f"读取本地任务配置失败: {e}", extra={"event": "scheduler_load_local_failed"})
        return []


def _load_storage_tasks_for_scheduler() -> List[Dict[str, Any]]:
    """读取数据库模式任务配置。"""
    try:
        storage = get_storage()
        tasks = storage.get_tasks()
        return tasks if isinstance(tasks, list) else []
    except Exception as e:
        logger.error(f"读取数据库任务配置失败: {e}", extra={"event": "scheduler_load_storage_failed"})
        return []


async def reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status):
    """重新加载调度任务，兼容本地模式与数据库模式。"""
    logger.info("正在重新加载定时任务调度器", extra={"event": "scheduler_reload"})
    sys.stdout.flush()

    scheduler.remove_all_jobs()

    if is_multi_user_mode():
        tasks = _load_storage_tasks_for_scheduler()
        for task in tasks:
            task_name = task.get("task_name")
            cron_str = task.get("cron")
            is_enabled = bool(task.get("enabled", False))
            owner_id = str(task.get("owner_id") or "").strip()
            if not owner_id:
                continue

            if task_name and cron_str and is_enabled and _task_has_generated_criteria(task):
                try:
                    trigger = CronTrigger.from_crontab(cron_str)
                    task_identifier = str(task.get("id") or f"{owner_id}:{task_name}")
                    safe_owner = _sanitize_identifier(owner_id)
                    safe_ident = _sanitize_identifier(task_identifier)
                    job_id = f"task_{safe_owner}_{safe_ident}"

                    scheduler.add_job(
                        run_single_task,
                        trigger=trigger,
                        args=[task_identifier, task_name, fetcher_processes, update_task_running_status, owner_id],
                        id=job_id,
                        name=f"Scheduled: {task_name}",
                        replace_existing=True,
                    )
                    logger.info(
                        f"已为数据库任务添加定时规则: owner_id={owner_id}, task_name={task_name}, cron={cron_str}",
                        extra={"event": "job_added", "task_name": task_name, "cron": cron_str, "owner_id": owner_id}
                    )
                except ValueError as e:
                    logger.warning(
                        f"数据库任务 Cron 无效，已跳过: owner_id={owner_id}, task_name={task_name}, cron={cron_str}, err={e}",
                        extra={"event": "invalid_cron", "task_name": task_name, "cron": cron_str, "owner_id": owner_id}
                    )
            elif task_name and cron_str and is_enabled and not _task_has_generated_criteria(task):
                logger.info(
                    f"数据库任务未生成标准，跳过调度: owner_id={owner_id}, task_name={task_name}",
                    extra={"event": "task_skipped", "task_name": task_name, "reason": "no_criteria", "owner_id": owner_id}
                )
    else:
        tasks = await _load_local_tasks_for_scheduler()
        for i, task in enumerate(tasks):
            task_name = task.get("task_name")
            cron_str = task.get("cron")
            is_enabled = bool(task.get("enabled", False))

            if task_name and cron_str and is_enabled and _task_has_generated_criteria(task):
                try:
                    trigger = CronTrigger.from_crontab(cron_str)
                    scheduler.add_job(
                        run_single_task,
                        trigger=trigger,
                        args=[i, task_name, fetcher_processes, update_task_running_status],
                        id=f"task_{i}",
                        name=f"Scheduled: {task_name}",
                        replace_existing=True,
                    )
                    logger.info(
                        f"已为本地任务添加定时规则: task_name={task_name}, cron={cron_str}",
                        extra={"event": "job_added", "task_name": task_name, "cron": cron_str}
                    )
                except ValueError as e:
                    logger.warning(
                        f"本地任务 Cron 无效，已跳过: task_name={task_name}, cron={cron_str}, err={e}",
                        extra={"event": "invalid_cron", "task_name": task_name, "cron": cron_str}
                    )
            elif task_name and cron_str and is_enabled and not _task_has_generated_criteria(task):
                logger.info(
                    f"本地任务未生成标准，跳过调度: task_name={task_name}",
                    extra={"event": "task_skipped", "task_name": task_name, "reason": "no_criteria"}
                )

    logger.info("定时任务加载完成", extra={"event": "scheduler_ready"})
    sys.stdout.flush()

    jobs = scheduler.get_jobs()
    if jobs:
        logger.info("当前已调度任务列表", extra={"event": "jobs_list", "count": len(jobs)})
        for job in jobs:
            next_run_time = _get_job_next_run_time(job)
            logger.info(
                f"Jobstore default: {job}",
                extra={
                    "event": "job_detail",
                    "job_id": job.id,
                    "job_name": job.name,
                    "next_run_time": next_run_time.isoformat() if next_run_time else None,
                },
            )


def get_scheduled_jobs(scheduler):
    """获取本地模式调度器任务详情（按下一次执行时间排序）。"""
    from datetime import datetime, timezone

    config_tasks = []
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config_tasks = json.load(f)
    except Exception:
        pass

    jobs = []
    for job in scheduler.get_jobs():
        try:
            task_id = int(str(job.id).replace("task_", ""))
        except ValueError:
            continue

        task_name = job.args[1] if len(job.args) > 1 else job.name.replace("Scheduled: ", "")

        cron_str = ""
        order_value = None
        if task_id < len(config_tasks):
            cron_str = config_tasks[task_id].get("cron", "")
            order_value = config_tasks[task_id].get("order")

        next_run = None
        if hasattr(job, "next_run_time") and job.next_run_time:
            next_run = job.next_run_time
        elif hasattr(job.trigger, "get_next_fire_time"):
            now = datetime.now(timezone.utc)
            next_run = job.trigger.get_next_fire_time(None, now)

        jobs.append(
            {
                "job_id": job.id,
                "task_id": task_id,
                "task_name": task_name,
                "cron": cron_str,
                "next_run_time": next_run.isoformat() if next_run else None,
                "order": order_value,
                "_next_run_dt": next_run,
            }
        )

    has_custom_order = any(job.get("order") is not None for job in jobs)
    if has_custom_order:
        jobs.sort(key=lambda x: x.get("order") if x.get("order") is not None else float("inf"))
    else:
        jobs.sort(key=lambda x: x["_next_run_dt"] or datetime.max.replace(tzinfo=timezone.utc))

    for i, job in enumerate(jobs):
        job["execution_order"] = i + 1
        del job["_next_run_dt"]

    return jobs

