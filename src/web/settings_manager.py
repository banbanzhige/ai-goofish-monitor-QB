import os
import aiofiles
import json
from typing import Optional
from urllib.parse import quote, unquote, urlparse
from fastapi import APIRouter, HTTPException, Depends
from src.web.models import NotificationSettings, GenericSettings, NewPromptRequest, PromptUpdate, LoginStateUpdate, BayesUpdate
from src.config import (
    get_env_value,
    get_bool_env_value,
    save_env_settings,
    normalize_database_url,
    STORAGE_BACKEND,
    DATABASE_URL,
    WEB_USERNAME,
    WEB_PASSWORD
)
from src.storage import get_storage
from src.logging_config import get_logger
from src.user_file_store import list_scoped_files, resolve_scoped_path
from src.web.ai_health import get_ai_health_snapshot, invalidate_ai_health_snapshot
from src.web.auth import require_auth, check_permission, has_category, get_user_management_level

logger = get_logger(__name__, service="web")

router = APIRouter()
REQUIRED_POSTGRES_TABLES = ("users", "user_groups", "user_group_members", "group_permissions")
_NOTIFICATION_SECRET_KEYS = {"GOTIFY_TOKEN", "WX_SECRET", "TELEGRAM_BOT_TOKEN", "DINGTALK_SECRET"}
_GENERIC_SECRET_KEYS = {"WEB_PASSWORD"}
_AI_SECRET_KEYS = {"OPENAI_API_KEY"}
_PROXY_SETTING_KEYS = [
    "PROXY_URL",
    "PROXY_AI_ENABLED",
    "PROXY_NTFY_ENABLED",
    "PROXY_GOTIFY_ENABLED",
    "PROXY_BARK_ENABLED",
    "PROXY_WX_BOT_ENABLED",
    "PROXY_WX_APP_ENABLED",
    "PROXY_TELEGRAM_ENABLED",
    "PROXY_WEBHOOK_ENABLED",
    "PROXY_DINGTALK_ENABLED",
]
_PROXY_BOOL_KEYS = {
    "PROXY_AI_ENABLED",
    "PROXY_NTFY_ENABLED",
    "PROXY_GOTIFY_ENABLED",
    "PROXY_BARK_ENABLED",
    "PROXY_WX_BOT_ENABLED",
    "PROXY_WX_APP_ENABLED",
    "PROXY_TELEGRAM_ENABLED",
    "PROXY_WEBHOOK_ENABLED",
    "PROXY_DINGTALK_ENABLED",
}
_NOTIFICATION_REQUIRED_CONFIG_KEYS = {
    "wx_app": ["corp_id", "agent_id", "secret"],
    "wx_bot": ["bot_url"],
    "dingtalk": ["webhook"],
    "telegram": ["bot_token", "chat_id"],
    "ntfy": ["topic_url"],
    "gotify": ["url", "token"],
    "bark": ["url"],
    "webhook": ["url"],
}


def _reset_storage_runtime_caches():
    """重置存储相关运行时缓存，确保后端切换后立即生效。"""
    try:
        from src.storage import reset_storage
        reset_storage()
    except Exception as exc:
        logger.warning(f"[数据库模式] 重置存储单例失败: {exc}")

    try:
        from src.feedback.sample_manager import clear_sample_manager_cache
        clear_sample_manager_cache()
    except Exception as exc:
        logger.warning(f"[数据库模式] 清理反馈样本管理器缓存失败: {exc}")

    try:
        from src.web.session_manager import reset_session_manager
        reset_session_manager()
    except Exception as exc:
        logger.warning(f"[数据库模式] 重置会话管理器单例失败: {exc}")


def _require_settings_admin(user: dict = Depends(require_auth)) -> dict:
    """要求当前用户具备系统设置管理权限。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if not check_permission(user, "manage_system"):
        raise HTTPException(status_code=403, detail="权限不足，需要系统设置管理权限")
    return user


def _require_notify_access(user: dict = Depends(require_auth)) -> dict:
    """要求当前用户具备通知配置权限。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if not (has_category(user, "notify") or check_permission(user, "manage_system")):
        raise HTTPException(status_code=403, detail="权限不足，需要通知配置权限")
    return user


def _require_ai_access(user: dict = Depends(require_auth)) -> dict:
    """要求当前用户具备 AI 配置权限。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if not (has_category(user, "ai") or check_permission(user, "manage_system")):
        raise HTTPException(status_code=403, detail="权限不足，需要 AI 配置权限")
    return user


def _require_ai_or_tasks_access(user: dict = Depends(require_auth)) -> dict:
    """读取 AI 相关资源时允许 AI/任务/系统管理权限。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if has_category(user, "ai") or has_category(user, "tasks") or check_permission(user, "manage_system"):
        return user
    raise HTTPException(status_code=403, detail="权限不足，需要 AI 或任务权限")


def _require_accounts_access(user: dict = Depends(require_auth)) -> dict:
    """要求当前用户具备账号管理权限。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if not (has_category(user, "accounts") or check_permission(user, "manage_system")):
        raise HTTPException(status_code=403, detail="权限不足，需要账号管理权限")
    return user


def _require_generic_settings_modify_admin(user: dict = Depends(require_auth)) -> dict:
    """要求当前用户具备管理员级别（admin/super_admin）以修改通用配置。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if get_user_management_level(user) < 3:
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可修改通用配置")
    return user


def _validate_safe_filename(filename: str, required_ext: str = "") -> str:
    """校验文件名，阻断路径穿越与平台相关路径写入。"""
    safe_name = (filename or "").strip()
    if required_ext and safe_name and not safe_name.lower().endswith(required_ext.lower()):
        safe_name = f"{safe_name}{required_ext}"
    if not safe_name:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    if any(token in safe_name for token in ("/", "\\", "\x00")):
        raise HTTPException(status_code=400, detail="无效的文件名。")
    if ":" in safe_name:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    if safe_name in {".", ".."} or ".." in safe_name:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    if os.path.basename(safe_name) != safe_name:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    drive, _ = os.path.splitdrive(safe_name)
    if drive or os.path.isabs(safe_name):
        raise HTTPException(status_code=400, detail="无效的文件名。")
    return safe_name


def _preserve_secret_on_empty(settings_dict: dict, secret_keys: set) -> dict:
    """对于密钥字段，前端传空字符串时保持原值不变。"""
    merged = dict(settings_dict)
    for key in secret_keys:
        if key not in merged:
            continue
        value = merged.get(key)
        if isinstance(value, str) and value.strip() == "":
            merged[key] = get_env_value(key, "")
    return merged


def _resolve_current_user_id(user: dict) -> str:
    """解析当前登录用户ID。"""
    user_id = str((user or {}).get("user_id") or (user or {}).get("id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="未识别当前用户")
    return user_id


def _resolve_owner_for_scoped_files(user: dict) -> Optional[str]:
    """解析文件作用域 owner_id（仅 PostgreSQL 模式启用用户隔离）。"""
    if STORAGE_BACKEND() != "postgres":
        return None
    return _resolve_current_user_id(user)


def _normalize_bayes_version(value: str) -> str:
    """标准化 Bayes 版本名称（不含 .json 后缀）。"""
    text = str(value or "").strip()
    if text.endswith(".json"):
        text = text[:-5]
    if not text:
        raise HTTPException(status_code=400, detail="无效的 Bayes 版本名。")
    if any(token in text for token in ("/", "\\", ":", "\x00")):
        raise HTTPException(status_code=400, detail="无效的 Bayes 版本名。")
    return text


def _build_ai_settings_from_user_api_config(user_api_config: dict) -> dict:
    """将用户API配置转换为AI设置响应结构。"""
    config_data = user_api_config if isinstance(user_api_config, dict) else {}
    extra_config = config_data.get("extra_config") if isinstance(config_data.get("extra_config"), dict) else {}

    tokens_limit = extra_config.get("AI_MAX_TOKENS_LIMIT")
    if tokens_limit in (None, ""):
        normalized_tokens_limit = ""
    else:
        try:
            normalized_tokens_limit = int(tokens_limit)
        except (TypeError, ValueError):
            normalized_tokens_limit = ""

    return {
        "OPENAI_API_KEY": "",
        "OPENAI_API_KEY_SET": bool(str(config_data.get("api_key") or "").strip()),
        "OPENAI_BASE_URL": str(config_data.get("api_base_url") or "").strip(),
        "OPENAI_MODEL_NAME": str(config_data.get("model") or "").strip(),
        "PROXY_URL": str(extra_config.get("PROXY_URL") or "").strip(),
        "AI_MAX_TOKENS_PARAM_NAME": str(extra_config.get("AI_MAX_TOKENS_PARAM_NAME") or "").strip(),
        "AI_MAX_TOKENS_LIMIT": normalized_tokens_limit,
    }


def _to_bool_value(value, default: bool = False) -> bool:
    """把任意值转换为布尔值。"""
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


def _build_proxy_settings_from_extra_config(extra_config: dict) -> dict:
    """从用户API扩展配置构造代理设置响应。"""
    extra = extra_config if isinstance(extra_config, dict) else {}
    settings = {}
    for key in _PROXY_SETTING_KEYS:
        if key in _PROXY_BOOL_KEYS:
            settings[key] = _to_bool_value(extra.get(key), default=False)
        else:
            settings[key] = str(extra.get(key) or "").strip()
    return settings


def _is_notification_config_complete(config_item: dict) -> bool:
    """判断用户通知配置是否填写完整。"""
    if not isinstance(config_item, dict):
        return False
    channel_type = str(config_item.get("channel_type") or "").strip().lower()
    config_data = config_item.get("config") if isinstance(config_item.get("config"), dict) else {}
    required_keys = _NOTIFICATION_REQUIRED_CONFIG_KEYS.get(channel_type, [])
    if not required_keys:
        return bool(config_data)
    return all(bool(str(config_data.get(key) or "").strip()) for key in required_keys)


def _build_notification_status(user: dict) -> dict:
    """构建通知渠道状态，按运行模式选择真实配置来源。"""
    if STORAGE_BACKEND() == "postgres":
        try:
            user_id = _resolve_current_user_id(user)
            configs = get_storage().get_user_notification_configs(user_id)
            enabled_configs = [
                item for item in configs
                if isinstance(item, dict) and bool(item.get("is_enabled", False))
            ]
            complete_enabled_configs = [
                item for item in enabled_configs
                if _is_notification_config_complete(item)
            ]
            ok = len(complete_enabled_configs) > 0
            return {
                "source": "postgres_user_notification_configs",
                "source_label": "当前用户通知配置（PostgreSQL）",
                "configured_count": len(configs),
                "enabled_count": len(enabled_configs),
                "complete_enabled_count": len(complete_enabled_configs),
                "ok": ok,
                "message": "已存在可用通知渠道。" if ok else "未配置可用通知渠道（需至少一个启用且完整的渠道）。",
            }
        except Exception as exc:
            logger.warning(
                "读取用户通知配置状态失败",
                extra={"event": "notification_status_load_failed"},
                exc_info=exc,
            )
            return {
                "source": "postgres_user_notification_configs",
                "source_label": "当前用户通知配置（PostgreSQL）",
                "configured_count": 0,
                "enabled_count": 0,
                "complete_enabled_count": 0,
                "ok": False,
                "message": "读取用户通知配置失败，请检查日志。",
            }

    has_any_channel = bool(
        get_env_value("NTFY_TOPIC_URL", "")
        or (get_env_value("GOTIFY_URL", "") and get_env_value("GOTIFY_TOKEN", ""))
        or get_env_value("BARK_URL", "")
        or get_env_value("WX_BOT_URL", "")
        or (
            get_env_value("WX_CORP_ID", "")
            and get_env_value("WX_AGENT_ID", "")
            and get_env_value("WX_SECRET", "")
        )
        or (get_env_value("TELEGRAM_BOT_TOKEN", "") and get_env_value("TELEGRAM_CHAT_ID", ""))
        or get_env_value("WEBHOOK_URL", "")
        or get_env_value("DINGTALK_WEBHOOK", "")
    )
    return {
        "source": "env_global_notification_config",
        "source_label": "全局配置（.env）",
        "configured_count": 1 if has_any_channel else 0,
        "enabled_count": 1 if has_any_channel else 0,
        "complete_enabled_count": 1 if has_any_channel else 0,
        "ok": has_any_channel,
        "message": "已存在可用通知渠道。" if has_any_channel else "未配置可用通知渠道。",
    }


@router.get("/api/settings/status")
async def get_system_status(user: dict = Depends(_require_settings_admin)):
    """检查系统关键文件和配置的状态。"""
    from src.web.main import fetcher_processes
    from src.config import (
        API_KEY, BASE_URL, MODEL_NAME, NTFY_TOPIC_URL, GOTIFY_URL,
        GOTIFY_TOKEN, BARK_URL, WX_BOT_URL, WX_CORP_ID, WX_AGENT_ID,
        WX_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEBHOOK_URL
    )

    running_pids = []
    for task_id, process in list(fetcher_processes.items()):
        if process.returncode is None:
            running_pids.append(process.pid)
        else:
            logger.info(
                "检测到任务进程已结束",
                extra={"event": "task_process_finished", "pid": process.pid, "task_id": task_id, "returncode": process.returncode}
            )
            del fetcher_processes[task_id]
            from src.web.task_manager import update_task_running_status
            import asyncio
            asyncio.create_task(update_task_running_status(task_id, False))

    storage_runtime = _get_storage_runtime_status()
    ai_health = get_ai_health_snapshot(user)
    ai_config = ai_health.get("config") if isinstance(ai_health.get("config"), dict) else {}
    notification_status = _build_notification_status(user)

    openai_api_key_set = bool(ai_config.get("api_key_set"))
    openai_base_url_set = bool(ai_config.get("base_url_set"))
    openai_model_name_set = bool(ai_config.get("model_name_set"))
    if not any([openai_api_key_set, openai_base_url_set, openai_model_name_set]):
        # 兼容旧逻辑：当健康快照无配置信息时回退到访问器读取。
        openai_api_key_set = bool(API_KEY())
        openai_base_url_set = bool(BASE_URL())
        openai_model_name_set = bool(MODEL_NAME())

    status = {
        "scraper_running": len(running_pids) > 0,
        # [已弃用] 原xianyu_state.json检查 - 现改为检查账号目录
        "login_state_file": {
            # 检查state目录是否有可用账号
            "exists": os.path.exists("state") and any(
                f.endswith(".json") and not f.startswith("_") 
                for f in os.listdir("state") if os.path.isfile(os.path.join("state", f))
            ) if os.path.exists("state") else False,
            "path": "state/*.json"  # 现使用多账号管理
        },
        "env_file": {
            "exists": os.path.exists(".env"),
            "openai_api_key_set": openai_api_key_set,
            "openai_base_url_set": openai_base_url_set,
            "openai_model_name_set": openai_model_name_set,
            "ntfy_topic_url_set": bool(NTFY_TOPIC_URL()),
            "gotify_url_set": bool(GOTIFY_URL()),
            "gotify_token_set": bool(GOTIFY_TOKEN()),
            "bark_url_set": bool(BARK_URL()),
            "wx_bot_url_set": bool(WX_BOT_URL()),
            "wx_corp_id_set": bool(WX_CORP_ID()),
            "wx_agent_id_set": bool(WX_AGENT_ID()),
            "wx_secret_set": bool(WX_SECRET()),
            "telegram_bot_token_set": bool(TELEGRAM_BOT_TOKEN()),
            "telegram_chat_id_set": bool(TELEGRAM_CHAT_ID()),
            "webhook_url_set": bool(WEBHOOK_URL()),
            "dingtalk_webhook_set": bool(get_env_value("DINGTALK_WEBHOOK", "")),
        },
        "storage_runtime": storage_runtime,
        "ai_api": ai_health,
        "notification_status": notification_status,
    }
    return status


@router.get("/api/prompts")
async def list_prompts(user: dict = Depends(_require_ai_or_tasks_access)):
    """列出 Prompt 模板文件名。"""
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        storage = get_storage()
        templates = storage.list_prompt_templates(owner_id=owner_id, include_system=True)
        names = {
            str(item.get("name") or "").strip()
            for item in templates
            if str(item.get("name") or "").strip().lower().endswith(".txt")
        }
        return sorted(name for name in names if name)
    return list_scoped_files("prompts", owner_id=owner_id, include_shared=True)


@router.post("/api/prompts")
async def create_new_prompt(new_prompt: NewPromptRequest, user: dict = Depends(_require_ai_access)):
    """创建一个新的 prompt 文件。"""
    safe_filename = _validate_safe_filename(new_prompt.filename, required_ext=".txt")
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        storage = get_storage()
        existing = storage.get_prompt_template(safe_filename, owner_id=owner_id)
        if existing:
            raise HTTPException(status_code=400, detail="该文件名已存在。")
        storage.save_prompt_template(
            {
                "name": safe_filename,
                "content": new_prompt.content,
                "is_default": safe_filename == "base_prompt.txt",
            },
            owner_id=owner_id,
        )
        return {"message": f"Prompt 文件 '{safe_filename}' 创建成功。"}

    existing_path = resolve_scoped_path("prompts", safe_filename, owner_id=owner_id, for_write=False)
    if existing_path.exists():
        raise HTTPException(status_code=400, detail="该文件名已存在。")

    try:
        filepath = resolve_scoped_path("prompts", safe_filename, owner_id=owner_id, for_write=True)
        async with aiofiles.open(str(filepath), 'w', encoding='utf-8') as f:
            await f.write(new_prompt.content)
        return {"message": f"Prompt 文件 '{safe_filename}' 创建成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Prompt 文件时出错: {e}")


@router.get("/api/prompts/{filename}")
async def get_prompt_content(filename: str, user: dict = Depends(_require_ai_or_tasks_access)):
    """获取指定 prompt 文件的内容。"""
    safe_filename = _validate_safe_filename(filename, required_ext=".txt")
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        storage = get_storage()
        template = storage.get_prompt_template(safe_filename, owner_id=owner_id)
        if not template:
            raise HTTPException(status_code=404, detail="Prompt 文件未找到。")
        return {
            "filename": safe_filename,
            "content": str(template.get("content") or ""),
        }

    filepath = resolve_scoped_path("prompts", safe_filename, owner_id=owner_id, for_write=False)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    async with aiofiles.open(str(filepath), 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": safe_filename, "content": content}


@router.get("/api/criteria")
async def list_criteria_files(user: dict = Depends(_require_ai_or_tasks_access)):
    """列出 criteria/ 目录下的所有 .txt 文件。"""
    owner_id = _resolve_owner_for_scoped_files(user)
    return list_scoped_files("criteria", owner_id=owner_id, include_shared=True)


@router.get("/api/criteria/{filename}")
async def get_criteria_content(filename: str, user: dict = Depends(_require_ai_or_tasks_access)):
    """获取指定 criteria 文件的内容。"""
    safe_filename = _validate_safe_filename(filename)
    owner_id = _resolve_owner_for_scoped_files(user)

    requirement_path = resolve_scoped_path("requirement", safe_filename, owner_id=owner_id, for_write=False)
    if requirement_path.exists():
        async with aiofiles.open(str(requirement_path), 'r', encoding='utf-8') as f:
            content = await f.read()
        return {"filename": safe_filename, "content": content}

    filepath = resolve_scoped_path("criteria", safe_filename, owner_id=owner_id, for_write=False)
    if not filepath.exists():
        logger.debug(
            "Criteria 文件未找到",
            extra={
                "event": "criteria_file_not_found",
                "criteria_path": filepath,
                "requirement_path": requirement_path,
                "criteria_filename": safe_filename
            }
        )
        raise HTTPException(status_code=404, detail="Criteria 文件未找到。")

    async with aiofiles.open(str(filepath), 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": safe_filename, "content": content}


@router.put("/api/criteria/{filename}")
async def update_criteria_content(filename: str, prompt_update: PromptUpdate, user: dict = Depends(_require_ai_or_tasks_access)):
    """更新指定 criteria 文件的内容。"""
    safe_filename = _validate_safe_filename(filename)
    owner_id = _resolve_owner_for_scoped_files(user)

    requirement_path = resolve_scoped_path("requirement", safe_filename, owner_id=owner_id, for_write=False)
    if requirement_path.exists():
        try:
            write_path = resolve_scoped_path(
                "requirement",
                safe_filename,
                owner_id=owner_id,
                for_write=True if owner_id else False,
            )
            async with aiofiles.open(str(write_path), 'w', encoding='utf-8') as f:
                await f.write(prompt_update.content)
            return {"message": f"Requirement 文件 '{safe_filename}' 更新成功。"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入 Requirement 文件时出错: {e}")

    filepath = resolve_scoped_path("criteria", safe_filename, owner_id=owner_id, for_write=False)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Criteria 文件未找到。")

    try:
        write_path = resolve_scoped_path(
            "criteria",
            safe_filename,
            owner_id=owner_id,
            for_write=True if owner_id else False,
        )
        async with aiofiles.open(str(write_path), 'w', encoding='utf-8') as f:
            await f.write(prompt_update.content)
        return {"message": f"Criteria 文件 '{safe_filename}' 更新成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Criteria 文件时出错: {e}")


@router.put("/api/prompts/{filename}")
async def update_prompt_content(filename: str, prompt_update: PromptUpdate, user: dict = Depends(_require_ai_access)):
    """更新指定 prompt 文件的内容。"""
    safe_filename = _validate_safe_filename(filename, required_ext=".txt")
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        storage = get_storage()
        existing = storage.get_prompt_template(safe_filename, owner_id=owner_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Prompt 文件未找到。")
        storage.save_prompt_template(
            {
                "name": safe_filename,
                "content": prompt_update.content,
                "is_default": bool(existing.get("is_default", safe_filename == "base_prompt.txt")),
            },
            owner_id=owner_id,
        )
        return {"message": f"Prompt 文件 '{safe_filename}' 更新成功。"}

    read_path = resolve_scoped_path("prompts", safe_filename, owner_id=owner_id, for_write=False)

    if not read_path.exists():
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    try:
        write_path = resolve_scoped_path(
            "prompts",
            safe_filename,
            owner_id=owner_id,
            for_write=True if owner_id else False,
        )
        async with aiofiles.open(str(write_path), 'w', encoding='utf-8') as f:
            await f.write(prompt_update.content)
        return {"message": f"Prompt 文件 '{safe_filename}' 更新成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Prompt 文件时出错: {e}")


@router.get("/api/bayes")
async def list_bayes_profiles(user: dict = Depends(_require_ai_or_tasks_access)):
    """列出 Bayes 配置文件名。"""
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        try:
            storage = get_storage()
            profiles = storage.list_bayes_profiles(owner_id=owner_id, include_system=True)
            versions = {
                str(item.get("version") or "").strip()
                for item in profiles
                if str(item.get("version") or "").strip()
            }
            if versions:
                return sorted(f"{version}.json" for version in versions)
        except Exception as e:
            logger.warning(
                "数据库读取 Bayes 列表失败，回退文件扫描",
                extra={"event": "settings_bayes_list_db_failed", "owner_id": owner_id},
                exc_info=e
            )
    return list_scoped_files("bayes", owner_id=owner_id, include_shared=True)


@router.post("/api/bayes")
async def create_bayes_profile(new_profile: NewPromptRequest, user: dict = Depends(_require_ai_access)):
    """创建一个新的 Bayes 参数文件。"""
    safe_filename = _validate_safe_filename(new_profile.filename, required_ext=".json")
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        normalized_version = _normalize_bayes_version(safe_filename)
        storage = get_storage()
        existing = storage.get_bayes_profile(normalized_version, owner_id=owner_id)
        if existing:
            raise HTTPException(status_code=400, detail="该文件名已存在。")
        try:
            payload = json.loads(new_profile.content or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Bayes 配置 JSON 格式错误: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Bayes 配置必须是 JSON 对象。")
        payload["version"] = normalized_version
        storage.save_bayes_profile(payload, owner_id=owner_id)
        return {"message": f"Bayes 文件 '{safe_filename}' 创建成功。"}

    existing_path = resolve_scoped_path("bayes", safe_filename, owner_id=owner_id, for_write=False)
    if existing_path.exists():
        raise HTTPException(status_code=400, detail="该文件名已存在。")

    try:
        filepath = resolve_scoped_path("bayes", safe_filename, owner_id=owner_id, for_write=True)
        async with aiofiles.open(str(filepath), 'w', encoding='utf-8') as f:
            await f.write(new_profile.content)
        return {"message": f"Bayes 文件 '{safe_filename}' 创建成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Bayes 文件时出错: {e}")


@router.get("/api/bayes/{filename}")
async def get_bayes_profile(filename: str, user: dict = Depends(_require_ai_or_tasks_access)):
    """获取指定 Bayes 参数文件的内容。"""
    safe_filename = _validate_safe_filename(filename, required_ext=".json")
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        normalized_version = _normalize_bayes_version(safe_filename)
        try:
            storage = get_storage()
            profile = storage.get_bayes_profile(normalized_version, owner_id=owner_id)
            if profile:
                return {
                    "filename": safe_filename,
                    "content": json.dumps(profile, ensure_ascii=False, indent=2),
                }
        except Exception as e:
            logger.warning(
                "数据库读取 Bayes 内容失败，回退文件读取",
                extra={"event": "settings_bayes_get_db_failed", "owner_id": owner_id, "bayes_filename": safe_filename},
                exc_info=e
            )

    filepath = resolve_scoped_path("bayes", safe_filename, owner_id=owner_id, for_write=False)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Bayes 文件未找到。")

    async with aiofiles.open(str(filepath), 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": safe_filename, "content": content}


@router.put("/api/bayes/{filename}")
async def update_bayes_profile(filename: str, bayes_update: BayesUpdate, user: dict = Depends(_require_ai_access)):
    """更新指定 Bayes 参数文件的内容。"""
    safe_filename = _validate_safe_filename(filename, required_ext=".json")
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        normalized_version = _normalize_bayes_version(safe_filename)
        storage = get_storage()
        existing = storage.get_bayes_profile(normalized_version, owner_id=owner_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Bayes 文件未找到。")
        try:
            payload = json.loads(bayes_update.content or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Bayes 配置 JSON 格式错误: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Bayes 配置必须是 JSON 对象。")
        payload["version"] = normalized_version
        storage.save_bayes_profile(payload, owner_id=owner_id)
        return {"message": f"Bayes 文件 '{safe_filename}' 更新成功。"}

    read_path = resolve_scoped_path("bayes", safe_filename, owner_id=owner_id, for_write=False)
    if not read_path.exists():
        raise HTTPException(status_code=404, detail="Bayes 文件未找到。")

    try:
        write_path = resolve_scoped_path(
            "bayes",
            safe_filename,
            owner_id=owner_id,
            for_write=True if owner_id else False,
        )
        async with aiofiles.open(str(write_path), 'w', encoding='utf-8') as f:
            await f.write(bayes_update.content)
        return {"message": f"Bayes 文件 '{safe_filename}' 更新成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Bayes 文件时出错: {e}")


@router.delete("/api/bayes/{filename}")
async def delete_bayes_profile(filename: str, user: dict = Depends(_require_ai_access)):
    """删除指定的 Bayes 参数文件。"""
    safe_filename = _validate_safe_filename(filename, required_ext=".json")
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        normalized_version = _normalize_bayes_version(safe_filename)
        storage = get_storage()
        if owner_id:
            deleted = storage.delete_bayes_profile(normalized_version, owner_id=owner_id)
            if deleted:
                if storage.get_bayes_profile(normalized_version, owner_id=owner_id):
                    return {"message": f"Bayes 文件 '{safe_filename}' 的个人副本已删除（系统共享模板仍保留）。"}
                return {"message": f"Bayes 文件 '{safe_filename}' 删除成功。"}
            if storage.get_bayes_profile(normalized_version, owner_id=owner_id):
                raise HTTPException(status_code=400, detail="该 Bayes 文件为系统共享模板，当前账号不能直接删除。")
            raise HTTPException(status_code=404, detail="Bayes 文件未找到。")

        all_profiles = storage.list_bayes_profiles(owner_id=None, include_system=True)
        all_versions = {
            str(item.get("version") or "").strip()
            for item in all_profiles
            if str(item.get("version") or "").strip()
        }
        if normalized_version in all_versions and len(all_versions) <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个 Bayes 配置版本")

        deleted = storage.delete_bayes_profile(normalized_version, owner_id=None)
        if not deleted:
            raise HTTPException(status_code=404, detail="Bayes 文件未找到。")
        return {"message": f"Bayes 文件 '{safe_filename}' 删除成功。"}

    if owner_id:
        # 多用户模式：仅允许删除当前用户私有覆盖文件，不允许删除系统共享模板
        user_path = resolve_scoped_path("bayes", safe_filename, owner_id=owner_id, for_write=True)
        shared_path = resolve_scoped_path("bayes", safe_filename, owner_id=None, for_write=False)
        if user_path.exists():
            try:
                os.remove(str(user_path))
                if shared_path.exists():
                    return {"message": f"Bayes 文件 '{safe_filename}' 的个人副本已删除（系统共享模板仍保留）。"}
                return {"message": f"Bayes 文件 '{safe_filename}' 删除成功。"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"删除 Bayes 文件时出错: {e}")
        if shared_path.exists():
            raise HTTPException(status_code=400, detail="该 Bayes 文件为系统共享模板，当前账号不能直接删除。")
        raise HTTPException(status_code=404, detail="Bayes 文件未找到。")

    filepath = resolve_scoped_path("bayes", safe_filename, owner_id=None, for_write=False)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Bayes 文件未找到。")
    try:
        os.remove(str(filepath))
        return {"message": f"Bayes 文件 '{safe_filename}' 删除成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Bayes 文件时出错: {e}")



@router.get("/api/guides/bayes")
async def get_bayes_guide(_user: dict = Depends(_require_ai_or_tasks_access)):
    """??Bayes??????????"""
    guide_path = os.path.join("prompts", "guide", "bayes_guide.md")
    if not os.path.exists(guide_path):
        raise HTTPException(status_code=404, detail="Bayes????????")
    async with aiofiles.open(guide_path, 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": "bayes_guide.md", "content": content}

@router.delete("/api/prompts/{filename}")
async def delete_prompt(filename: str, user: dict = Depends(_require_ai_access)):
    """删除指定的 prompt 文件。"""
    safe_filename = _validate_safe_filename(filename, required_ext=".txt")
    owner_id = _resolve_owner_for_scoped_files(user)
    if STORAGE_BACKEND() == "postgres":
        storage = get_storage()
        if owner_id:
            deleted = storage.delete_prompt_template(safe_filename, owner_id=owner_id)
            if deleted:
                if storage.get_prompt_template(safe_filename, owner_id=owner_id):
                    return {"message": f"Prompt 文件 '{safe_filename}' 的个人副本已删除（系统共享模板仍保留）。"}
                return {"message": f"Prompt 文件 '{safe_filename}' 删除成功。"}
            if storage.get_prompt_template(safe_filename, owner_id=owner_id):
                raise HTTPException(status_code=400, detail="该 Prompt 文件为系统共享模板，当前账号不能直接删除。")
            raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

        deleted = storage.delete_prompt_template(safe_filename, owner_id=None)
        if not deleted:
            raise HTTPException(status_code=404, detail="Prompt 文件未找到。")
        return {"message": f"Prompt 文件 '{safe_filename}' 删除成功。"}

    if owner_id:
        # 多用户模式：仅允许删除当前用户私有覆盖文件，不允许删除系统共享模板
        user_path = resolve_scoped_path("prompts", safe_filename, owner_id=owner_id, for_write=True)
        shared_path = resolve_scoped_path("prompts", safe_filename, owner_id=None, for_write=False)
        if user_path.exists():
            try:
                os.remove(str(user_path))
                if shared_path.exists():
                    return {"message": f"Prompt 文件 '{safe_filename}' 的个人副本已删除（系统共享模板仍保留）。"}
                return {"message": f"Prompt 文件 '{safe_filename}' 删除成功。"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"删除 Prompt 文件时出错: {e}")
        if shared_path.exists():
            raise HTTPException(status_code=400, detail="该 Prompt 文件为系统共享模板，当前账号不能直接删除。")
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    filepath = resolve_scoped_path("prompts", safe_filename, owner_id=None, for_write=False)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")
    try:
        os.remove(str(filepath))
        return {"message": f"Prompt 文件 '{safe_filename}' 删除成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Prompt 文件时出错: {e}")


async def _cleanup_login_process(process):
    """清理登录进程的后台任务"""
    await process.wait()
    from src.web.main import login_process
    login_process = None
    logger.info(
        "自动登录程序已结束",
        extra={"event": "manual_login_process_stopped", "pid": process.pid}
    )


@router.post("/api/manual-login")
async def start_manual_login(_user: dict = Depends(_require_accounts_access)):
    """启动自动登录程序 login.py"""
    from src.web.main import login_process
    import asyncio
    import sys

    try:
        if not os.path.exists("login.py"):
            raise HTTPException(status_code=500, detail="未找到 login.py，无法启动自动登录程序。")

        if login_process is not None and login_process.returncode is None:
            return {"message": "已有登录进程在运行中，请等待其完成或关闭后再尝试。"}

        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "login.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=child_env
        )

        login_process = process
        logger.info(
            "自动登录程序已启动",
            extra={"event": "manual_login_process_started", "pid": process.pid}
        )

        asyncio.create_task(_cleanup_login_process(process))

        return {"message": "自动登录程序已成功启动，请在服务器上查看浏览器窗口并完成登录。"}
    except Exception as e:
        login_process = None
        raise HTTPException(status_code=500, detail=f"启动自动登录程序时出错: {str(e)}")


@router.get("/api/settings/notifications")
async def get_notification_settings(_user: dict = Depends(_require_notify_access)):
    """获取通知设置。"""
    if STORAGE_BACKEND() == "postgres":
        raise HTTPException(
            status_code=400,
            detail="服务器模式请使用用户级通知配置，不再使用全局 .env 通知设置。"
        )

    notification_keys = [
        "NTFY_TOPIC_URL", "NTFY_ENABLED", "GOTIFY_URL", "GOTIFY_TOKEN", "GOTIFY_ENABLED",
        "BARK_URL", "BARK_ENABLED", "WX_BOT_URL", "WX_BOT_ENABLED", "WX_CORP_ID", "WX_AGENT_ID",
        "WX_SECRET", "WX_TO_USER", "WX_APP_ENABLED", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
        "TELEGRAM_ENABLED", "WEBHOOK_URL", "WEBHOOK_ENABLED", "WEBHOOK_METHOD", "WEBHOOK_HEADERS",
        "WEBHOOK_CONTENT_TYPE", "WEBHOOK_QUERY_PARAMETERS", "WEBHOOK_BODY", 
        "DINGTALK_WEBHOOK", "DINGTALK_SECRET", "DINGTALK_ENABLED",
        "PCURL_TO_MOBILE", "NOTIFY_AFTER_TASK_COMPLETE"
    ]
    
    settings = {}
    for key in notification_keys:
        if key.endswith("ENABLED") or key in ["PCURL_TO_MOBILE", "NOTIFY_AFTER_TASK_COMPLETE"]:
            settings[key] = get_bool_env_value(key)
        elif key in _NOTIFICATION_SECRET_KEYS:
            secret_value = get_env_value(key, "")
            settings[key] = ""
            settings[f"{key}_SET"] = bool(secret_value)
        else:
            settings[key] = get_env_value(key)
    
    return settings


@router.put("/api/settings/notifications")
async def update_notification_settings(settings: NotificationSettings, _user: dict = Depends(_require_notify_access)):
    """更新通知设置。"""
    if STORAGE_BACKEND() == "postgres":
        raise HTTPException(
            status_code=400,
            detail="服务器模式请使用用户级通知配置，不支持更新全局 .env 通知设置。"
        )

    try:
        settings_dict = settings.model_dump(exclude_none=True)
        settings_dict = _preserve_secret_on_empty(settings_dict, _NOTIFICATION_SECRET_KEYS)
        notification_keys = [
            "NTFY_TOPIC_URL", "NTFY_ENABLED", "GOTIFY_URL", "GOTIFY_TOKEN", "GOTIFY_ENABLED",
            "BARK_URL", "BARK_ENABLED", "WX_BOT_URL", "WX_BOT_ENABLED", "WX_CORP_ID", "WX_AGENT_ID",
            "WX_SECRET", "WX_TO_USER", "WX_APP_ENABLED", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
            "TELEGRAM_ENABLED", "WEBHOOK_URL", "WEBHOOK_ENABLED", "WEBHOOK_METHOD", "WEBHOOK_HEADERS",
            "WEBHOOK_CONTENT_TYPE", "WEBHOOK_QUERY_PARAMETERS", "WEBHOOK_BODY",
            "DINGTALK_WEBHOOK", "DINGTALK_SECRET", "DINGTALK_ENABLED",
            "PCURL_TO_MOBILE", "NOTIFY_AFTER_TASK_COMPLETE"
        ]
        
        save_env_settings(settings_dict, notification_keys)

        from src.notifier import config as notifier_config
        notifier_config.reload()

        from src.config import reload_config
        reload_config()

        return {"message": "通知设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新通知设置时出错: {e}")


@router.get("/api/settings/generic")
async def get_generic_settings(_user: dict = Depends(_require_settings_admin)):
    """获取通用设置。"""
    generic_keys = [
        "LOGIN_IS_EDGE", "RUN_HEADLESS", "AI_DEBUG_MODE",
        "ENABLE_THINKING", "ENABLE_RESPONSE_FORMAT", "AI_VISION_ENABLED",
        "SERVER_PORT", "WEB_USERNAME", "WEB_PASSWORD"
    ]
    
    settings = {}
    for key in generic_keys:
        if key in [
            "LOGIN_IS_EDGE",
            "RUN_HEADLESS",
            "AI_DEBUG_MODE",
            "ENABLE_THINKING",
            "ENABLE_RESPONSE_FORMAT",
            "AI_VISION_ENABLED",
        ]:
            settings[key] = get_bool_env_value(key)
        elif key == "SERVER_PORT":
            settings[key] = int(get_env_value(key, 8000))
        elif key in _GENERIC_SECRET_KEYS:
            secret_value = get_env_value(key, "")
            settings[key] = ""
            settings[f"{key}_SET"] = bool(secret_value)
        else:
            settings[key] = get_env_value(key)
    
    return settings


@router.put("/api/settings/generic")
async def update_generic_settings(settings: GenericSettings, _user: dict = Depends(_require_generic_settings_modify_admin)):
    """更新通用设置。"""
    try:
        settings_dict = settings.model_dump(exclude_none=True)
        settings_dict = _preserve_secret_on_empty(settings_dict, _GENERIC_SECRET_KEYS)
        generic_keys = [
            "LOGIN_IS_EDGE", "RUN_HEADLESS", "AI_DEBUG_MODE",
            "ENABLE_THINKING", "ENABLE_RESPONSE_FORMAT", "AI_VISION_ENABLED",
            "SERVER_PORT", "WEB_USERNAME", "WEB_PASSWORD"
        ]
        
        save_env_settings(settings_dict, generic_keys)

        from src.config import reload_config
        reload_config()

        return {"message": "通用设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新通用设置时出错: {e}")


@router.get("/api/settings/ai")
async def get_ai_settings(user: dict = Depends(_require_ai_or_tasks_access)):
    """获取AI模型设置。"""
    if STORAGE_BACKEND() == "postgres":
        user_id = _resolve_current_user_id(user)
        storage = get_storage()
        user_api_config = storage.get_default_api_config(user_id) or {}
        settings = _build_ai_settings_from_user_api_config(user_api_config)
        settings["IS_MULTI_USER_MODE"] = True
        settings["NEEDS_SETUP"] = not bool(
            settings.get("OPENAI_API_KEY_SET")
            and str(settings.get("OPENAI_BASE_URL") or "").strip()
            and str(settings.get("OPENAI_MODEL_NAME") or "").strip()
        )
        return settings

    ai_keys = [
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL_NAME",
        "PROXY_URL",
        "AI_MAX_TOKENS_PARAM_NAME",
        "AI_MAX_TOKENS_LIMIT",
    ]
    
    settings = {}
    for key in ai_keys:
        if key in _AI_SECRET_KEYS:
            secret_value = get_env_value(key, "")
            settings[key] = ""
            settings[f"{key}_SET"] = bool(secret_value)
        else:
            settings[key] = get_env_value(key)

    settings["IS_MULTI_USER_MODE"] = STORAGE_BACKEND() == "postgres"
    settings["NEEDS_SETUP"] = not bool(
        settings.get("OPENAI_API_KEY_SET")
        and str(settings.get("OPENAI_BASE_URL") or "").strip()
        and str(settings.get("OPENAI_MODEL_NAME") or "").strip()
    )
    return settings


@router.put("/api/settings/ai")
async def update_ai_settings(settings: dict, user: dict = Depends(_require_ai_access)):
    """更新AI模型设置。"""
    try:
        if STORAGE_BACKEND() == "postgres":
            user_id = _resolve_current_user_id(user)
            storage = get_storage()
            existing = storage.get_default_api_config(user_id) or {}

            existing_extra_config = existing.get("extra_config") if isinstance(existing.get("extra_config"), dict) else {}
            merged_extra_config = dict(existing_extra_config)

            for key in ["PROXY_URL", "AI_MAX_TOKENS_PARAM_NAME", "AI_MAX_TOKENS_LIMIT"]:
                if key in settings and settings.get(key) not in (None, ""):
                    if key == "AI_MAX_TOKENS_LIMIT":
                        try:
                            merged_extra_config[key] = int(settings.get(key))
                        except (TypeError, ValueError):
                            continue
                    else:
                        merged_extra_config[key] = settings.get(key)
                elif key in settings and settings.get(key) == "":
                    merged_extra_config.pop(key, None)

            raw_api_key = str(settings.get("OPENAI_API_KEY") or "").strip()
            final_api_key = raw_api_key or str(existing.get("api_key") or "").strip()
            final_base_url = str(
                (settings.get("OPENAI_BASE_URL") if "OPENAI_BASE_URL" in settings else existing.get("api_base_url")) or ""
            ).strip()
            final_model = str(
                (settings.get("OPENAI_MODEL_NAME") if "OPENAI_MODEL_NAME" in settings else existing.get("model")) or ""
            ).strip()

            if not final_base_url or not final_model:
                raise HTTPException(
                    status_code=400,
                    detail="当前用户AI配置不完整，请先配置 Base URL 和模型名称。"
                )

            payload = {
                "id": existing.get("id"),
                "provider": str(existing.get("provider") or "openai"),
                "name": str(existing.get("name") or "默认AI配置"),
                "api_base_url": final_base_url,
                "model": final_model,
                "extra_config": merged_extra_config,
                "is_default": True,
            }

            if final_api_key:
                payload["api_key"] = final_api_key

            saved_config = storage.save_user_api_config(user_id, payload)
            logger.info(
                "用户AI配置已保存到用户私有API配置",
                extra={
                    "event": "user_ai_settings_saved",
                    "user_id": user_id,
                    "config_id": saved_config.get("id"),
                }
            )
            invalidate_ai_health_snapshot(user)

            return {"message": "AI模型设置已成功更新并保存到当前用户配置。"}

        ai_keys = [
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL_NAME",
            "PROXY_URL",
            "AI_MAX_TOKENS_PARAM_NAME",
            "AI_MAX_TOKENS_LIMIT",
        ]
        merged_settings = _preserve_secret_on_empty(settings, _AI_SECRET_KEYS)
        save_env_settings(merged_settings, ai_keys)
        from src.config import reload_config
        reload_config()
        invalidate_ai_health_snapshot(user)
        return {"message": "AI模型设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新AI模型设置时出错: {e}")


@router.get("/api/settings/proxy")
async def get_proxy_settings(user: dict = Depends(_require_settings_admin)):
    """获取代理设置。"""
    if STORAGE_BACKEND() == "postgres":
        user_id = _resolve_current_user_id(user)
        storage = get_storage()
        user_api_config = storage.get_default_api_config(user_id) or {}
        extra_config = user_api_config.get("extra_config") if isinstance(user_api_config.get("extra_config"), dict) else {}
        settings = _build_proxy_settings_from_extra_config(extra_config)
        settings["IS_MULTI_USER_MODE"] = True
        return settings

    settings = {}
    for key in _PROXY_SETTING_KEYS:
        settings[key] = get_bool_env_value(key) if key in _PROXY_BOOL_KEYS else get_env_value(key, "")

    settings["IS_MULTI_USER_MODE"] = False
    return settings


@router.put("/api/settings/proxy")
async def update_proxy_settings(settings: dict, user: dict = Depends(_require_settings_admin)):
    """更新代理设置。"""
    try:
        if STORAGE_BACKEND() == "postgres":
            user_id = _resolve_current_user_id(user)
            storage = get_storage()
            existing = storage.get_default_api_config(user_id) or {}
            existing_extra_config = existing.get("extra_config") if isinstance(existing.get("extra_config"), dict) else {}
            merged_extra_config = dict(existing_extra_config)

            for key in _PROXY_SETTING_KEYS:
                if key not in settings:
                    continue
                if key in _PROXY_BOOL_KEYS:
                    merged_extra_config[key] = _to_bool_value(settings.get(key), default=False)
                else:
                    merged_extra_config[key] = str(settings.get(key) or "").strip()

            payload = {
                "id": existing.get("id"),
                "provider": str(existing.get("provider") or "openai"),
                "name": str(existing.get("name") or "默认AI配置"),
                "api_base_url": str(existing.get("api_base_url") or "").strip(),
                "model": str(existing.get("model") or "").strip(),
                "extra_config": merged_extra_config,
                "is_default": True,
            }
            if existing.get("api_key"):
                payload["api_key"] = str(existing.get("api_key")).strip()

            saved = storage.save_user_api_config(user_id, payload)
            logger.info(
                "用户代理设置已保存",
                extra={
                    "event": "user_proxy_settings_saved",
                    "user_id": user_id,
                    "config_id": saved.get("id"),
                }
            )
            invalidate_ai_health_snapshot(user)
            return {"message": "代理设置已成功更新并保存到当前用户配置。"}

        save_env_settings(settings, _PROXY_SETTING_KEYS)

        # 代理配置会影响AI与通知渠道，两侧都需要重新加载
        from src.config import reload_config
        reload_config()

        from src.notifier import config as notifier_config
        notifier_config.reload()
        invalidate_ai_health_snapshot(user)

        return {"message": "代理设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新代理设置时出错: {e}")


@router.post("/api/settings/ai-proxy/migrate")
async def migrate_ai_proxy_settings_to_user(user: dict = Depends(_require_ai_access)):
    """将全局 .env 的 AI + 代理设置一键迁移到当前用户。"""
    if STORAGE_BACKEND() != "postgres":
        raise HTTPException(status_code=400, detail="仅服务器模式支持一键迁移到用户配置。")
    user_id = _resolve_current_user_id(user)
    return _migrate_env_ai_proxy_settings_to_user(user_id)


def _migrate_env_ai_proxy_settings_to_user(user_id: str) -> dict:
    """将全局 .env 的 AI + 代理配置迁移到指定用户。"""
    if STORAGE_BACKEND() != "postgres":
        raise RuntimeError("当前不是 PostgreSQL 多用户模式，无法迁移用户私有 AI/代理配置。")
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("缺少用户标识，无法迁移 AI/代理配置。")

    storage = get_storage()
    existing = storage.get_default_api_config(normalized_user_id) or {}
    existing_extra_config = existing.get("extra_config") if isinstance(existing.get("extra_config"), dict) else {}
    migrated_extra_config = dict(existing_extra_config)

    for key in _PROXY_SETTING_KEYS:
        if key in _PROXY_BOOL_KEYS:
            migrated_extra_config[key] = get_bool_env_value(key)
        else:
            migrated_extra_config[key] = get_env_value(key, "")

    tokens_param_name = str(get_env_value("AI_MAX_TOKENS_PARAM_NAME", "") or "").strip()
    tokens_limit_raw = str(get_env_value("AI_MAX_TOKENS_LIMIT", "") or "").strip()
    if tokens_param_name:
        migrated_extra_config["AI_MAX_TOKENS_PARAM_NAME"] = tokens_param_name
    if tokens_limit_raw:
        try:
            migrated_extra_config["AI_MAX_TOKENS_LIMIT"] = int(tokens_limit_raw)
        except ValueError:
            logger.warning(
                "全局AI_MAX_TOKENS_LIMIT格式无效，迁移时已忽略",
                extra={"event": "ai_proxy_migrate_invalid_tokens_limit", "user_id": normalized_user_id}
            )

    env_api_key = str(get_env_value("OPENAI_API_KEY", "") or "").strip()
    env_base_url = str(get_env_value("OPENAI_BASE_URL", "") or "").strip()
    env_model_name = str(get_env_value("OPENAI_MODEL_NAME", "") or "").strip()

    payload = {
        "id": existing.get("id"),
        "provider": str(existing.get("provider") or "openai"),
        "name": str(existing.get("name") or "默认AI配置"),
        "api_base_url": env_base_url or str(existing.get("api_base_url") or "").strip(),
        "model": env_model_name or str(existing.get("model") or "").strip(),
        "extra_config": migrated_extra_config,
        "is_default": True,
    }

    if env_api_key:
        payload["api_key"] = env_api_key
    elif existing.get("api_key"):
        payload["api_key"] = str(existing.get("api_key")).strip()

    saved = storage.save_user_api_config(normalized_user_id, payload)
    latest_config = storage.get_default_api_config(normalized_user_id) or saved
    ai_settings = _build_ai_settings_from_user_api_config(latest_config)
    proxy_settings = _build_proxy_settings_from_extra_config(
        latest_config.get("extra_config") if isinstance(latest_config.get("extra_config"), dict) else {}
    )
    ai_settings["IS_MULTI_USER_MODE"] = True
    proxy_settings["IS_MULTI_USER_MODE"] = True

    logger.info(
        "全局AI与代理配置已迁移到用户配置",
        extra={
            "event": "user_ai_proxy_migrated",
            "user_id": normalized_user_id,
            "config_id": latest_config.get("id"),
        }
    )

    return {
        "message": "已将全局AI与代理设置迁移到当前用户配置。",
        "user_id": normalized_user_id,
        "config_id": latest_config.get("id"),
        "ai_settings": ai_settings,
        "proxy_settings": proxy_settings,
    }


def _resolve_migration_target_user_id(user: dict, owner_username: str = "") -> str:
    """解析迁移后用于承接 AI/代理私有配置的目标用户 ID。"""
    storage = get_storage()

    current_user_id = str((user or {}).get("user_id") or (user or {}).get("id") or "").strip()
    if current_user_id:
        found_by_id = storage.get_user_by_id(current_user_id)
        if found_by_id and str(found_by_id.get("id") or "").strip():
            return str(found_by_id.get("id")).strip()

    candidate_usernames = [
        str((user or {}).get("username") or "").strip(),
        str(owner_username or "").strip(),
        str(WEB_USERNAME() or "").strip(),
    ]
    for username in candidate_usernames:
        if not username:
            continue
        matched = storage.get_user_by_username(username)
        if matched and str(matched.get("id") or "").strip():
            return str(matched.get("id")).strip()

    return ""


# ============== 数据库设置 API ==============

def _parse_database_url(url: str) -> dict:
    """解析 DATABASE_URL 为各个字段"""
    default_result = {"host": "", "port": "5432", "database": "", "username": "", "password": ""}
    if not url:
        return default_result

    url = normalize_database_url(url)

    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme.lower().startswith("postgres"):
            return default_result

        db_name = (parsed_url.path or "").lstrip("/")
        return {
            "host": parsed_url.hostname or "",
            "port": str(parsed_url.port or 5432),
            "database": unquote(db_name),
            "username": unquote(parsed_url.username or ""),
            "password": unquote(parsed_url.password or "")
        }
    except Exception:
        return default_result


def _normalize_db_host(host: str) -> str:
    """规范化数据库主机，清理协议与路径"""
    host = (host or "").strip()
    if not host:
        return ""
    if "://" in host:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(host)
            if parsed.hostname:
                return parsed.hostname
        except Exception:
            pass
        host = host.split("://", 1)[-1]
    host = host.split("/", 1)[0]
    return host


def _split_host_and_port(host: str, port: str) -> tuple:
    """从主机字段中提取主机与端口，兼容 http(s):// 与 host:port"""
    host = (host or "").strip()
    port = (port or "").strip() or "5432"
    if not host:
        return "", port

    if "://" in host:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(host)
            if parsed.hostname:
                host = parsed.hostname
                if parsed.port:
                    port = str(parsed.port)
            else:
                host = host.split("://", 1)[-1]
        except Exception:
            host = host.split("://", 1)[-1]

    host = host.split("/", 1)[0]

    if ":" in host and host.count(":") == 1 and not host.startswith("["):
        host_part, port_part = host.split(":", 1)
        if port_part.isdigit():
            port = port_part
            host = host_part

    host = _normalize_db_host(host)
    return host, port


def _build_database_url(host: str, port: str, database: str, username: str, password: str) -> str:
    """构建 DATABASE_URL"""
    database = (database or "").strip().lstrip("/")
    username = (username or "").strip()
    password = "" if password is None else str(password)

    host, port = _split_host_and_port(host, port)
    if not host or not database:
        return ""

    encoded_database = quote(database, safe="")
    encoded_username = quote(username, safe="") if username else ""
    encoded_password = quote(password, safe="") if password else ""

    if encoded_username and password:
        return f"postgresql://{encoded_username}:{encoded_password}@{host}:{port}/{encoded_database}"
    elif encoded_username:
        return f"postgresql://{encoded_username}@{host}:{port}/{encoded_database}"
    else:
        return f"postgresql://{host}:{port}/{encoded_database}"

def _format_pg_version(version: str) -> str:
    """格式化 PostgreSQL 版本信息，降低用户阅读门槛"""
    if not version:
        return ""
    import re
    match = re.search(r"PostgreSQL\s+([0-9.]+)\s+on\s+([^,]+)(?:,.*?(64-bit|32-bit))?", version)
    if match:
        ver = match.group(1)
        platform = match.group(2) or ""
        bits = match.group(3) or ""
        bits_cn = "64位" if bits == "64-bit" else "32位" if bits == "32-bit" else ""
        extras = "，".join([part for part in [platform, bits_cn] if part])
        return f"PostgreSQL {ver}（{extras}）" if extras else f"PostgreSQL {ver}"
    return "PostgreSQL 服务已响应"


def _map_db_error_message(error_text: str) -> str:
    """将常见数据库错误映射为中文提示"""
    raw_text = (error_text or "").strip()
    lower_text = raw_text.lower()
    if "background on this error at" in lower_text:
        raw_text = raw_text.split("Background on this error at:", 1)[0].strip()
        lower_text = raw_text.lower()
    if "sqlalchemy.exc" in lower_text:
        raw_text = raw_text.split(") ", 1)[-1].strip()
        lower_text = raw_text.lower()
    text = lower_text
    if "password authentication failed" in text:
        return "用户名或密码错误"
    if "authentication failed" in text:
        return "认证失败，请检查用户名和密码"
    if "database" in text and "does not exist" in text:
        return "数据库不存在"
    if "role" in text and "does not exist" in text:
        return "用户名不存在"
    if "could not translate host name" in text or "name or service not known" in text or "getaddrinfo failed" in text:
        return "主机地址无法解析"
    if "connection refused" in text:
        return "连接被拒绝（端口未开放或服务未启动）"
    if "timeout" in text or "timed out" in text:
        return "连接超时（请检查网络或防火墙）"
    if "no password supplied" in text:
        return "未提供密码"
    if "ssl" in text and "required" in text:
        return "连接需要 SSL，请检查数据库 SSL 配置"
    if "remaining connection slots are reserved" in text:
        return "连接数已满，请稍后重试"
    if "could not connect" in text or "connection failed" in text:
        return "无法连接数据库，请检查地址、端口和网络"
    return "连接失败，请检查连接信息"


def _backend_to_label(backend: str) -> str:
    """将后端标识转换为可读文案"""
    backend = (backend or "").lower()
    if backend == "postgres":
        return "PostgreSQL（多用户）"
    if backend == "local":
        return "本地文件（单用户）"
    return "未知模式"


def _probe_database_connection(database_url: str, timeout_seconds: int = 3) -> dict:
    """探测 PostgreSQL 连接状态"""
    normalized_url = normalize_database_url(database_url)
    if not normalized_url:
        return {
            "configured": False,
            "connected": None,
            "level": "warning",
            "label": "数据库未配置",
            "message": "请先在系统设置中配置 DATABASE_URL",
            "version": ""
        }

    engine = None
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(
            normalized_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": timeout_seconds}
        )
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
        return {
            "configured": True,
            "connected": True,
            "level": "ok",
            "label": "数据库连接正常",
            "message": "PostgreSQL 可用",
            "version": _format_pg_version(version)
        }
    except Exception as exc:
        logger.warning(f"[数据库状态] 连接探测失败: {exc}")
        return {
            "configured": True,
            "connected": False,
            "level": "error",
            "label": "数据库连接失败",
            "message": _map_db_error_message(str(exc)),
            "version": ""
        }
    finally:
        if engine is not None:
            engine.dispose()


def _get_missing_postgres_tables(conn) -> list:
    """检查 PostgreSQL 中缺失的核心表。"""
    from sqlalchemy import text

    result = conn.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
    """))
    existing_tables = {row[0] for row in result}
    return [table_name for table_name in REQUIRED_POSTGRES_TABLES if table_name not in existing_tables]


def _get_storage_runtime_status() -> dict:
    """获取配置后端、运行后端与数据库连接的综合状态"""
    configured_backend = (STORAGE_BACKEND() or "local").lower()
    runtime_backend = "unknown"
    runtime_storage_class = ""
    runtime_error = ""

    try:
        storage = get_storage()
        runtime_storage_class = storage.__class__.__name__
        if runtime_storage_class == "PostgresAdapter":
            runtime_backend = "postgres"
        elif runtime_storage_class == "LocalStorageAdapter":
            runtime_backend = "local"
        else:
            runtime_backend = configured_backend
    except Exception as exc:
        runtime_error = str(exc)
        logger.warning(f"[存储状态] 获取运行时存储实例失败: {exc}")
        runtime_backend = configured_backend if configured_backend in ("local", "postgres") else "unknown"

    db_probe = _probe_database_connection(DATABASE_URL(), timeout_seconds=3)
    runtime_uses_database = runtime_backend == "postgres"
    mode_consistent = runtime_backend == configured_backend

    if runtime_uses_database:
        db_label = db_probe["label"]
        db_message = db_probe["message"]
        db_level = db_probe["level"]
    elif db_probe["configured"] and db_probe["connected"] is True:
        db_label = "数据库可连接（当前未启用）"
        db_message = "数据库配置有效，但当前运行模式未使用 PostgreSQL"
        db_level = "info"
    elif db_probe["configured"] and db_probe["connected"] is False:
        db_label = "数据库连接失败（当前未启用）"
        db_message = db_probe["message"]
        db_level = "warning"
    else:
        db_label = "数据库未启用"
        db_message = "当前运行模式无需数据库连接"
        db_level = "info"

    return {
        "configured_backend": configured_backend,
        "configured_backend_label": _backend_to_label(configured_backend),
        "runtime_backend": runtime_backend,
        "runtime_backend_label": _backend_to_label(runtime_backend),
        "mode_consistent": mode_consistent,
        "runtime_storage_class": runtime_storage_class,
        "runtime_error": runtime_error,
        "database": {
            "runtime_uses_database": runtime_uses_database,
            "configured": db_probe["configured"],
            "connected": db_probe["connected"],
            "level": db_level,
            "label": db_label,
            "message": db_message,
            "version": db_probe["version"]
        }
    }


@router.get("/api/settings/database")
async def get_database_settings(_user: dict = Depends(_require_settings_admin)):
    """获取数据库配置（不返回密码）。"""
    storage_backend = STORAGE_BACKEND()
    database_url = DATABASE_URL()
    encryption_key = get_env_value("ENCRYPTION_MASTER_KEY", "")
    storage_runtime = _get_storage_runtime_status()
    
    parsed = _parse_database_url(database_url)
    
    return {
        "STORAGE_BACKEND": storage_backend,
        "CONFIGURED_BACKEND": storage_runtime["configured_backend"],
        "CONFIGURED_BACKEND_LABEL": storage_runtime["configured_backend_label"],
        "RUNTIME_BACKEND": storage_runtime["runtime_backend"],
        "RUNTIME_BACKEND_LABEL": storage_runtime["runtime_backend_label"],
        "BACKEND_CONSISTENT": storage_runtime["mode_consistent"],
        "RUNTIME_STORAGE_CLASS": storage_runtime["runtime_storage_class"],
        "RUNTIME_ERROR": storage_runtime["runtime_error"],
        "DB_STATUS": storage_runtime["database"],
        "DB_STATUS_LABEL": storage_runtime["database"]["label"],
        "DB_STATUS_LEVEL": storage_runtime["database"]["level"],
        "DB_STATUS_MESSAGE": storage_runtime["database"]["message"],
        "DB_STATUS_VERSION": storage_runtime["database"]["version"],
        "DB_HOST": parsed["host"],
        "DB_PORT": parsed["port"],
        "DB_NAME": parsed["database"],
        "DB_USER": parsed["username"],
        # 不返回密码，仅指示是否已设置
        "DB_PASSWORD_SET": bool(parsed["password"]),
        "ENCRYPTION_MASTER_KEY_SET": bool(encryption_key),
        "ENCRYPTION_KEY_DEFAULT": encryption_key == "change-this-in-production"
    }


@router.put("/api/settings/database")
async def update_database_settings(settings: dict, _user: dict = Depends(_require_settings_admin)):
    """保存数据库连接配置（不切换模式）。"""
    try:
        # 构建 DATABASE_URL（仅保存连接信息，不切换模式）
        db_host = (settings.get("DB_HOST") or "").strip()
        db_port = (settings.get("DB_PORT") or "").strip()
        db_name = (settings.get("DB_NAME") or "").strip()
        db_user = (settings.get("DB_USER") or "").strip()
        db_password = settings.get("DB_PASSWORD")

        # 兜底使用现有配置，避免前端字段缺失时误覆盖为空
        existing_url = get_env_value("DATABASE_URL", "")
        existing_parsed = _parse_database_url(existing_url) if existing_url else {}

        if not db_host:
            db_host = existing_parsed.get("host", "")
        if not db_port:
            db_port = existing_parsed.get("port", "5432") or "5432"
        if not db_name:
            db_name = existing_parsed.get("database", "")
        if not db_user:
            db_user = existing_parsed.get("username", "")
        if not db_password:
            db_password = existing_parsed.get("password", "")

        if not db_host or not db_name:
            raise HTTPException(
                status_code=400,
                detail="请填写主机地址和数据库名后再保存。已保留原有数据库配置。"
            )
        
        # 构建并验证连接
        database_url = _build_database_url(db_host, db_port, db_name, db_user, db_password)
        database_url = normalize_database_url(database_url)
        
        # 如果填写了连接信息，验证连接是否有效
        db_ready = False
        missing_tables = []
        if database_url:
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(
                    database_url, 
                    pool_pre_ping=True, 
                    connect_args={"connect_timeout": 10}
                )
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    missing_tables = _get_missing_postgres_tables(conn)
                    db_ready = len(missing_tables) == 0
                engine.dispose()
            except Exception as conn_err:
                logger.warning(f"[数据库配置] 连接验证失败: {conn_err}")
                error_message = _map_db_error_message(str(conn_err))
                raise HTTPException(
                    status_code=400,
                    detail=f"PostgreSQL 连接验证失败，配置未保存。原因：{error_message}"
                )
        
        # 只保存连接信息，不修改 STORAGE_BACKEND
        env_settings = {
            "DATABASE_URL": database_url,
        }
        
        # 如果提供了加密密钥，也保存
        if settings.get("ENCRYPTION_MASTER_KEY"):
            env_settings["ENCRYPTION_MASTER_KEY"] = settings["ENCRYPTION_MASTER_KEY"]
        
        save_env_settings(env_settings, list(env_settings.keys()))
        
        from src.config import reload_config
        reload_config()
        _reset_storage_runtime_caches()
        
        # 返回数据库状态
        return {
            "message": "PostgreSQL 连接配置已保存。",
            "db_ready": db_ready,
            "need_migration": not db_ready,
            "missing_tables": missing_tables
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存数据库配置时出错: {e}")


@router.post("/api/settings/database/enable")
async def enable_postgres_mode(_user: dict = Depends(_require_settings_admin)):
    """开启 PostgreSQL 模式（需要先完成迁移）。"""
    logger.info("[数据库模式] 收到开启 PostgreSQL 模式请求")
    try:
        database_url = normalize_database_url(get_env_value("DATABASE_URL", ""))
        
        if not database_url:
            logger.warning("[数据库模式] 失败：DATABASE_URL 未配置")
            raise HTTPException(
                status_code=400,
                detail="请先配置并保存 PostgreSQL 连接信息"
            )
        
        logger.info("[数据库模式] 验证数据库连接和表结构...")
        # 验证连接和表是否初始化
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(
                database_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 10}
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                missing_tables = _get_missing_postgres_tables(conn)
            engine.dispose()

            if missing_tables:
                logger.warning(f"[数据库模式] 检测到缺失表，尝试自动补齐: {missing_tables}")
                from src.storage.postgres_adapter import PostgresAdapter
                PostgresAdapter(database_url).create_tables()

                engine = create_engine(
                    database_url,
                    pool_pre_ping=True,
                    connect_args={"connect_timeout": 10}
                )
                with engine.connect() as conn:
                    missing_tables = _get_missing_postgres_tables(conn)
                engine.dispose()

            if missing_tables:
                logger.warning(f"[数据库模式] 缺失表补齐失败: {missing_tables}")
                raise HTTPException(
                    status_code=400,
                    detail=f"数据库缺少核心表：{missing_tables}。请先执行「数据迁移」初始化数据库结构。"
                )

            engine = create_engine(
                database_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 10}
            )
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
            engine.dispose()
            logger.info(f"[数据库模式] 验证通过，核心表齐全，共 {user_count} 个用户")
        except HTTPException:
            raise
        except Exception as conn_err:
            logger.error(f"[数据库模式] 连接失败: {conn_err}")
            error_message = _map_db_error_message(str(conn_err))
            raise HTTPException(
                status_code=400,
                detail=f"PostgreSQL 连接失败：{error_message}"
            )
        
        # 验证通过，切换模式
        logger.info("[数据库模式] 正在切换 STORAGE_BACKEND 为 postgres...")
        save_env_settings({"STORAGE_BACKEND": "postgres"}, ["STORAGE_BACKEND"])
        
        from src.config import reload_config
        reload_config()
        _reset_storage_runtime_caches()
        
        logger.info(f"[数据库模式] ✅ 成功开启 PostgreSQL 模式！用户数: {user_count}")
        return {
            "message": f"已成功开启 PostgreSQL 模式（当前 {user_count} 个用户），切换已即时生效。",
            "success": True,
            "user_count": user_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[数据库模式] 异常: {e}")
        raise HTTPException(status_code=500, detail=f"开启数据库模式时出错: {e}")


@router.post("/api/settings/database/disable")
async def disable_postgres_mode(_user: dict = Depends(_require_settings_admin)):
    """关闭 PostgreSQL 模式，切换回本地文件存储。"""
    logger.info("[数据库模式] 收到关闭 PostgreSQL 模式请求")
    try:
        current_backend = (STORAGE_BACKEND() or "local").lower()

        if current_backend != "postgres":
            logger.info(f"[数据库模式] 当前已是本地模式: {current_backend}")
            return {
                "message": "当前已经是本地文件存储模式。",
                "success": True
            }

        logger.info("[数据库模式] 正在切换 STORAGE_BACKEND 为 local...")
        save_env_settings({"STORAGE_BACKEND": "local"}, ["STORAGE_BACKEND"])

        from src.config import reload_config
        reload_config()
        _reset_storage_runtime_caches()

        logger.info("[数据库模式] ✅ 成功切换到本地文件存储模式")
        return {
            "message": "已成功切换到本地文件存储模式，切换已即时生效。",
            "success": True
        }
    except Exception as e:
        logger.error(f"[数据库模式] 异常: {e}")
        raise HTTPException(status_code=500, detail=f"关闭数据库模式时出错: {e}")


@router.post("/api/settings/database/test")
async def test_database_connection(settings: dict = None, _user: dict = Depends(_require_settings_admin)):
    """测试数据库连接。"""
    try:
        # 使用传入的设置或从环境变量读取
        if settings:
            db_host = (settings.get("DB_HOST") or "").strip()
            db_port = (settings.get("DB_PORT") or "").strip()
            db_name = (settings.get("DB_NAME") or "").strip()
            db_user = (settings.get("DB_USER") or "").strip()
            db_password = settings.get("DB_PASSWORD", "")

            existing_url = get_env_value("DATABASE_URL", "")
            if existing_url:
                parsed = _parse_database_url(existing_url)
                if not db_host:
                    db_host = parsed.get("host", "")
                if not db_port:
                    db_port = parsed.get("port", "5432") or "5432"
                if not db_name:
                    db_name = parsed.get("database", "")
                if not db_user:
                    db_user = parsed.get("username", "")
                if not db_password:
                    db_password = parsed.get("password", "")
            database_url = _build_database_url(db_host, db_port, db_name, db_user, db_password)
        else:
            database_url = get_env_value("DATABASE_URL", "")
        
        database_url = normalize_database_url(database_url)
        
        if not database_url:
            return {
                "success": False,
                "message": "数据库连接URL未配置"
            }
        
        # 尝试连接数据库
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
        
        engine.dispose()
        
        return {
            "success": True,
            "message": "连接成功",
            "version": _format_pg_version(version)
        }
    except Exception as e:
        logger.warning(f"[数据库测试] 连接失败: {e}")
        error_message = _map_db_error_message(str(e))
        return {
            "success": False,
            "message": f"连接失败：{error_message}"
        }


@router.get("/api/settings/database/migration-scope")
async def get_database_migration_scope(_user: dict = Depends(_require_settings_admin)):
    """获取数据迁移覆盖范围说明（会迁移 / 不会迁移）。"""
    try:
        from src.storage.migration import DataMigrator
        return {
            "success": True,
            "scope": DataMigrator.get_migration_scope()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取迁移范围失败: {str(e)}")


@router.post("/api/settings/database/migrate")
async def run_database_migration(options: dict = None, _user: dict = Depends(_require_settings_admin)):
    """执行数据迁移。"""
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        
        database_url = normalize_database_url(get_env_value("DATABASE_URL", ""))
        if not database_url:
            raise HTTPException(status_code=400, detail="数据库连接URL未配置，请先配置并测试连接")
        
        dry_run = options.get("dry_run", False) if options else False
        # 正式迁移默认自动切换到 PostgreSQL 模式（可通过 auto_enable_mode 显式关闭）
        auto_enable_mode = options.get("auto_enable_mode", not dry_run) if options else (not dry_run)
        include_ai_proxy_migration = _to_bool_value(
            options.get("include_ai_proxy_migration", not dry_run) if options else (not dry_run),
            default=(not dry_run)
        )
        owner_username = options.get("owner_username") if options else None
        owner_password = options.get("owner_password") if options else None
        if not owner_username and options:
            owner_username = options.get("admin_username")
        if not owner_password and options:
            owner_password = options.get("admin_password")
        if not owner_username:
            owner_username = WEB_USERNAME()
        if not owner_password:
            owner_password = WEB_PASSWORD()
        
        from src.storage.migration import DataMigrator
        
        migrator = DataMigrator(
            database_url=database_url,
            dry_run=dry_run,
            verbose=True
        )
        
        stats = migrator.run_full_migration(owner_username, owner_password)
        scope = DataMigrator.get_migration_scope()
        
        mode_text = "测试迁移" if dry_run else "正式迁移"

        mode_switched = False
        mode_switch_message = ""
        if (not dry_run) and auto_enable_mode:
            try:
                save_env_settings({"STORAGE_BACKEND": "postgres"}, ["STORAGE_BACKEND"])
                from src.config import reload_config
                reload_config()
                _reset_storage_runtime_caches()
                mode_switched = True
                mode_switch_message = "已自动切换为 PostgreSQL 模式，切换已即时生效。"
            except Exception as switch_err:
                logger.warning(f"[数据库迁移] 自动切换 PostgreSQL 模式失败: {switch_err}")
                mode_switch_message = f"数据迁移成功，但自动切换模式失败：{switch_err}。请手动点击“开启 PostgreSQL 模式”。"

        ai_proxy_migration_result = {
            "enabled": bool(include_ai_proxy_migration and (not dry_run)),
            "success": False,
            "message": "",
            "user_id": "",
        }
        if include_ai_proxy_migration and (not dry_run):
            try:
                if STORAGE_BACKEND() != "postgres":
                    raise RuntimeError("当前未切换到 PostgreSQL 模式，已跳过 AI/代理配置迁移。")

                target_user_id = _resolve_migration_target_user_id(_user, owner_username)
                if not target_user_id:
                    raise RuntimeError("未找到可用的目标用户，已跳过 AI/代理配置迁移。")

                ai_proxy_result = _migrate_env_ai_proxy_settings_to_user(target_user_id)
                ai_proxy_migration_result["success"] = True
                ai_proxy_migration_result["message"] = ai_proxy_result.get("message") or "AI/代理配置迁移完成。"
                ai_proxy_migration_result["user_id"] = str(ai_proxy_result.get("user_id") or target_user_id)
            except Exception as ai_proxy_error:
                error_message = str(ai_proxy_error)
                ai_proxy_migration_result["message"] = f"AI/代理配置迁移失败：{error_message}"
                logger.warning(
                    "数据库迁移后自动迁移 AI/代理配置失败",
                    extra={
                        "event": "database_migration_ai_proxy_failed",
                        "error": error_message,
                    }
                )

        return {
            "success": True,
            "message": f"{mode_text}完成",
            "dry_run": dry_run,
            "stats": stats,
            "migration_owner_username": owner_username,
            "scope": scope,
            "auto_enable_mode": bool(auto_enable_mode),
            "mode_switched": mode_switched,
            "mode_switch_message": mode_switch_message,
            "ai_proxy_migration": ai_proxy_migration_result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据迁移失败: {str(e)}")



