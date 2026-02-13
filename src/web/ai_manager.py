from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI, AsyncOpenAI
import httpx

import src.config
from src.storage import get_storage
from src.config import STORAGE_BACKEND
from src.logging_config import get_logger
from src.web.auth import require_auth, has_category, check_permission


router = APIRouter()
logger = get_logger(__name__, service="web")


def _parse_bool(value, default: bool = False) -> bool:
    """解析布尔配置值，兼容字符串与数字。"""
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


def _require_ai_access(user: dict = Depends(require_auth)) -> dict:
    """要求当前用户具备 AI 配置权限。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if not (has_category(user, "ai") or check_permission(user, "manage_system")):
        raise HTTPException(status_code=403, detail="权限不足，需要 AI 配置权限")
    return user


def _resolve_tokens_config(settings: dict, default_param_name: str = "", default_limit: int = 20000) -> tuple[str, int]:
    """解析 tokens 字段名与上限，优先使用入参，缺失时回退到调用方传入的默认值。"""
    param_name = (settings.get("AI_MAX_TOKENS_PARAM_NAME") or default_param_name or "").strip()
    try:
        normalized_default_limit = int(default_limit)
    except (TypeError, ValueError):
        normalized_default_limit = 20000
    if normalized_default_limit <= 0:
        normalized_default_limit = 20000

    raw_limit = settings.get("AI_MAX_TOKENS_LIMIT")
    if raw_limit in (None, ""):
        limit = normalized_default_limit
    else:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = normalized_default_limit

    # 测试请求限制上限，避免无意义的大额调用
    test_limit = max(1, min(limit, 10))
    return param_name, test_limit


@router.post("/api/settings/ai/test")
async def test_ai_settings(settings: dict, user: dict = Depends(_require_ai_access)):
    """测试 AI 模型配置是否可用（从 Web 进程发起）。"""
    http_client = None
    try:
        user_extra_config = {}
        if STORAGE_BACKEND() == "postgres":
            user_id = str((user or {}).get("user_id") or (user or {}).get("id") or "").strip()
            if not user_id:
                return {
                    "success": False,
                    "message": "未识别当前用户，无法执行AI连接测试。"
                }

            storage = get_storage()
            user_api_config = storage.get_default_api_config(user_id) or {}
            user_extra_config = user_api_config.get("extra_config") if isinstance(user_api_config.get("extra_config"), dict) else {}
            api_key = str(settings.get("OPENAI_API_KEY") or user_api_config.get("api_key") or "").strip()
            base_url = str(settings.get("OPENAI_BASE_URL") or user_api_config.get("api_base_url") or "").strip()
            model_name = str(settings.get("OPENAI_MODEL_NAME") or user_api_config.get("model") or "").strip()

            if not api_key or not base_url or not model_name:
                return {
                    "success": False,
                    "message": "当前用户AI配置不完整，请先保存 API Key、Base URL 和模型名称。"
                }
        else:
            api_key = settings.get("OPENAI_API_KEY") or src.config.API_KEY() or ""
            base_url = settings.get("OPENAI_BASE_URL") or src.config.BASE_URL() or ""
            model_name = settings.get("OPENAI_MODEL_NAME") or src.config.MODEL_NAME() or ""

        proxy_url = settings.get("PROXY_URL")
        if proxy_url in (None, ""):
            if STORAGE_BACKEND() == "postgres":
                proxy_url = str(user_extra_config.get("PROXY_URL") or "").strip()
            else:
                proxy_url = user_extra_config.get("PROXY_URL") or src.config.PROXY_URL() or ""

        proxy_ai_enabled = settings.get("PROXY_AI_ENABLED")
        if proxy_ai_enabled is None:
            if "PROXY_AI_ENABLED" in user_extra_config:
                proxy_ai_enabled = _parse_bool(user_extra_config.get("PROXY_AI_ENABLED"), default=False)
            elif STORAGE_BACKEND() == "postgres":
                proxy_ai_enabled = False
            else:
                proxy_ai_enabled = src.config.PROXY_AI_ENABLED()
        else:
            proxy_ai_enabled = _parse_bool(proxy_ai_enabled, default=False)

        client_params = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": httpx.Timeout(30.0),
        }

        if proxy_ai_enabled and proxy_url:
            http_client = httpx.Client(proxy=proxy_url, timeout=30.0)
            client_params["http_client"] = http_client
        elif proxy_url and not proxy_ai_enabled:
            logger.info(
                "检测到代理地址但 AI 代理未开启，本次 AI 测试将直连",
                extra={"event": "ai_proxy_disabled_for_test"}
            )

        logger.info(
            "执行 AI 连接测试",
            extra={
                "event": "ai_settings_test_start",
                "base_url": base_url,
                "model_name": model_name,
                "proxy_ai_enabled": bool(proxy_ai_enabled),
                "proxy_configured": bool(proxy_url)
            }
        )

        client = OpenAI(**client_params)

        if STORAGE_BACKEND() == "postgres":
            merged_settings = dict(settings)
            if "AI_MAX_TOKENS_PARAM_NAME" not in merged_settings and user_extra_config.get("AI_MAX_TOKENS_PARAM_NAME"):
                merged_settings["AI_MAX_TOKENS_PARAM_NAME"] = user_extra_config.get("AI_MAX_TOKENS_PARAM_NAME")
            if "AI_MAX_TOKENS_LIMIT" not in merged_settings and user_extra_config.get("AI_MAX_TOKENS_LIMIT") not in (None, ""):
                merged_settings["AI_MAX_TOKENS_LIMIT"] = user_extra_config.get("AI_MAX_TOKENS_LIMIT")
            default_param_name = str(user_extra_config.get("AI_MAX_TOKENS_PARAM_NAME") or "").strip()
            raw_default_limit = user_extra_config.get("AI_MAX_TOKENS_LIMIT")
            try:
                default_limit = int(raw_default_limit) if raw_default_limit not in (None, "") else 20000
            except (TypeError, ValueError):
                default_limit = 20000
            tokens_param_name, tokens_test_limit = _resolve_tokens_config(
                merged_settings,
                default_param_name=default_param_name,
                default_limit=default_limit,
            )
        else:
            tokens_param_name, tokens_test_limit = _resolve_tokens_config(
                settings,
                default_param_name=src.config.AI_MAX_TOKENS_PARAM_NAME(),
                default_limit=src.config.AI_MAX_TOKENS_LIMIT(),
            )
        request_kwargs = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": "Hello, this is a test message to verify the connection."}
            ],
        }
        if tokens_param_name:
            request_kwargs[tokens_param_name] = tokens_test_limit

        response = client.chat.completions.create(
            **src.config.get_ai_request_params(**request_kwargs)
        )

        return {
            "success": True,
            "message": "AI模型连接测试成功！",
            "response": response.choices[0].message.content if response.choices else "No response"
        }
    except Exception as e:
        logger.warning(
            "AI 连接测试失败",
            extra={"event": "ai_settings_test_failed"},
            exc_info=e
        )
        return {
            "success": False,
            "message": f"AI模型连接测试失败: {str(e)}"
        }
    finally:
        if http_client is not None:
            http_client.close()


@router.post("/api/settings/ai/test/backend")
async def test_ai_settings_backend(user: dict = Depends(_require_ai_access)):
    """测试 AI 模型配置是否可用（从后端容器环境发起）。"""
    http_async_client = None
    try:
        if STORAGE_BACKEND() == "postgres":
            user_id = str((user or {}).get("user_id") or (user or {}).get("id") or "").strip()
            if not user_id:
                return {
                    "success": False,
                    "message": "未识别当前用户，无法执行后端AI测试。"
                }

            storage = get_storage()
            user_api_config = storage.get_default_api_config(user_id) or {}
            api_key = str(user_api_config.get("api_key") or "").strip()
            base_url = str(user_api_config.get("api_base_url") or "").strip()
            model_name = str(user_api_config.get("model") or "").strip()
            extra_config = user_api_config.get("extra_config") if isinstance(user_api_config.get("extra_config"), dict) else {}
            tokens_param_name = str(extra_config.get("AI_MAX_TOKENS_PARAM_NAME") or "").strip()
            try:
                raw_tokens_limit = extra_config.get("AI_MAX_TOKENS_LIMIT")
                tokens_limit = int(raw_tokens_limit) if raw_tokens_limit not in (None, "") else 20000
            except (TypeError, ValueError):
                tokens_limit = 20000
            proxy_url = str(extra_config.get("PROXY_URL") or "").strip()
            proxy_ai_enabled = _parse_bool(extra_config.get("PROXY_AI_ENABLED"), default=False)

            if not api_key or not base_url or not model_name:
                return {
                    "success": False,
                    "message": "当前用户尚未完成AI配置，请先保存API Key、Base URL和模型名称。"
                }

            client_kwargs = {
                "api_key": api_key,
                "base_url": base_url,
                "timeout": httpx.Timeout(30.0),
            }
            if proxy_ai_enabled and proxy_url:
                http_async_client = httpx.AsyncClient(proxy=proxy_url, timeout=30.0)
                client_kwargs["http_client"] = http_async_client

            client = AsyncOpenAI(**client_kwargs)
        else:
            if not src.config.client:
                success = src.config.reload_config()
                if not success or not src.config.client:
                    return {
                        "success": False,
                        "message": "后端AI客户端未初始化，请检查 .env 文件中的AI配置。"
                    }
            client = src.config.client
            model_name = src.config.MODEL_NAME()
            tokens_param_name = src.config.AI_MAX_TOKENS_PARAM_NAME()
            tokens_limit = src.config.AI_MAX_TOKENS_LIMIT()

        tokens_test_limit = max(1, min(tokens_limit, 10))
        request_kwargs = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": "Hello, this is a test message from backend container to verify connection."}
            ],
        }
        if tokens_param_name:
            request_kwargs[tokens_param_name] = tokens_test_limit

        response = await client.chat.completions.create(
            **src.config.get_ai_request_params(**request_kwargs)
        )

        return {
            "success": True,
            "message": "后端AI模型连接测试成功！容器网络正常。",
            "response": response.choices[0].message.content if response.choices else "No response"
        }
    except Exception as e:
        logger.warning(
            "后端 AI 连接测试失败",
            extra={"event": "ai_backend_test_failed"},
            exc_info=e
        )
        return {
            "success": False,
            "message": f"后端AI模型连接测试失败: {str(e)}。这通常表示容器网络或代理配置存在问题。"
        }
    finally:
        if http_async_client is not None:
            await http_async_client.aclose()
