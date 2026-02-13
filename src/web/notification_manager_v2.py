from fastapi import APIRouter, Depends, HTTPException

from src.ai_handler import (
    send_all_notifications,
    send_test_notification,
    send_test_product_notification,
    send_test_task_completion_notification,
)
from src.logging_config import get_logger
from src.web.auth import check_permission, has_category, is_multi_user_mode, require_auth
from src.web.models import (
    NotificationRequest,
    TestNotificationRequest,
    TestProductNotificationRequest,
    TestTaskCompletionNotificationRequest,
)

logger = get_logger(__name__, service="web")
router = APIRouter()

CHANNEL_NAME_MAP = {
    "ntfy": "Ntfy",
    "gotify": "Gotify",
    "bark": "Bark",
    "wx_bot": "企业微信机器人",
    "wx_app": "企业微信应用",
    "telegram": "Telegram",
    "webhook": "Webhook",
    "dingtalk": "钉钉机器人",
}


def _require_notify_access(user: dict = Depends(require_auth)) -> dict:
    """要求当前用户具备通知配置权限。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if not (has_category(user, "notify") or check_permission(user, "manage_system")):
        raise HTTPException(status_code=403, detail="权限不足，需要通知配置权限")
    return user


def _resolve_owner_id(user: dict) -> str | None:
    """在多用户模式下解析当前用户ID。"""
    if not is_multi_user_mode():
        return None
    user_id = (user or {}).get("user_id") or (user or {}).get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未识别当前用户")
    return str(user_id)


@router.post("/api/notifications/send")
async def send_notification_api(
    item_data: NotificationRequest,
    user: dict = Depends(_require_notify_access),
):
    """发送通知到当前用户可用的通知配置。"""
    try:
        owner_id = _resolve_owner_id(user)
        product_data = item_data.model_dump()

        ai_reason = ""
        ai_payload = product_data.get("ai_analysis")
        if isinstance(ai_payload, dict):
            ai_reason = str(ai_payload.get("reason", "")).strip()

        if not ai_reason and isinstance(product_data.get("商品信息"), dict):
            product_ai = product_data["商品信息"].get("ai_analysis")
            if isinstance(product_ai, dict):
                ai_reason = str(product_ai.get("reason", "")).strip()

        result = await send_all_notifications(
            product_data,
            ai_reason or "用户手动发送通知",
            owner_id=owner_id,
            bound_task=item_data.bound_task or item_data.bound_account,
        )
        return {"message": "通知发送完成。", "channels": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "发送通知失败",
            extra={"event": "notification_send_failed"},
            exc_info=exc,
        )
        raise HTTPException(status_code=500, detail=f"发送通知时出错: {exc}")


@router.post("/api/notifications/test")
async def send_test_notification_api(
    request: TestNotificationRequest,
    user: dict = Depends(_require_notify_access),
):
    """向指定渠道发送测试通知。"""
    try:
        owner_id = _resolve_owner_id(user)
        channel_display_name = CHANNEL_NAME_MAP.get(request.channel, request.channel)
        result = await send_test_notification(
            request.channel,
            owner_id=owner_id,
            bound_task=request.bound_task or request.bound_account,
            config_id=request.config_id,
        )
        if result:
            return {"message": f"测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        return {"message": f"测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "发送测试通知失败",
            extra={"event": "notification_test_failed", "channel": request.channel},
            exc_info=exc,
        )
        raise HTTPException(status_code=500, detail=f"发送测试通知时出错: {exc}")


@router.post("/api/notifications/test-task-completion")
async def send_test_task_completion_notification_api(
    request: TestTaskCompletionNotificationRequest,
    user: dict = Depends(_require_notify_access),
):
    """向指定渠道发送任务完成测试通知。"""
    try:
        owner_id = _resolve_owner_id(user)
        channel_display_name = CHANNEL_NAME_MAP.get(request.channel, request.channel)
        result = await send_test_task_completion_notification(
            request.channel,
            owner_id=owner_id,
            bound_task=request.bound_task or request.bound_account,
            config_id=request.config_id,
        )
        if result:
            return {"message": f"任务完成测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        return {"message": f"任务完成测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "发送任务完成测试通知失败",
            extra={"event": "notification_test_completion_failed", "channel": request.channel},
            exc_info=exc,
        )
        raise HTTPException(status_code=500, detail=f"发送任务完成测试通知时出错: {exc}")


@router.post("/api/notifications/test-product")
async def send_test_product_notification_api(
    request: TestProductNotificationRequest,
    user: dict = Depends(_require_notify_access),
):
    """向指定渠道发送商品卡测试通知。"""
    try:
        owner_id = _resolve_owner_id(user)
        channel_display_name = CHANNEL_NAME_MAP.get(request.channel, request.channel)
        result = await send_test_product_notification(
            request.channel,
            owner_id=owner_id,
            bound_task=request.bound_task or request.bound_account,
            config_id=request.config_id,
        )
        if result:
            return {"message": f"商品卡测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        return {"message": f"商品卡测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "发送商品卡测试通知失败",
            extra={"event": "notification_test_product_failed", "channel": request.channel},
            exc_info=exc,
        )
        raise HTTPException(status_code=500, detail=f"发送商品卡测试通知时出错: {exc}")
