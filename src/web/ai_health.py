import asyncio
import copy
import time
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional

import httpx
from openai import AsyncOpenAI, OpenAI

import src.config
from src.config import STORAGE_BACKEND
from src.logging_config import get_logger
from src.storage import get_storage


logger = get_logger(__name__, service="web")

# 16x16 PNG（透明像素），用于多模态能力探测时避免依赖外部图片服务。
_VISION_TEST_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAEklEQVR42mNgGAWjYBSMAggAAAQQAAGvRYgsAAAAAElFTkSuQmCC"
)

_AI_HEALTH_CACHE: Dict[str, Dict[str, Any]] = {}
_AI_HEALTH_CACHE_LOCK = Lock()


def _now_text() -> str:
    """返回本地时间文本，便于前端直接展示。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_bool(value: Any, default: bool = False) -> bool:
    """将任意输入稳健转换为布尔值。"""
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


def _resolve_int(value: Any, default: int) -> int:
    """把值转换为正整数，失败时回退默认值。"""
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _resolve_user_id(user: Optional[dict]) -> str:
    """提取当前用户ID。"""
    return str((user or {}).get("user_id") or (user or {}).get("id") or "").strip()


def _cache_key(user: Optional[dict]) -> str:
    """根据后端模式与用户生成缓存键。"""
    backend = (STORAGE_BACKEND() or "local").lower()
    if backend == "postgres":
        return f"postgres:{_resolve_user_id(user) or 'anonymous'}"
    return "local:global"


def _build_probe_result(
    *,
    success: Optional[bool],
    level: str,
    message: str,
    latency_ms: Optional[int] = None,
    checked_at: str = "",
) -> Dict[str, Any]:
    return {
        "success": success,
        "level": level,
        "message": str(message or ""),
        "latency_ms": latency_ms,
        "checked_at": checked_at,
    }


def _build_vision_result(
    *,
    status: str,
    level: str,
    message: str,
    latency_ms: Optional[int] = None,
    checked_at: str = "",
) -> Dict[str, Any]:
    return {
        "status": status,
        "level": level,
        "message": str(message or ""),
        "latency_ms": latency_ms,
        "checked_at": checked_at,
    }


def _resolve_effective_ai_config(user: Optional[dict], overrides: Optional[dict] = None) -> Dict[str, Any]:
    """按运行模式解析当前应生效的 AI 配置。"""
    payload = overrides if isinstance(overrides, dict) else {}
    backend = (STORAGE_BACKEND() or "local").lower()

    if backend == "postgres":
        user_id = _resolve_user_id(user)
        user_api_config: Dict[str, Any] = {}
        if user_id:
            try:
                user_api_config = get_storage().get_default_api_config(user_id) or {}
            except Exception as exc:
                logger.warning(
                    "读取用户AI配置失败",
                    extra={"event": "ai_health_load_user_config_failed", "owner_id": user_id},
                    exc_info=exc,
                )

        extra_config = user_api_config.get("extra_config") if isinstance(user_api_config.get("extra_config"), dict) else {}
        api_key = str(payload.get("OPENAI_API_KEY") or user_api_config.get("api_key") or "").strip()
        base_url = str(payload.get("OPENAI_BASE_URL") or user_api_config.get("api_base_url") or "").strip()
        model_name = str(payload.get("OPENAI_MODEL_NAME") or user_api_config.get("model") or "").strip()

        proxy_url = payload.get("PROXY_URL")
        if proxy_url in (None, ""):
            proxy_url = str(extra_config.get("PROXY_URL") or "").strip()
        else:
            proxy_url = str(proxy_url).strip()

        proxy_ai_enabled = payload.get("PROXY_AI_ENABLED")
        if proxy_ai_enabled is None:
            proxy_ai_enabled = _parse_bool(extra_config.get("PROXY_AI_ENABLED"), default=False)
        else:
            proxy_ai_enabled = _parse_bool(proxy_ai_enabled, default=False)

        tokens_param_name = str(
            payload.get("AI_MAX_TOKENS_PARAM_NAME") or extra_config.get("AI_MAX_TOKENS_PARAM_NAME") or ""
        ).strip()
        tokens_limit_default = _resolve_int(extra_config.get("AI_MAX_TOKENS_LIMIT"), 20000)
        tokens_limit = _resolve_int(payload.get("AI_MAX_TOKENS_LIMIT"), tokens_limit_default)

        return {
            "backend": backend,
            "source": "postgres_user_config",
            "source_label": "当前用户配置（PostgreSQL）",
            "owner_id": user_id,
            "api_key": api_key,
            "api_key_set": bool(api_key),
            "base_url": base_url,
            "base_url_set": bool(base_url),
            "model_name": model_name,
            "model_name_set": bool(model_name),
            "proxy_url": proxy_url,
            "proxy_ai_enabled": bool(proxy_ai_enabled),
            "tokens_param_name": tokens_param_name,
            "tokens_limit": tokens_limit,
        }

    api_key = str(payload.get("OPENAI_API_KEY") or src.config.API_KEY() or "").strip()
    base_url = str(payload.get("OPENAI_BASE_URL") or src.config.BASE_URL() or "").strip()
    model_name = str(payload.get("OPENAI_MODEL_NAME") or src.config.MODEL_NAME() or "").strip()

    proxy_url = payload.get("PROXY_URL")
    if proxy_url in (None, ""):
        proxy_url = str(src.config.PROXY_URL() or "").strip()
    else:
        proxy_url = str(proxy_url).strip()

    proxy_ai_enabled = payload.get("PROXY_AI_ENABLED")
    if proxy_ai_enabled is None:
        proxy_ai_enabled = src.config.PROXY_AI_ENABLED()
    else:
        proxy_ai_enabled = _parse_bool(proxy_ai_enabled, default=False)

    tokens_param_name = str(payload.get("AI_MAX_TOKENS_PARAM_NAME") or src.config.AI_MAX_TOKENS_PARAM_NAME() or "").strip()
    tokens_limit = _resolve_int(payload.get("AI_MAX_TOKENS_LIMIT"), src.config.AI_MAX_TOKENS_LIMIT())

    return {
        "backend": backend,
        "source": "env_global_config",
        "source_label": "全局配置（.env）",
        "owner_id": "",
        "api_key": api_key,
        "api_key_set": bool(api_key),
        "base_url": base_url,
        "base_url_set": bool(base_url),
        "model_name": model_name,
        "model_name_set": bool(model_name),
        "proxy_url": proxy_url,
        "proxy_ai_enabled": bool(proxy_ai_enabled),
        "tokens_param_name": tokens_param_name,
        "tokens_limit": tokens_limit,
    }


def _resolve_config_state(config: Dict[str, Any]) -> Dict[str, Any]:
    """生成配置完整性状态。"""
    api_key_set = bool(config.get("api_key_set"))
    base_url_set = bool(config.get("base_url_set"))
    model_name_set = bool(config.get("model_name_set"))

    missing_items = []
    if not api_key_set:
        missing_items.append("API Key")
    if not base_url_set:
        missing_items.append("Base URL")
    if not model_name_set:
        missing_items.append("模型名称")

    config_ready = len(missing_items) == 0
    if config_ready:
        message = "AI 配置完整，可执行连通性检测。"
    else:
        message = f"AI 配置不完整，缺少：{', '.join(missing_items)}。"

    return {
        "ready": config_ready,
        "message": message,
        "api_key_set": api_key_set,
        "base_url_set": base_url_set,
        "model_name_set": model_name_set,
    }


def _build_request_kwargs(config: Dict[str, Any], content: Any) -> Dict[str, Any]:
    """统一构造请求参数，保证 tokens 参数行为一致。"""
    request_kwargs = {
        "model": str(config.get("model_name") or "").strip(),
        "messages": [{"role": "user", "content": content}],
    }

    tokens_param_name = str(config.get("tokens_param_name") or "").strip()
    if tokens_param_name:
        tokens_limit = _resolve_int(config.get("tokens_limit"), 20000)
        request_kwargs[tokens_param_name] = max(1, min(tokens_limit, 10))

    return src.config.get_ai_request_params(**request_kwargs)


def _run_web_text_probe_sync(config: Dict[str, Any]) -> Dict[str, Any]:
    """执行 Web 进程连通性探测（同步客户端）。"""
    http_client = None
    started = time.perf_counter()
    try:
        client_params: Dict[str, Any] = {
            "api_key": config.get("api_key"),
            "base_url": config.get("base_url"),
            "timeout": httpx.Timeout(30.0),
        }
        if config.get("proxy_ai_enabled") and config.get("proxy_url"):
            http_client = httpx.Client(proxy=str(config.get("proxy_url")), timeout=30.0)
            client_params["http_client"] = http_client

        client = OpenAI(**client_params)
        client.chat.completions.create(
            **_build_request_kwargs(
                config,
                "Health check from web process. Reply with OK.",
            )
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        return _build_probe_result(
            success=True,
            level="ok",
            message="Web 进程连通成功。",
            latency_ms=latency_ms,
            checked_at=_now_text(),
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return _build_probe_result(
            success=False,
            level="error",
            message=f"Web 进程连通失败：{exc}",
            latency_ms=latency_ms,
            checked_at=_now_text(),
        )
    finally:
        if http_client is not None:
            http_client.close()


async def _run_backend_text_probe_async(config: Dict[str, Any]) -> Dict[str, Any]:
    """执行后端容器连通性探测（异步客户端）。"""
    http_async_client = None
    started = time.perf_counter()
    try:
        client_params: Dict[str, Any] = {
            "api_key": config.get("api_key"),
            "base_url": config.get("base_url"),
            "timeout": httpx.Timeout(30.0),
        }
        if config.get("proxy_ai_enabled") and config.get("proxy_url"):
            http_async_client = httpx.AsyncClient(proxy=str(config.get("proxy_url")), timeout=30.0)
            client_params["http_client"] = http_async_client

        client = AsyncOpenAI(**client_params)
        await client.chat.completions.create(
            **_build_request_kwargs(
                config,
                "Health check from backend process. Reply with OK.",
            )
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        return _build_probe_result(
            success=True,
            level="ok",
            message="后端进程连通成功。",
            latency_ms=latency_ms,
            checked_at=_now_text(),
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return _build_probe_result(
            success=False,
            level="error",
            message=f"后端进程连通失败：{exc}",
            latency_ms=latency_ms,
            checked_at=_now_text(),
        )
    finally:
        if http_async_client is not None:
            await http_async_client.aclose()


def _classify_vision_error(message: str) -> str:
    """根据错误文本归类图像能力检测结果。"""
    lowered = (message or "").lower()
    unsupported_markers = [
        "does not support image",
        "not support image",
        "unsupported image",
        "unsupported content type",
        "image_url is not supported",
        "vision is not supported",
        "input_image is not supported",
        "多模态",
        "不支持图片",
        "不支持图像",
    ]
    for marker in unsupported_markers:
        if marker in lowered:
            return "unsupported"
    small_image_markers = [
        "image dimensions are too small",
        "minimum allowed dimension",
    ]
    for marker in small_image_markers:
        if marker in lowered:
            return "supported"
    return "unknown"


async def _run_vision_probe_async(config: Dict[str, Any]) -> Dict[str, Any]:
    """执行图像能力探测，判定模型是否支持 image_url 输入。"""
    http_async_client = None
    started = time.perf_counter()
    try:
        client_params: Dict[str, Any] = {
            "api_key": config.get("api_key"),
            "base_url": config.get("base_url"),
            "timeout": httpx.Timeout(30.0),
        }
        if config.get("proxy_ai_enabled") and config.get("proxy_url"):
            http_async_client = httpx.AsyncClient(proxy=str(config.get("proxy_url")), timeout=30.0)
            client_params["http_client"] = http_async_client

        client = AsyncOpenAI(**client_params)
        vision_content = [
            {"type": "text", "text": "Vision capability check. Reply with OK."},
            {"type": "image_url", "image_url": {"url": _VISION_TEST_IMAGE_DATA_URL}},
        ]
        await client.chat.completions.create(**_build_request_kwargs(config, vision_content))

        latency_ms = int((time.perf_counter() - started) * 1000)
        return _build_vision_result(
            status="supported",
            level="ok",
            message="模型支持图像输入（image_url）。",
            latency_ms=latency_ms,
            checked_at=_now_text(),
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        status = _classify_vision_error(str(exc))
        if status == "unsupported":
            return _build_vision_result(
                status="unsupported",
                level="warning",
                message=f"模型不支持图像输入：{exc}",
                latency_ms=latency_ms,
                checked_at=_now_text(),
            )
        if status == "supported":
            return _build_vision_result(
                status="supported",
                level="warning",
                message=f"模型支持图像输入，但本次探测图片参数不合规：{exc}",
                latency_ms=latency_ms,
                checked_at=_now_text(),
            )
        return _build_vision_result(
            status="unknown",
            level="warning",
            message=f"图像能力暂时无法判断：{exc}",
            latency_ms=latency_ms,
            checked_at=_now_text(),
        )
    finally:
        if http_async_client is not None:
            await http_async_client.aclose()


def _compute_overall_level(
    config_ready: bool,
    web_test: Dict[str, Any],
    backend_test: Dict[str, Any],
    run_web: bool,
    run_backend: bool,
) -> Dict[str, str]:
    """综合配置完整性与连通性结果生成总状态。"""
    if not config_ready:
        return {"level": "error", "label": "异常", "message": "AI 配置不完整。"}

    executed = []
    if run_web:
        executed.append(web_test.get("success") is True)
    if run_backend:
        executed.append(backend_test.get("success") is True)

    if not executed:
        return {"level": "unknown", "label": "未知", "message": "尚未执行连通性检测。"}
    if all(executed):
        return {"level": "ok", "label": "正常", "message": "AI API 连通性正常。"}
    if any(executed):
        return {"level": "warning", "label": "警告", "message": "AI API 部分可用，请检查失败链路。"}
    return {"level": "error", "label": "异常", "message": "AI API 连通性不可用。"}


def _default_health_snapshot(config: Dict[str, Any], config_state: Dict[str, Any]) -> Dict[str, Any]:
    """返回默认（未检测）健康快照。"""
    overall = _compute_overall_level(
        config_state.get("ready", False),
        _build_probe_result(success=None, level="unknown", message="尚未检测。"),
        _build_probe_result(success=None, level="unknown", message="尚未检测。"),
        run_web=False,
        run_backend=False,
    )
    return {
        "source": config.get("source"),
        "source_label": config.get("source_label"),
        "owner_id": config.get("owner_id") or "",
        "config": {
            "api_key_set": bool(config_state.get("api_key_set")),
            "base_url_set": bool(config_state.get("base_url_set")),
            "model_name_set": bool(config_state.get("model_name_set")),
            "ready": bool(config_state.get("ready")),
            "message": str(config_state.get("message") or ""),
        },
        "web_test": _build_probe_result(success=None, level="unknown", message="尚未检测。"),
        "backend_test": _build_probe_result(success=None, level="unknown", message="尚未检测。"),
        "vision_capability": _build_vision_result(status="unknown", level="unknown", message="尚未检测。"),
        "overall_level": overall["level"],
        "overall_label": overall["label"],
        "overall_message": overall["message"],
        "checked_at": "",
    }


def _set_cached_snapshot(user: Optional[dict], snapshot: Dict[str, Any]) -> None:
    """写入缓存，避免设置页频繁触发真实探测。"""
    with _AI_HEALTH_CACHE_LOCK:
        _AI_HEALTH_CACHE[_cache_key(user)] = copy.deepcopy(snapshot)


def invalidate_ai_health_snapshot(user: Optional[dict]) -> None:
    """失效当前用户的 AI 健康缓存。"""
    with _AI_HEALTH_CACHE_LOCK:
        _AI_HEALTH_CACHE.pop(_cache_key(user), None)


def get_ai_health_snapshot(user: Optional[dict]) -> Dict[str, Any]:
    """读取最新 AI 健康状态（仅读缓存，不触发网络探测）。"""
    config = _resolve_effective_ai_config(user)
    config_state = _resolve_config_state(config)

    with _AI_HEALTH_CACHE_LOCK:
        cached = copy.deepcopy(_AI_HEALTH_CACHE.get(_cache_key(user)))

    if not cached:
        return _default_health_snapshot(config, config_state)

    # 每次读取都覆盖来源与配置完整性，避免配置变更后缓存误导。
    cached["source"] = config.get("source")
    cached["source_label"] = config.get("source_label")
    cached["owner_id"] = config.get("owner_id") or ""
    cached["config"] = {
        "api_key_set": bool(config_state.get("api_key_set")),
        "base_url_set": bool(config_state.get("base_url_set")),
        "model_name_set": bool(config_state.get("model_name_set")),
        "ready": bool(config_state.get("ready")),
        "message": str(config_state.get("message") or ""),
    }
    if not config_state.get("ready"):
        cached["overall_level"] = "error"
        cached["overall_label"] = "异常"
        cached["overall_message"] = "AI 配置不完整。"
    return cached


async def run_ai_health_check(
    user: Optional[dict],
    *,
    overrides: Optional[dict] = None,
    run_web: bool = True,
    run_backend: bool = True,
    check_vision: bool = True,
) -> Dict[str, Any]:
    """执行 AI 健康检查并更新缓存。"""
    config = _resolve_effective_ai_config(user, overrides=overrides)
    config_state = _resolve_config_state(config)
    snapshot = _default_health_snapshot(config, config_state)

    if not config_state.get("ready"):
        _set_cached_snapshot(user, snapshot)
        return snapshot

    web_result = _build_probe_result(success=None, level="unknown", message="本次未执行。")
    backend_result = _build_probe_result(success=None, level="unknown", message="本次未执行。")

    tasks = []
    task_types = []
    if run_web:
        tasks.append(asyncio.to_thread(_run_web_text_probe_sync, config))
        task_types.append("web")
    if run_backend:
        tasks.append(_run_backend_text_probe_async(config))
        task_types.append("backend")

    if tasks:
        probe_results = await asyncio.gather(*tasks)
        for probe_type, probe_result in zip(task_types, probe_results):
            if probe_type == "web":
                web_result = probe_result
            elif probe_type == "backend":
                backend_result = probe_result

    vision_result = _build_vision_result(status="unknown", level="unknown", message="本次未执行。")
    if check_vision:
        if (web_result.get("success") is True) or (backend_result.get("success") is True):
            vision_result = await _run_vision_probe_async(config)
        else:
            vision_result = _build_vision_result(
                status="unknown",
                level="warning",
                message="文本连通性未通过，暂未执行图像能力检测。",
            )

    overall = _compute_overall_level(config_state.get("ready", False), web_result, backend_result, run_web, run_backend)
    checked_at = _now_text()
    snapshot = {
        "source": config.get("source"),
        "source_label": config.get("source_label"),
        "owner_id": config.get("owner_id") or "",
        "config": {
            "api_key_set": bool(config_state.get("api_key_set")),
            "base_url_set": bool(config_state.get("base_url_set")),
            "model_name_set": bool(config_state.get("model_name_set")),
            "ready": bool(config_state.get("ready")),
            "message": str(config_state.get("message") or ""),
        },
        "web_test": web_result,
        "backend_test": backend_result,
        "vision_capability": vision_result,
        "overall_level": overall["level"],
        "overall_label": overall["label"],
        "overall_message": overall["message"],
        "checked_at": checked_at,
    }
    _set_cached_snapshot(user, snapshot)
    return snapshot
