import asyncio
import json
import requests
from typing import Dict, Any, Optional

from src.notifier.base import BaseNotifier
from src.notifier.config import config


class NtfyNotifier(BaseNotifier):
    """ntfy通知渠道"""
    
    def __init__(self):
        super().__init__("ntfy")
    
    async def send_test_notification(self) -> bool:
        if not config["NTFY_TOPIC_URL"] or not config["NTFY_ENABLED"]:
            return False
            
        try:
            test_title = "测试通知 - 闲鱼公开内容查看智能处理程序"
            test_message = "这是一个测试通知，用于验证ntfy配置是否正确。\n\n如果您收到这条消息，说明ntfy配置已经生效！"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    config["NTFY_TOPIC_URL"],
                    data=test_message.encode('utf-8'),
                    headers={
                        "Title": test_title.encode('utf-8'),
                        "Priority": "urgent",
                        "Tags": "bell,vibration"
                    },
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 ntfy 测试通知失败: {e}")
            return False
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        if not config["NTFY_TOPIC_URL"] or not config["NTFY_ENABLED"]:
            return False
            
        try:
            product_info = self._get_product_info(product)
            actual_product = product_info['actual_product']
            main_image = product_info['main_image']
            product_link = product_info['mobile_link'] if config["PCURL_TO_MOBILE"] else product_info['pc_link']
            
            title = actual_product.get('商品标题', 'N/A')
            price = actual_product.get('当前售价', 'N/A')
            publish_time = actual_product.get('发布时间', 'N/A')
            
            # 构建和Telegram一样的文案逻辑
            notification_title = f"🚨 新推荐!"
            message = f"{title}\n\n💰 价格: {price}\n⏰ 发布时间: {publish_time}\n📝 推荐理由: {reason}\n"
            
            # 构建请求头
            headers = {
                "Title": notification_title.encode('utf-8'),
                "Priority": "urgent",
                "Tags": "bell,vibration",
                "Click": product_link.encode('utf-8')  # 添加点击跳转链接
            }
            
            # 如果有商品图片，添加图片头
            if main_image:
                headers["Attach"] = main_image.encode('utf-8')
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    config["NTFY_TOPIC_URL"],
                    data=message.encode('utf-8'),
                    headers=headers,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 ntfy 通知失败: {e}")
            return False
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        if not config["NTFY_TOPIC_URL"] or not config["NTFY_ENABLED"]:
            return False
            
        try:
            notification_title = "🚀 任务开始"
            message = f"开始了 '{task_name}' 任务 - {reason}"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    config["NTFY_TOPIC_URL"],
                    data=message.encode('utf-8'),
                    headers={
                        "Title": notification_title.encode('utf-8'),
                        "Priority": "normal",
                        "Tags": "rocket"
                    },
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 ntfy 任务开始通知失败: {e}")
            return False
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> bool:
        if not config["NTFY_TOPIC_URL"] or not config["NTFY_ENABLED"]:
            return False
            
        try:
            notification_title = "✅ 任务完成"
            message = f"结束了 '{task_name}' 任务 - {reason}"
            if processed_count > 0 or recommended_count > 0:
                message += f"\n\n本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    config["NTFY_TOPIC_URL"],
                    data=message.encode('utf-8'),
                    headers={
                        "Title": notification_title.encode('utf-8'),
                        "Priority": "normal",
                        "Tags": "check-circle,white_check_mark"
                    },
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 ntfy 任务完成通知失败: {e}")
            return False


class GotifyNotifier(BaseNotifier):
    """Gotify通知渠道"""
    
    def __init__(self):
        super().__init__("gotify")
    
    async def send_test_notification(self) -> bool:
        if not config["GOTIFY_URL"] or not config["GOTIFY_TOKEN"] or not config["GOTIFY_ENABLED"]:
            return False
            
        try:
            test_title = "测试通知 - 闲鱼公开内容查看智能处理程序"
            test_message = "这是一个测试通知，用于验证Gotify配置是否正确。\n\n如果您收到这条消息，说明Gotify配置已经生效！"
            
            payload = {
                'title': (None, test_title),
                'message': (None, test_message),
                'priority': (None, '5')
            }
            
            gotify_url_with_token = f"{config['GOTIFY_URL']}/message?token={config['GOTIFY_TOKEN']}"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    gotify_url_with_token,
                    files=payload,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Gotify 测试通知失败: {e}")
            return False
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        if not config["GOTIFY_URL"] or not config["GOTIFY_TOKEN"] or not config["GOTIFY_ENABLED"]:
            return False
            
        try:
            product_info = self._get_product_info(product)
            actual_product = product_info['actual_product']
            
            title = actual_product.get('商品标题', 'N/A')
            price = actual_product.get('当前售价', 'N/A')
            publish_time = actual_product.get('发布时间', 'N/A')
            
            # 构建和Telegram一样的文案逻辑
            notification_title = f"🚨 新推荐!"
            message = f"{title}\n\n💰 价格: {price}\n⏰ 发布时间: {publish_time}\n📝 推荐理由: {reason}\n"
            
            payload = {
                'title': (None, notification_title),
                'message': (None, message),
                'priority': (None, '5')
            }
            
            gotify_url_with_token = f"{config['GOTIFY_URL']}/message?token={config['GOTIFY_TOKEN']}"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    gotify_url_with_token,
                    files=payload,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Gotify 通知失败: {e}")
            return False
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        if not config["GOTIFY_URL"] or not config["GOTIFY_TOKEN"] or not config["GOTIFY_ENABLED"]:
            return False
            
        try:
            notification_title = "🚀 任务开始"
            message = f"开始了 '{task_name}' 任务 - {reason}"
            
            payload = {
                'title': (None, notification_title),
                'message': (None, message),
                'priority': (None, '3')  # 正常优先级
            }
            
            gotify_url_with_token = f"{config['GOTIFY_URL']}/message?token={config['GOTIFY_TOKEN']}"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    gotify_url_with_token,
                    files=payload,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Gotify 任务开始通知失败: {e}")
            return False
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> bool:
        if not config["GOTIFY_URL"] or not config["GOTIFY_TOKEN"] or not config["GOTIFY_ENABLED"]:
            return False
            
        try:
            notification_title = "✅ 任务完成"
            message = f"结束了 '{task_name}' 任务 - {reason}"
            if processed_count > 0 or recommended_count > 0:
                message += f"\n\n本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。"
            
            payload = {
                'title': (None, notification_title),
                'message': (None, message),
                'priority': (None, '3')  # 正常优先级
            }
            
            gotify_url_with_token = f"{config['GOTIFY_URL']}/message?token={config['GOTIFY_TOKEN']}"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    gotify_url_with_token,
                    files=payload,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Gotify 任务完成通知失败: {e}")
            return False


class BarkNotifier(BaseNotifier):
    """Bark通知渠道"""
    
    def __init__(self):
        super().__init__("bark")
    
    async def send_test_notification(self) -> bool:
        if not config["BARK_URL"] or not config["BARK_ENABLED"]:
            return False
            
        try:
            test_title = "测试通知 - 闲鱼公开内容查看智能处理程序"
            test_message = "这是一个测试通知，用于验证Bark配置是否正确。\n\n如果您收到这条消息，说明Bark配置已经生效！"
            
            bark_payload = {
                "title": test_title,
                "body": test_message,
                "level": "timeSensitive",
                "group": "闲鱼公开内容查看"
            }
            
            headers = { "Content-Type": "application/json; charset=utf-8" }
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    config["BARK_URL"],
                    json=bark_payload,
                    headers=headers,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Bark 测试通知失败: {e}")
            return False
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        if not config["BARK_URL"] or not config["BARK_ENABLED"]:
            return False
            
        try:
            product_info = self._get_product_info(product)
            actual_product = product_info['actual_product']
            main_image = product_info['main_image']
            product_link = product_info['mobile_link'] if config["PCURL_TO_MOBILE"] else product_info['pc_link']
            
            title = actual_product.get('商品标题', 'N/A')
            price = actual_product.get('当前售价', 'N/A')
            publish_time = actual_product.get('发布时间', 'N/A')
            
            # 构建和Telegram一样的文案逻辑
            notification_title = f"🚨 新推荐!"
            message = f"{title}\n\n💰 价格: {price}\n⏰ 发布时间: {publish_time}\n📝 推荐理由: {reason}\n"
            
            bark_payload = {
                "title": notification_title,
                "body": message,
                "level": "timeSensitive",
            "group": "闲鱼公开内容查看"
            }
            
            bark_payload["url"] = product_link
            
            # 添加图标
            if main_image:
                bark_payload['icon'] = main_image
            
            headers = { "Content-Type": "application/json; charset=utf-8" }
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    config["BARK_URL"],
                    json=bark_payload,
                    headers=headers,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Bark 通知失败: {e}")
            return False
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        if not config["BARK_URL"] or not config["BARK_ENABLED"]:
            return False
        try:
            notification_title = "🚀 任务开始"
            message = f"开始了 '{task_name}' 任务 - {reason}"
            
            bark_payload = {
                "title": notification_title,
                "body": message,
                "level": "active",
                "group": "闲鱼公开内容查看"
            }
            
            headers = {"Content-Type": "application/json; charset=utf-8"}
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    config["BARK_URL"],
                    json=bark_payload,
                    headers=headers,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Bark 任务开始通知失败: {e}")
            return False
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> bool:
        if not config["BARK_URL"] or not config["BARK_ENABLED"]:
            return False
        try:
            notification_title = "✅ 任务完成"
            message = f"结束了 '{task_name}' 任务 - {reason}"
            if processed_count > 0 or recommended_count > 0:
                message += f"\n\n本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。"
            
            bark_payload = {
                "title": notification_title,
                "body": message,
                "level": "active",
                "group": "闲鱼公开内容查看"
            }
            
            headers = {"Content-Type": "application/json; charset=utf-8"}
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    config["BARK_URL"],
                    json=bark_payload,
                    headers=headers,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Bark 任务完成通知失败: {e}")
            return False


class WeChatBotNotifier(BaseNotifier):
    """企业微信机器人通知渠道"""
    
    def __init__(self):
        super().__init__("wx_bot")
    
    async def send_test_notification(self) -> bool:
        # 直接从环境变量获取最新配置，避免单例模式的缓存问题
        from src.config import WX_BOT_URL, get_bool_env_value
        wx_bot_url = WX_BOT_URL()
        wx_bot_enabled = get_bool_env_value("WX_BOT_ENABLED", False)
        
        if not wx_bot_url or not wx_bot_enabled:
            return False
            
        try:
            test_title = "测试通知 - 闲鱼公开内容查看智能处理程序"
            test_message = "这是一个测试通知，用于验证企业微信机器人配置是否正确。\n\n如果您收到这条消息，说明配置已经生效！"
            
            full_message = f"{test_title}\n\n{test_message}"
            
            payload = {
                "msgtype": "text",
                "text": {
                    "content": full_message
                }
            }
            
            headers = { "Content-Type": "application/json" }
            
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    wx_bot_url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            )
            
            # 检查响应状态
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") != 0:
                print(f"   -> 发送企业微信机器人测试通知失败: {result.get('errmsg', '未知错误')}")
                return False
                
            return True
        except Exception as e:
            print(f"   -> 发送企业微信机器人测试通知失败: {e}")
            return False
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        # 直接从环境变量获取最新配置，避免单例模式的缓存问题
        from src.config import WX_BOT_URL, get_bool_env_value
        wx_bot_url = WX_BOT_URL()
        wx_bot_enabled = get_bool_env_value("WX_BOT_ENABLED", False)
        
        if not wx_bot_url or not wx_bot_enabled:
            return False
            
        try:
            product_info = self._get_product_info(product)
            notification_title, message = self._format_notification_content(product_info, reason)
            main_image = product_info['main_image']
            
            headers = { "Content-Type": "application/json" }
            
            # 1. 发送包含商品链接的文字消息
            text_payload = {
                "msgtype": "text",
                "text": {
                    "content": f"{notification_title}\n\n{message}"
                }
            }
            
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    wx_bot_url,
                    json=text_payload,
                    headers=headers,
                    timeout=10
                )
            )
            
            # 检查文字消息发送状态
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") != 0:
                print(f"   -> 发送企业微信机器人文字通知失败: {result.get('errmsg', '未知错误')}")
                return False
            
            # 2. 如果有商品图片，发送图文消息（包含标题+价格+发布时间）
            if main_image:
                try:
                    # 从商品信息中提取需要的字段
                    actual_product = product_info['actual_product']
                    product_title = actual_product.get('商品标题', '未知商品')
                    price = actual_product.get('当前售价', '未知价格')
                    publish_time = actual_product.get('发布时间', '未知时间')
                    
                    # 构建图文消息
                    news_payload = {
                        "msgtype": "news",
                        "news": {
                            "articles": [
                                {
                                    "title": product_title[:128],  # 处理标题不超过128字符的限制
                                    "description": f"价格: {price}\n发布时间: {publish_time}",
                                    "url": product_info['mobile_link'] if config["PCURL_TO_MOBILE"] else product_info['pc_link'],
                                    "picurl": main_image
                                }
                            ]
                        }
                    }
                    
                    img_response = await asyncio.get_running_loop().run_in_executor(
                        None,
                        lambda: requests.post(
                            wx_bot_url,
                            json=news_payload,
                            headers=headers,
                            timeout=10
                        )
                    )
                    
                    img_response.raise_for_status()
                    img_result = img_response.json()
                    
                    if img_result.get("errcode") != 0:
                        print(f"   -> 发送商品图文消息失败: {img_result.get('errmsg', '未知错误')}")
                        # 图文消息发送失败不影响整个通知流程
                except Exception as img_e:
                    print(f"   -> 发送商品图文消息失败: {img_e}")
                    # 图文消息发送失败不影响整个通知流程
            
            return True
        except Exception as e:
            print(f"   -> 发送企业微信机器人通知失败: {e}")
            return False
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        # 直接从环境变量获取最新配置，避免单例模式的缓存问题
        from src.config import WX_BOT_URL, get_bool_env_value
        wx_bot_url = WX_BOT_URL()
        wx_bot_enabled = get_bool_env_value("WX_BOT_ENABLED", False)
        
        if not wx_bot_url or not wx_bot_enabled:
            return False
        try:
            notification_title = "🚀 任务开始"
            message = f"开始了 '{task_name}' 任务 - {reason}"
            
            payload = {
                "msgtype": "text",
                "text": {
                    "content": f"{notification_title}\n\n{message}"
                }
            }
            
            headers = {"Content-Type": "application/json"}
            
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    wx_bot_url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            )
            
            # 检查响应状态
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") != 0:
                print(f"   -> 发送企业微信机器人任务开始通知失败: {result.get('errmsg', '未知错误')}")
                return False
                
            return True
        except Exception as e:
            print(f"   -> 发送企业微信机器人任务开始通知失败: {e}")
            return False
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> bool:
        # 直接从环境变量获取最新配置，避免单例模式的缓存问题
        from src.config import WX_BOT_URL, get_bool_env_value
        wx_bot_url = WX_BOT_URL()
        wx_bot_enabled = get_bool_env_value("WX_BOT_ENABLED", False)
        
        if not wx_bot_url or not wx_bot_enabled:
            return False
        try:
            notification_title = "✅ 任务完成"
            message = f"结束了 '{task_name}' 任务 - {reason}"
            if processed_count > 0 or recommended_count > 0:
                message += f"\n\n本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。"
            
            payload = {
                "msgtype": "text",
                "text": {
                    "content": f"{notification_title}\n\n{message}"
                }
            }
            
            headers = {"Content-Type": "application/json"}
            
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    wx_bot_url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            )
            
            # 检查响应状态
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") != 0:
                print(f"   -> 发送企业微信机器人任务完成通知失败: {result.get('errmsg', '未知错误')}")
                return False
                
            return True
        except Exception as e:
            print(f"   -> 发送企业微信机器人任务完成通知失败: {e}")
            return False


class WeChatAppNotifier(BaseNotifier):
    """企业微信应用通知渠道"""
    
    def __init__(self):
        super().__init__("wx_app")
    
    async def send_test_notification(self) -> bool:
        if not config["WX_CORP_ID"] or not config["WX_AGENT_ID"] or not config["WX_SECRET"] or not config["WX_APP_ENABLED"]:
            return False
            
        try:
            # 创建一个模拟商品数据
            mock_product = {
                "商品信息": {
                    "商品标题": "测试商品",
                    "当前售价": "100.00元",
                    "发布时间": "2023-01-01 10:00:00",
                    "商品图片列表": ["https://via.placeholder.com/100"],
                    "商品链接": "https://2.taobao.com/item.htm?id=test12345"
                },
                "ai_analysis": {
                    "reason": "这是一个测试通知，用于验证企业微信应用配置是否正确。\n\n如果您收到这条消息，说明配置已经生效！"
                }
            }
            
            return await self.send_product_notification(mock_product, "测试通知")
        except Exception as e:
            print(f"   -> 发送企业微信应用测试通知失败: {e}")
            return False
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        if not config["WX_CORP_ID"] or not config["WX_AGENT_ID"] or not config["WX_SECRET"] or not config["WX_APP_ENABLED"]:
            return False
            
        try:
            # 获取访问令牌
            access_token = self._get_wecom_access_token()
            if not access_token:
                return False
            
            product_info = self._get_product_info(product)
            actual_product = product_info['actual_product']
            pc_link = product_info['pc_link']
            mobile_link = product_info['mobile_link']
            
            title = actual_product.get('商品标题', '未知商品')
            
            # Extract AI reason from multiple locations
            ai_reason = ""
            ai_analysis = product_info['ai_analysis']
            if ai_analysis:
                ai_reason = ai_analysis.get('reason', '')
            
            if not ai_reason:
                ai_reason = "AI推荐商品，查看详情了解更多"
            
            # Check if there's more detailed analysis available
            ai_analysis = product_info['ai_analysis']
            
            # Include risk tags if available
            risk_tags = ai_analysis.get('risk_tags', [])
            risk_tags_str = ""
            if risk_tags:
                risk_tags_str = f"\n风险标签: {', '.join(risk_tags)}"
            
            # Get criteria analysis if available
            criteria_analysis = ai_analysis.get('criteria_analysis', {})
            
            # Include AI reason in a better format
            if ai_reason:
                content = f"""
价格：{actual_product.get('当前售价', '未知')}
发布时间：{actual_product.get('发布时间', '未知')}

推荐理由：
{ai_reason}
"""
            else:
                content = f"""
价格：{actual_product.get('当前售价', '未知')}
发布时间：{actual_product.get('发布时间', '未知')}

AI推荐商品，查看详情了解更多...
"""
            
            # Convert to mobile link
            link_url = mobile_link
            
            # 构建图文消息内容
            message_data = {
                "touser": config["WX_TO_USER"],
                "msgtype": "news",
                "agentid": config["WX_AGENT_ID"],
                "news": {
                    "articles": [{
                        "title": title,
                        "description": content,
                        "url": link_url,
                        "picurl": product_info['main_image'] or ''
                    }]
                },
                "duplicate_check_interval": 60
            }
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._send_wechat_request(access_token, message_data)
            )
            return True
        except Exception as e:
            print(f"   -> 发送企业微信应用通知失败: {e}")
            return False
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        if not config["WX_CORP_ID"] or not config["WX_AGENT_ID"] or not config["WX_SECRET"] or not config["WX_APP_ENABLED"]:
            return False
        try:
            access_token = self._get_wecom_access_token()
            if not access_token:
                return False
            
            notification_title = "🚀 任务开始"
            message = f"开始了 '{task_name}' 任务 - {reason}"
            
            message_data = {
                "touser": config["WX_TO_USER"],
                "msgtype": "text",
                "agentid": config["WX_AGENT_ID"],
                "text": {
                    "content": message
                },
                "duplicate_check_interval": 60
            }
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._send_wechat_request(access_token, message_data)
            )
            return True
        except Exception as e:
            print(f"   -> 发送企业微信应用任务开始通知失败: {e}")
            return False
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> bool:
        if not config["WX_CORP_ID"] or not config["WX_AGENT_ID"] or not config["WX_SECRET"] or not config["WX_APP_ENABLED"]:
            return False
        try:
            access_token = self._get_wecom_access_token()
            if not access_token:
                return False
            
            notification_title = "✅ 任务完成"
            message = f"结束了 '{task_name}' 任务 - {reason}"
            if processed_count > 0 or recommended_count > 0:
                message += f"\n\n本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。"
            
            message_data = {
                "touser": config["WX_TO_USER"],
                "msgtype": "text",
                "agentid": config["WX_AGENT_ID"],
                "text": {
                    "content": message
                },
                "duplicate_check_interval": 60
            }
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._send_wechat_request(access_token, message_data)
            )
            return True
        except Exception as e:
            print(f"   -> 发送企业微信应用任务完成通知失败: {e}")
            return False
    
    def _get_wecom_access_token(self) -> Optional[str]:
        """
        获取企业微信API访问令牌
        
        Returns:
            Optional[str]: 成功时返回访问令牌，失败返回None
        """
        if not all([config["WX_CORP_ID"], config["WX_SECRET"]]):
            print("错误：未在 .env 文件中完整设置 WX_CORP_ID 和 WX_SECRET")
            return None
            
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={config['WX_CORP_ID']}&corpsecret={config['WX_SECRET']}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") != 0:
                print(f"获取企业微信访问令牌失败: {result.get('errmsg', '未知错误')}")
                return None
                
            return result["access_token"]
            
        except requests.exceptions.RequestException as e:
            print(f"请求企业微信API时发生错误: {e}")
            return None
    
    def _send_wechat_request(self, access_token: str, message_data: dict) -> bool:
        """
        发送企业微信API请求
        
        Returns:
            bool: 成功返回True，失败返回False
        """
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        
        try:
            response = requests.post(url, data=json.dumps(message_data, ensure_ascii=False).encode('utf-8'))
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") != 0:
                print(f"发送微信图文通知失败: {result.get('errmsg', '未知错误')}")
                return False
                
            print(f"微信图文通知已发送")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"发送微信图文通知时发生错误: {e}")
            return False


class TelegramNotifier(BaseNotifier):
    """Telegram通知渠道"""
    
    def __init__(self):
        super().__init__("telegram")
    
    async def send_test_notification(self) -> bool:
        if not config["TELEGRAM_BOT_TOKEN"] or not config["TELEGRAM_CHAT_ID"] or not config["TELEGRAM_ENABLED"]:
            return False
            
        try:
            test_title = "测试通知 - 闲鱼公开内容查看智能处理程序"
            test_message = "这是一个测试通知，用于验证Telegram配置是否正确。\n\n如果您收到这条消息，说明配置已经生效！"
            
            telegram_api_url = f"https://api.telegram.org/bot{config['TELEGRAM_BOT_TOKEN']}/sendMessage"
            
            telegram_message = f"🔔 <b>测试通知!</b>\n\n"
            telegram_message += f"💡 {test_message}"
            
            telegram_payload = {
                "chat_id": config["TELEGRAM_CHAT_ID"],
                "text": telegram_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            
            headers = {"Content-Type": "application/json"}
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    telegram_api_url,
                    json=telegram_payload,
                    headers=headers,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Telegram 测试通知失败: {e}")
            return False
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        if not config["TELEGRAM_BOT_TOKEN"] or not config["TELEGRAM_CHAT_ID"] or not config["TELEGRAM_ENABLED"]:
            return False
            
        try:
            product_info = self._get_product_info(product)
            actual_product = product_info['actual_product']
            pc_link = product_info['pc_link']
            mobile_link = product_info['mobile_link']
            main_image = product_info['main_image']
            
            title = actual_product.get('商品标题', 'N/A')
            price = actual_product.get('当前售价', 'N/A')
            publish_time = actual_product.get('发布时间', 'N/A')
            
            # 选择合适的链接
            product_link = mobile_link if config["PCURL_TO_MOBILE"] else pc_link
            
            # 构建图片描述
            caption = f"🚨 <b>新推荐!</b>\n\n"
            caption += f"<b>{title}</b>\n\n"
            caption += f"💰 价格: {price}\n"
            caption += f"⏰ 发布时间: {publish_time}\n"
            caption += f"📝 推荐理由: {reason}\n"
            
            # 构建 Telegram 图片消息
            telegram_api_url = f"https://api.telegram.org/bot{config['TELEGRAM_BOT_TOKEN']}/sendPhoto"
            
            # 如果有商品图片，发送图片+按钮
            if main_image:
                telegram_payload = {
                    "chat_id": config["TELEGRAM_CHAT_ID"],
                    "photo": main_image,  # 直接使用图片URL
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "查看商品",
                                    "url": product_link
                                }
                            ]
                        ]
                    }
                }
                
                headers = {"Content-Type": "application/json"}
                
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: requests.post(
                        telegram_api_url,
                        json=telegram_payload,
                        headers=headers,
                        timeout=10
                    )
                )
            else:
                # 如果没有商品图片，回退到原来的文本消息格式
                telegram_message = f"🚨 <b>新推荐!</b>\n\n"
                telegram_message += f"<b>{title[:50]}...</b>\n\n"
                telegram_message += f"💰 价格: {price}\n"
                telegram_message += f"📝 原因: {reason}\n"
                
                if config["PCURL_TO_MOBILE"]:
                    telegram_message += f"📱 <a href='{mobile_link}'>手机端链接</a>\n"
                telegram_message += f"💻 <a href='{pc_link}'>电脑端链接</a>"
                
                telegram_payload = {
                    "chat_id": config["TELEGRAM_CHAT_ID"],
                    "text": telegram_message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                }
                
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: requests.post(
                        f"https://api.telegram.org/bot{config['TELEGRAM_BOT_TOKEN']}/sendMessage",
                        json=telegram_payload,
                        headers=headers,
                        timeout=10
                    )
                )
            
            return True
        except Exception as e:
            print(f"   -> 发送 Telegram 通知失败: {e}")
            return False
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        if not config["TELEGRAM_BOT_TOKEN"] or not config["TELEGRAM_CHAT_ID"] or not config["TELEGRAM_ENABLED"]:
            return False
        try:
            telegram_api_url = f"https://api.telegram.org/bot{config['TELEGRAM_BOT_TOKEN']}/sendMessage"
            notification_title = "🚀 任务开始"
            message = f"<b>开始了 '{task_name}' 任务 - {reason}</b>"
            
            telegram_payload = {
                "chat_id": config["TELEGRAM_CHAT_ID"],
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            headers = {"Content-Type": "application/json"}
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    telegram_api_url,
                    json=telegram_payload,
                    headers=headers,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Telegram 任务开始通知失败: {e}")
            return False
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> bool:
        if not config["TELEGRAM_BOT_TOKEN"] or not config["TELEGRAM_CHAT_ID"] or not config["TELEGRAM_ENABLED"]:
            return False
        try:
            telegram_api_url = f"https://api.telegram.org/bot{config['TELEGRAM_BOT_TOKEN']}/sendMessage"
            notification_title = "✅ 任务完成"
            message = f"<b>结束了 '{task_name}' 任务 - {reason}</b>"
            if processed_count > 0 or recommended_count > 0:
                message += f"\n\n本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。"
            
            telegram_payload = {
                "chat_id": config["TELEGRAM_CHAT_ID"],
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            headers = {"Content-Type": "application/json"}
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    telegram_api_url,
                    json=telegram_payload,
                    headers=headers,
                    timeout=10
                )
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Telegram 任务完成通知失败: {e}")
            return False


class WebhookNotifier(BaseNotifier):
    """Webhook通知渠道"""
    
    def __init__(self):
        super().__init__("webhook")
    
    async def send_test_notification(self) -> bool:
        if not config["WEBHOOK_URL"] or not config["WEBHOOK_ENABLED"]:
            return False
            
        try:
            test_title = "测试通知 - 闲鱼公开内容查看智能处理程序"
            test_message = "这是一个测试通知，用于验证Webhook配置是否正确。\n\n如果您收到这条消息，说明配置已经生效！"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._send_webhook_request(test_title, test_message)
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Webhook 测试通知失败: {e}")
            return False
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        if not config["WEBHOOK_URL"] or not config["WEBHOOK_ENABLED"]:
            return False
            
        try:
            product_info = self._get_product_info(product)
            notification_title, message = self._format_notification_content(product_info, reason)
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._send_webhook_request(notification_title, message)
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Webhook 通知失败: {e}")
            return False
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        if not config["WEBHOOK_URL"] or not config["WEBHOOK_ENABLED"]:
            return False
        try:
            notification_title = "🚀 任务开始"
            message = f"开始了 '{task_name}' 任务 - {reason}"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._send_webhook_request(notification_title, message)
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Webhook 任务开始通知失败: {e}")
            return False
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> bool:
        if not config["WEBHOOK_URL"] or not config["WEBHOOK_ENABLED"]:
            return False
        try:
            notification_title = "✅ 任务完成"
            message = f"结束了 '{task_name}' 任务 - {reason}"
            if processed_count > 0 or recommended_count > 0:
                message += f"\n\n本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。"
            
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._send_webhook_request(notification_title, message)
            )
            return True
        except Exception as e:
            print(f"   -> 发送 Webhook 任务完成通知失败: {e}")
            return False
    
    def _send_webhook_request(self, title: str, content: str) -> None:
        """发送Webhook请求"""
        from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
        
        headers = config["WEBHOOK_HEADERS"].copy()
        final_url = config["WEBHOOK_URL"]
        
        if config["WEBHOOK_METHOD"] == "GET":
            if config["WEBHOOK_QUERY_PARAMETERS"]:
                try:
                    params_str = self._replace_placeholders(config["WEBHOOK_QUERY_PARAMETERS"], title, content)
                    params = json.loads(params_str)
                    
                    url_parts = list(urlparse(final_url))
                    query = dict(parse_qsl(url_parts[4]))
                    query.update(params)
                    url_parts[4] = urlencode(query)
                    final_url = urlunparse(url_parts)
                except json.JSONDecodeError:
                    print(f"   -> [警告] Webhook 查询参数格式错误，请检查 .env 中的 WEBHOOK_QUERY_PARAMETERS。")
            
            requests.get(final_url, headers=headers, timeout=15)
        
        elif config["WEBHOOK_METHOD"] == "POST":
            data = None
            json_payload = None
            
            if config["WEBHOOK_BODY"]:
                body_str = self._replace_placeholders(config["WEBHOOK_BODY"], title, content)
                try:
                    if config["WEBHOOK_CONTENT_TYPE"] == "JSON":
                        json_payload = json.loads(body_str)
                        if 'Content-Type' not in headers and 'content-type' not in headers:
                            headers['Content-Type'] = 'application/json; charset=utf-8'
                    elif config["WEBHOOK_CONTENT_TYPE"] == "FORM":
                        data = json.loads(body_str)
                        if 'Content-Type' not in headers and 'content-type' not in headers:
                            headers['Content-Type'] = 'application/x-www-form-urlencoded'
                    else:
                        print(f"   -> [警告] 不支持的 WEBHOOK_CONTENT_TYPE: {config['WEBHOOK_CONTENT_TYPE']}。")
                except json.JSONDecodeError:
                    print(f"   -> [警告] Webhook 请求体格式错误，请检查 .env 中的 WEBHOOK_BODY。")
            
            requests.post(final_url, headers=headers, json=json_payload, data=data, timeout=15)


class DingTalkNotifier(BaseNotifier):
    """钉钉机器人通知渠道"""
    
    def __init__(self):
        super().__init__("dingtalk")
    
    def _get_signed_url(self) -> str:
        """
        获取带签名的钉钉Webhook URL
        如果配置了SECRET，则使用HMAC-SHA256签名
        """
        import time
        import hmac
        import hashlib
        import base64
        import urllib.parse
        
        webhook_url = config["DINGTALK_WEBHOOK"]
        secret = config.get("DINGTALK_SECRET", "")
        
        if secret:
            timestamp = str(round(time.time() * 1000))
            secret_enc = secret.encode('utf-8')
            string_to_sign = f'{timestamp}\n{secret}'
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            return f"{webhook_url}&timestamp={timestamp}&sign={sign}"
        
        return webhook_url
    
    async def send_test_notification(self) -> bool:
        if not config["DINGTALK_WEBHOOK"] or not config["DINGTALK_ENABLED"]:
            return False
            
        try:
            test_title = "测试通知 - 闲鱼公开内容查看智能处理程序"
            test_message = "这是一个测试通知，用于验证钉钉机器人配置是否正确。\n\n如果您收到这条消息，说明配置已经生效！"
            
            # 使用ActionCard图文卡片格式
            payload = {
                "msgtype": "actionCard",
                "actionCard": {
                    "title": test_title,
                    "text": f"### {test_title}\n\n{test_message}",
                    "btnOrientation": "0",
                    "singleTitle": "查看管理后台",
                    "singleURL": "http://127.0.0.1:8791"
                }
            }
            
            headers = {"Content-Type": "application/json; charset=utf-8"}
            url = self._get_signed_url()
            
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            )
            
            result = response.json()
            if result.get("errcode") == 0:
                print("   -> 钉钉测试通知发送成功")
                return True
            else:
                print(f"   -> 钉钉发送通知失败: errcode={result.get('errcode')}, errmsg={result.get('errmsg')}")
                return False
        except Exception as e:
            print(f"   -> 发送钉钉测试通知异常: {e}")
            return False
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        if not config["DINGTALK_WEBHOOK"] or not config["DINGTALK_ENABLED"]:
            return False
            
        try:
            product_info = self._get_product_info(product)
            actual_product = product_info['actual_product']
            pc_link = product_info['pc_link']
            mobile_link = product_info['mobile_link']
            main_image = product_info['main_image']
            
            title = actual_product.get('商品标题', '未知商品')
            price = actual_product.get('当前售价', '未知价格')
            publish_time = actual_product.get('发布时间', '未知时间')
            
            # 选择合适的链接
            product_link = mobile_link if config["PCURL_TO_MOBILE"] else pc_link
            
            # 构建Markdown内容
            markdown_text = f"### 🚨 新推荐商品\n\n"
            markdown_text += f"**{title}**\n\n"
            markdown_text += f"💰 价格: {price}\n\n"
            markdown_text += f"⏰ 发布时间: {publish_time}\n\n"
            markdown_text += f"📝 推荐理由: {reason}\n\n"
            
            if main_image:
                markdown_text += f"![商品图片]({main_image})\n\n"
            
            # 使用ActionCard图文卡片格式，点击跳转商品链接
            payload = {
                "msgtype": "actionCard",
                "actionCard": {
                    "title": f"🚨 {title[:30]}...",
                    "text": markdown_text,
                    "btnOrientation": "0",
                    "singleTitle": "查看商品详情 >>",
                    "singleURL": product_link
                }
            }
            
            headers = {"Content-Type": "application/json; charset=utf-8"}
            url = self._get_signed_url()
            
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            )
            
            result = response.json()
            if result.get("errcode") == 0:
                print("   -> 钉钉商品通知发送成功")
                return True
            else:
                print(f"   -> 钉钉发送商品通知失败: errcode={result.get('errcode')}, errmsg={result.get('errmsg')}")
                return False
        except Exception as e:
            print(f"   -> 发送钉钉商品通知异常: {e}")
            return False
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        if not config["DINGTALK_WEBHOOK"] or not config["DINGTALK_ENABLED"]:
            return False
        try:
            notification_title = "🚀 任务开始"
            message = f"开始了 '{task_name}' 任务 - {reason}"
            
            # 使用Markdown格式
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": notification_title,
                    "text": f"### {notification_title}\n\n{message}"
                }
            }
            
            headers = {"Content-Type": "application/json; charset=utf-8"}
            url = self._get_signed_url()
            
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            )
            
            result = response.json()
            if result.get("errcode") == 0:
                print("   -> 钉钉任务开始通知发送成功")
                return True
            else:
                print(f"   -> 钉钉发送任务开始通知失败: errcode={result.get('errcode')}, errmsg={result.get('errmsg')}")
                return False
        except Exception as e:
            print(f"   -> 发送钉钉任务开始通知异常: {e}")
            return False
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> bool:
        if not config["DINGTALK_WEBHOOK"] or not config["DINGTALK_ENABLED"]:
            return False
        try:
            notification_title = "✅ 任务完成"
            message = f"结束了 '{task_name}' 任务 - {reason}"
            if processed_count > 0 or recommended_count > 0:
                message += f"\n\n本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。"
            
            # 使用Markdown格式
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": notification_title,
                    "text": f"### {notification_title}\n\n{message}"
                }
            }
            
            headers = {"Content-Type": "application/json; charset=utf-8"}
            url = self._get_signed_url()
            
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            )
            
            result = response.json()
            if result.get("errcode") == 0:
                print("   -> 钉钉任务完成通知发送成功")
                return True
            else:
                print(f"   -> 钉钉发送任务完成通知失败: errcode={result.get('errcode')}, errmsg={result.get('errmsg')}")
                return False
        except Exception as e:
            print(f"   -> 发送钉钉任务完成通知异常: {e}")
            return False
