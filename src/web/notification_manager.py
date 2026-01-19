from fastapi import APIRouter, HTTPException
from src.web.models import NotificationRequest, TestNotificationRequest, TestTaskCompletionNotificationRequest, TestProductNotificationRequest
from src.ai_handler import send_all_notifications, send_test_notification, send_test_task_completion_notification, send_test_product_notification


router = APIRouter()


@router.post("/api/notifications/send")
async def send_notification_api(item_data: NotificationRequest):
    """发送通知到所有已配置的渠道。"""
    try:
        product_data = item_data.model_dump()

        ai_reason = ""
        if 'ai_analysis' in product_data and product_data['ai_analysis']:
            ai_reason = product_data['ai_analysis'].get('reason', '')

        if not ai_reason and '商品信息' in product_data:
            if 'ai_analysis' in product_data['商品信息'] and product_data['商品信息']['ai_analysis']:
                ai_reason = product_data['商品信息']['ai_analysis'].get('reason', '')

        if ai_reason:
            result = await send_all_notifications(product_data, ai_reason)
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
