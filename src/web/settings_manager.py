import os
import aiofiles
import json
from fastapi import APIRouter, HTTPException
from src.web.models import NotificationSettings, GenericSettings, NewPromptRequest, PromptUpdate, LoginStateUpdate, BayesUpdate
from src.config import get_env_value, get_bool_env_value, save_env_settings


router = APIRouter()


@router.get("/api/settings/status")
async def get_system_status():
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
            print(f"检测到任务进程 {process.pid} (ID: {task_id}) 已结束，返回码: {process.returncode}。")
            del fetcher_processes[task_id]
            from src.web.task_manager import update_task_running_status
            import asyncio
            asyncio.create_task(update_task_running_status(task_id, False))
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
            "openai_api_key_set": bool(API_KEY()),
            "openai_base_url_set": bool(BASE_URL()),
            "openai_model_name_set": bool(MODEL_NAME()),
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
        }
    }
    return status


@router.get("/api/prompts")
async def list_prompts():
    """列出 prompts/ 目录下的所有 .txt 文件。"""
    PROMPTS_DIR = "prompts"
    if not os.path.isdir(PROMPTS_DIR):
        return []
    return [f for f in os.listdir(PROMPTS_DIR) if f.endswith(".txt")]


@router.post("/api/prompts")
async def create_new_prompt(new_prompt: NewPromptRequest):
    """创建一个新的 prompt 文件。"""
    PROMPTS_DIR = "prompts"
    if "/" in new_prompt.filename or ".." in new_prompt.filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    if not new_prompt.filename.endswith(".txt"):
        new_prompt.filename += ".txt"

    filepath = os.path.join(PROMPTS_DIR, new_prompt.filename)

    if os.path.exists(filepath):
        raise HTTPException(status_code=400, detail="该文件名已存在。")

    try:
        os.makedirs(PROMPTS_DIR, exist_ok=True)
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(new_prompt.content)
        return {"message": f"Prompt 文件 '{new_prompt.filename}' 创建成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Prompt 文件时出错: {e}")


@router.get("/api/prompts/{filename}")
async def get_prompt_content(filename: str):
    """获取指定 prompt 文件的内容。"""
    PROMPTS_DIR = "prompts"
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    filepath = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": filename, "content": content}


@router.get("/api/criteria")
async def list_criteria_files():
    """列出 criteria/ 目录下的所有 .txt 文件。"""
    CRITERIA_DIR = "criteria"
    if not os.path.isdir(CRITERIA_DIR):
        return []
    return [f for f in os.listdir(CRITERIA_DIR) if f.endswith(".txt")]


@router.get("/api/criteria/{filename}")
async def get_criteria_content(filename: str):
    """获取指定 criteria 文件的内容。"""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    requirement_path = os.path.join("requirement", filename)
    if os.path.exists(requirement_path):
        async with aiofiles.open(requirement_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        return {"filename": filename, "content": content}

    filepath = os.path.join("criteria", filename)
    if not os.path.exists(filepath):
        print(f"DEBUG: Criteria file not found at: {filepath} or {requirement_path}")
        raise HTTPException(status_code=404, detail="Criteria 文件未找到。")

    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": filename, "content": content}


@router.put("/api/criteria/{filename}")
async def update_criteria_content(filename: str, prompt_update: PromptUpdate):
    """更新指定 criteria 文件的内容。"""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    requirement_path = os.path.join("requirement", filename)
    if os.path.exists(requirement_path):
        try:
            async with aiofiles.open(requirement_path, 'w', encoding='utf-8') as f:
                await f.write(prompt_update.content)
            return {"message": f"Requirement 文件 '{filename}' 更新成功。"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入 Requirement 文件时出错: {e}")

    filepath = os.path.join("criteria", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Criteria 文件未找到。")

    try:
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(prompt_update.content)
        return {"message": f"Criteria 文件 '{filename}' 更新成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Criteria 文件时出错: {e}")


@router.put("/api/prompts/{filename}")
async def update_prompt_content(filename: str, prompt_update: PromptUpdate):
    """更新指定 prompt 文件的内容。"""
    PROMPTS_DIR = "prompts"
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    filepath = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    try:
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(prompt_update.content)
        return {"message": f"Prompt 文件 '{filename}' 更新成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Prompt 文件时出错: {e}")


@router.get("/api/bayes")
async def list_bayes_profiles():
    """列出 prompts/bayes/ 目录下的所有 .json 文件。"""
    BAYES_DIR = os.path.join("prompts", "bayes")
    if not os.path.isdir(BAYES_DIR):
        return []
    return [f for f in os.listdir(BAYES_DIR) if f.endswith(".json")]


@router.post("/api/bayes")
async def create_bayes_profile(new_profile: NewPromptRequest):
    """创建一个新的 Bayes 参数文件。"""
    BAYES_DIR = os.path.join("prompts", "bayes")
    if "/" in new_profile.filename or ".." in new_profile.filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    if not new_profile.filename.endswith(".json"):
        new_profile.filename += ".json"

    filepath = os.path.join(BAYES_DIR, new_profile.filename)
    if os.path.exists(filepath):
        raise HTTPException(status_code=400, detail="该文件名已存在。")

    try:
        os.makedirs(BAYES_DIR, exist_ok=True)
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(new_profile.content)
        return {"message": f"Bayes 文件 '{new_profile.filename}' 创建成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Bayes 文件时出错: {e}")


@router.get("/api/bayes/{filename}")
async def get_bayes_profile(filename: str):
    """获取指定 Bayes 参数文件的内容。"""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    BAYES_DIR = os.path.join("prompts", "bayes")
    filepath = os.path.join(BAYES_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Bayes 文件未找到。")

    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": filename, "content": content}


@router.put("/api/bayes/{filename}")
async def update_bayes_profile(filename: str, bayes_update: BayesUpdate):
    """更新指定 Bayes 参数文件的内容。"""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    BAYES_DIR = os.path.join("prompts", "bayes")
    filepath = os.path.join(BAYES_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Bayes 文件未找到。")

    try:
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(bayes_update.content)
        return {"message": f"Bayes 文件 '{filename}' 更新成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Bayes 文件时出错: {e}")


@router.delete("/api/bayes/{filename}")
async def delete_bayes_profile(filename: str):
    """删除指定的 Bayes 参数文件。"""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    BAYES_DIR = os.path.join("prompts", "bayes")
    filepath = os.path.join(BAYES_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Bayes 文件未找到。")

    try:
        os.remove(filepath)
        return {"message": f"Bayes 文件 '{filename}' 删除成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Bayes 文件时出错: {e}")



@router.get("/api/guides/bayes")
async def get_bayes_guide():
    """??Bayes??????????"""
    guide_path = os.path.join("prompts", "guide", "bayes_guide.md")
    if not os.path.exists(guide_path):
        raise HTTPException(status_code=404, detail="Bayes????????")
    async with aiofiles.open(guide_path, 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": "bayes_guide.md", "content": content}

@router.delete("/api/prompts/{filename}")
async def delete_prompt(filename: str):
    """删除指定的 prompt 文件。"""
    PROMPTS_DIR = "prompts"
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    filepath = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    try:
        os.remove(filepath)
        return {"message": f"Prompt 文件 '{filename}' 删除成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Prompt 文件时出错: {e}")


async def _cleanup_login_process(process):
    """清理登录进程的后台任务"""
    await process.wait()
    from src.web.main import login_process
    login_process = None
    print(f"自动登录程序 (PID: {process.pid}) 已结束。")


@router.post("/api/manual-login")
async def start_manual_login():
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

        print(f"自动登录程序已启动，PID: {process.pid}")

        asyncio.create_task(_cleanup_login_process(process))

        return {"message": "自动登录程序已成功启动，请在服务器上查看浏览器窗口并完成登录。"}
    except Exception as e:
        login_process = None
        raise HTTPException(status_code=500, detail=f"启动自动登录程序时出错: {str(e)}")


@router.get("/api/settings/notifications")
async def get_notification_settings():
    """获取通知设置。"""
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
        else:
            settings[key] = get_env_value(key)
    
    return settings


@router.put("/api/settings/notifications")
async def update_notification_settings(settings: NotificationSettings):
    """更新通知设置。"""
    try:
        settings_dict = settings.model_dump(exclude_none=True)
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
async def get_generic_settings():
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
        else:
            settings[key] = get_env_value(key)
    
    return settings


@router.put("/api/settings/generic")
async def update_generic_settings(settings: GenericSettings):
    """更新通用设置。"""
    try:
        settings_dict = settings.model_dump(exclude_none=True)
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
async def get_ai_settings():
    """获取AI模型设置。"""
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
        settings[key] = get_env_value(key)
    
    return settings


@router.put("/api/settings/ai")
async def update_ai_settings(settings: dict):
    """更新AI模型设置。"""
    try:
        ai_keys = [
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL_NAME",
            "PROXY_URL",
            "AI_MAX_TOKENS_PARAM_NAME",
            "AI_MAX_TOKENS_LIMIT",
        ]
        save_env_settings(settings, ai_keys)
        from src.config import reload_config
        reload_config()
        return {"message": "AI模型设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新AI模型设置时出错: {e}")


@router.get("/api/settings/proxy")
async def get_proxy_settings():
    """获取代理设置。"""
    proxy_keys = [
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

    bool_keys = {
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

    settings = {}
    for key in proxy_keys:
        settings[key] = get_bool_env_value(key) if key in bool_keys else get_env_value(key, "")

    return settings


@router.put("/api/settings/proxy")
async def update_proxy_settings(settings: dict):
    """更新代理设置。"""
    try:
        proxy_keys = [
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
        save_env_settings(settings, proxy_keys)

        # 代理配置会影响AI与通知渠道，两侧都需要重新加载
        from src.config import reload_config
        reload_config()

        from src.notifier import config as notifier_config
        notifier_config.reload()

        return {"message": "代理设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新代理设置时出错: {e}")
