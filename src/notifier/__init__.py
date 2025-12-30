import asyncio
from typing import Dict, Any, Optional, List

from src.notifier.channels import (
    NtfyNotifier,
    GotifyNotifier,
    BarkNotifier,
    WeChatBotNotifier,
    WeChatAppNotifier,
    TelegramNotifier,
    WebhookNotifier
)
from src.notifier.config import config


class Notifier:
    """统一通知接口"""
    
    def __init__(self):
        # 初始化所有通知渠道
        self.channels = {
            "ntfy": NtfyNotifier(),
            "gotify": GotifyNotifier(),
            "bark": BarkNotifier(),
            "wx_bot": WeChatBotNotifier(),
            "wx_app": WeChatAppNotifier(),
            "telegram": TelegramNotifier(),
            "webhook": WebhookNotifier()
        }
        
        # 渠道名称映射，用于统一显示
        self.channel_name_map = {
            "ntfy": "Ntfy",
            "gotify": "Gotify", 
            "bark": "Bark",
            "wx_bot": "企业微信机器人",
            "wx_app": "企业微信应用",
            "telegram": "Telegram",
            "webhook": "Webhook"
        }
    
    async def send_test_notification(self, channel: str) -> bool:
        """
        发送测试通知到指定渠道
        
        Args:
            channel (str): 渠道名称
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        if channel not in self.channels:
            print(f"未知的通知渠道: {channel}")
            return False
            
        return await self.channels[channel].send_test_notification()
    
    async def send_test_notifications(self) -> Dict[str, bool]:
        """
        发送测试通知到所有配置的渠道
        
        Returns:
            Dict[str, bool]: 各渠道发送结果
        """
        tasks = []
        
        # 创建所有渠道的测试任务
        for channel_name, notifier in self.channels.items():
            tasks.append(self._run_test_notification(channel_name, notifier))
        
        # 并发执行所有测试任务
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        result_dict = {}
        for channel_name, success in results:
            display_name = self.channel_name_map.get(channel_name, channel_name)
            result_dict[display_name] = success
        
        return result_dict
    
    async def _run_test_notification(self, channel_name: str, notifier) -> tuple:
        """运行单个渠道的测试通知"""
        try:
            success = await notifier.send_test_notification()
            return (channel_name, success)
        except Exception as e:
            print(f"   -> 发送 {channel_name} 测试通知失败: {e}")
            return (channel_name, False)
    
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> Dict[str, bool]:
        """
        发送产品通知到所有配置的渠道
        
        Returns:
            Dict[str, bool]: 各渠道发送结果
        """
        tasks = []
        
        # 创建所有渠道的通知任务
        for channel_name, notifier in self.channels.items():
            tasks.append(self._run_product_notification(channel_name, notifier, product, reason))
        
        # 并发执行所有通知任务
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        result_dict = {}
        for channel_name, success in results:
            display_name = self.channel_name_map.get(channel_name, channel_name)
            result_dict[display_name] = success
        
        return result_dict
    
    async def _run_product_notification(self, channel_name: str, notifier, product: Dict[str, Any], reason: str) -> tuple:
        """运行单个渠道的产品通知"""
        try:
            success = await notifier.send_product_notification(product, reason)
            return (channel_name, success)
        except Exception as e:
            print(f"   -> 发送 {channel_name} 通知失败: {e}")
            return (channel_name, False)
    
    async def send_to_channel(self, channel: str, product: Dict[str, Any], reason: str) -> bool:
        """
        发送产品通知到特定渠道
        
        Args:
            channel (str): 渠道名称
            product (Dict[str, Any]): 产品数据
            reason (str): 推荐理由
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        if channel not in self.channels:
            print(f"未知的通知渠道: {channel}")
            return False
            
        return await self.channels[channel].send_product_notification(product, reason)
    
    def list_configured_channels(self) -> List[str]:
        """
        获取所有配置了的通知渠道
        
        Returns:
            List[str]: 配置了的渠道列表
        """
        configured_channels = []
        
        for channel, channel_config in self._get_channel_configurations().items():
            if channel_config["configured"]:
                configured_channels.append(channel)
        
        return configured_channels
    
    def _get_channel_configurations(self) -> Dict[str, Dict[str, Any]]:
        """
        获取各渠道的配置状态
        
        Returns:
            Dict[str, Dict[str, Any]]: 各渠道的配置状态
        """
        return {
            "ntfy": {
                "configured": bool(config["NTFY_TOPIC_URL"]),
                "name": "Ntfy"
            },
            "gotify": {
                "configured": bool(config["GOTIFY_URL"] and config["GOTIFY_TOKEN"]),
                "name": "Gotify"
            },
            "bark": {
                "configured": bool(config["BARK_URL"]),
                "name": "Bark"
            },
            "wx_bot": {
                "configured": bool(config["WX_BOT_URL"]),
                "name": "企业微信机器人"
            },
            "wx_app": {
                "configured": bool(config["WX_CORP_ID"] and config["WX_AGENT_ID"] and config["WX_SECRET"]),
                "name": "企业微信应用"
            },
            "telegram": {
                "configured": bool(config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]),
                "name": "Telegram"
            },
            "webhook": {
                "configured": bool(config["WEBHOOK_URL"]),
                "name": "Webhook"
            }
        }


# 创建单例实例
notifier = Notifier()
