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


router = APIRouter()
logger = get_logger(__name__, service="web")


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
    """发送通知到所有已配置的渠道。"""
    try:
        owner_id = _resolve_owner_id(user)
        product_data = item_data.model_dump()

        ai_reason = ""
        if 'ai_analysis' in product_data and product_data['ai_analysis']:
            ai_reason = product_data['ai_analysis'].get('reason', '')

        if not ai_reason and '商品信息' in product_data:
            if 'ai_analysis' in product_data['商品信息'] and product_data['商品信息']['ai_analysis']:
                ai_reason = product_data['商品信息']['ai_analysis'].get('reason', '')

        if ai_reason:
            result = await send_all_notifications(
                product_data,
                ai_reason,
                owner_id=owner_id,
                bound_account=item_data.bound_account,
            )
        else:
            result = await send_all_notifications(product_data, "用户手动发送通知")

        return {"message": "通知已发送到所有已配置的渠道。", "channels": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送通知时出错: {e}")


@router.post("/api/notifications/test")
async def send_test_notification_api(request: TestNotificationRequest):
    """向指定渠道发送测试通知。"""
    try:
        channel_name_map = {
            "ntfy": "Ntfy",
            "gotify": "Gotify",
            "bark": "Bark",
            "wx_bot": "企业微信机器人",
            "wx_app": "企业微信应用",
            "telegram": "Telegram",
            "webhook": "Webhook",
            "dingtalk": "钉钉机器人"
        }
        channel_display_name = channel_name_map.get(request.channel, request.channel)

        result = await send_test_notification(request.channel)
        if result:
            return {"message": f"测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        else:
            return {"message": f"测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送测试通知时出错: {e}")


@router.post("/api/notifications/test-task-completion")
async def send_test_task_completion_notification_api(request: TestTaskCompletionNotificationRequest):
    """向指定渠道发送任务完成通知的测试。"""
    try:
        channel_name_map = {
            "ntfy": "Ntfy",
            "gotify": "Gotify",
            "bark": "Bark",
            "wx_bot": "企业微信机器人",
            "wx_app": "企业微信应用",
            "telegram": "Telegram",
            "webhook": "Webhook",
            "dingtalk": "钉钉机器人"
        }
        channel_display_name = channel_name_map.get(request.channel, request.channel)

        result = await send_test_task_completion_notification(request.channel)
        if result:
            return {"message": f"任务完成测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        else:
            return {"message": f"任务完成测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送任务完成测试通知时出错: {e}")


@router.post("/api/notifications/test-product")
async def send_test_product_notification_api(request: TestProductNotificationRequest):
    """向指定渠道发送商品卡测试通知。"""
    try:
        channel_name_map = {
            "ntfy": "Ntfy",
            "gotify": "Gotify",
            "bark": "Bark",
            "wx_bot": "企业微信机器人",
            "wx_app": "企业微信应用",
            "telegram": "Telegram",
            "webhook": "Webhook",
            "dingtalk": "钉钉机器人"
        }
        channel_display_name = channel_name_map.get(request.channel, request.channel)

        result = await send_test_product_notification(request.channel)
        if result:
            return {"message": f"商品卡测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        else:
            return {"message": f"商品卡测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送商品卡测试通知时出错: {e}")
