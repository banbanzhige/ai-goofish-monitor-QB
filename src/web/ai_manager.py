from fastapi import APIRouter, Depends, HTTPException

from src.logging_config import get_logger
from src.web.ai_health import get_ai_health_snapshot, run_ai_health_check
from src.web.auth import check_permission, has_category, require_auth


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


@router.get("/api/settings/health/ai")
async def get_ai_health(user: dict = Depends(_require_ai_access)):
    """获取最近一次 AI API 可用性检测结果（不触发实时探测）。"""
    return get_ai_health_snapshot(user)


@router.post("/api/settings/health/ai/check")
async def run_ai_health(payload: dict = None, user: dict = Depends(_require_ai_access)):
    """执行 AI API 可用性检测并返回最新结果。"""
    options = payload if isinstance(payload, dict) else {}
    overrides = options.get("settings") if isinstance(options.get("settings"), dict) else None
    run_web = _parse_bool(options.get("run_web"), default=True)
    run_backend = _parse_bool(options.get("run_backend"), default=True)
    check_vision = _parse_bool(options.get("check_vision"), default=True)

    logger.info(
        "执行统一AI可用性检测",
        extra={
            "event": "ai_health_check_start",
            "run_web": run_web,
            "run_backend": run_backend,
            "check_vision": check_vision,
        },
    )
    return await run_ai_health_check(
        user,
        overrides=overrides,
        run_web=run_web,
        run_backend=run_backend,
        check_vision=check_vision,
    )


@router.post("/api/settings/ai/test")
async def test_ai_settings(settings: dict, user: dict = Depends(_require_ai_access)):
    """测试 AI 模型配置是否可用（从 Web 进程发起）。"""
    snapshot = await run_ai_health_check(
        user,
        overrides=settings if isinstance(settings, dict) else None,
        run_web=True,
        run_backend=False,
        check_vision=False,
    )
    web_result = snapshot.get("web_test") if isinstance(snapshot.get("web_test"), dict) else {}
    success = web_result.get("success") is True
    message = "AI模型连接测试成功！" if success else f"AI模型连接测试失败: {web_result.get('message') or '未知错误'}"
    return {
        "success": success,
        "message": message,
        "health": snapshot,
    }


@router.post("/api/settings/ai/test/backend")
async def test_ai_settings_backend(user: dict = Depends(_require_ai_access)):
    """测试 AI 模型配置是否可用（从后端容器环境发起）。"""
    snapshot = await run_ai_health_check(
        user,
        run_web=False,
        run_backend=True,
        check_vision=False,
    )
    backend_result = snapshot.get("backend_test") if isinstance(snapshot.get("backend_test"), dict) else {}
    success = backend_result.get("success") is True
    message = "后端AI模型连接测试成功！容器网络正常。" if success else (
        f"后端AI模型连接测试失败: {backend_result.get('message') or '未知错误'}。这通常表示容器网络或代理配置存在问题。"
    )
    return {
        "success": success,
        "message": message,
        "health": snapshot,
    }
