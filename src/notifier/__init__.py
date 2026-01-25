import asyncio
from typing import Dict, Any, Optional, List

from src.notifier.channels import (
    NtfyNotifier,
    GotifyNotifier,
    BarkNotifier,
    WeChatBotNotifier,
    WeChatAppNotifier,
    TelegramNotifier,
    WebhookNotifier,
    DingTalkNotifier
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
            "webhook": WebhookNotifier(),
            "dingtalk": DingTalkNotifier()
        }
        
        # 渠道名称映射，用于统一显示
        self.channel_name_map = {
            "ntfy": "Ntfy",
            "gotify": "Gotify", 
            "bark": "Bark",
            "wx_bot": "企业微信机器人",
            "wx_app": "企业微信应用",
            "telegram": "Telegram",
            "webhook": "Webhook",
            "dingtalk": "钉钉机器人"
        }
    
    async def send_test_notification(self, channel: str) -> bool:
        """
        发送测试通知到指定渠道
        
        Args:
            channel (str): 渠道名称
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
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
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
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
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
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
    
    async def send_task_start_notification(self, task_name: str, reason: str) -> Dict[str, bool]:
        """
        发送任务开始通知到所有配置的渠道
        
        Returns:
            Dict[str, bool]: 各渠道发送结果
        """
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
        tasks = []
        
        # 创建所有渠道的通知任务
        for channel_name, notifier in self.channels.items():
            tasks.append(self._run_task_start_notification(channel_name, notifier, task_name, reason))
        
        # 并发执行所有通知任务
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        result_dict = {}
        for channel_name, success in results:
            display_name = self.channel_name_map.get(channel_name, channel_name)
            result_dict[display_name] = success
        
        return result_dict
    
    async def _run_task_start_notification(self, channel_name: str, notifier, task_name: str, reason: str) -> tuple:
        """运行单个渠道的任务开始通知"""
        try:
            success = await notifier.send_task_start_notification(task_name, reason)
            return (channel_name, success)
        except Exception as e:
            print(f"   -> 发送 {channel_name} 任务开始通知失败: {e}")
            return (channel_name, False)

    def _format_task_end_reason(self, reason: str) -> str:
        if not reason:
            return "未知原因"
        mapping = {
            "RISK_CONTROL:FAIL_SYS_USER_VALIDATE": "触发风控：系统验证（FAIL_SYS_USER_VALIDATE）",
            "RISK_CONTROL:BAXIA_DIALOG": "触发风控：页面验证弹窗（baxia-dialog）",
            "RISK_CONTROL:MIDDLEWARE_WIDGET": "触发风控：页面验证弹窗（J_MIDDLEWARE_FRAME_WIDGET）",
        }
        if reason in mapping:
            return mapping[reason]
        if reason.startswith("RISK_CONTROL:"):
            return f"触发风控：{reason.replace('RISK_CONTROL:', '')}"
        if reason.startswith("AI_CALL_FAILURE:"):
            return f"AI调用失败：{reason.replace('AI_CALL_FAILURE:', '').strip()}"
        return reason
    
    async def send_task_completion_notification(self, task_name: str, reason: str, processed_count: int = 0, recommended_count: int = 0) -> Dict[str, bool]:
        """
        发送任务完成通知到所有配置的渠道
        
        Returns:
            Dict[str, bool]: 各渠道发送结果
        """
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
        # 检查是否启用任务完成后通知
        if not notifier_config.get("NOTIFY_AFTER_TASK_COMPLETE", True):
            # 如果未启用，直接返回空结果
            print(f"任务完成通知已被禁用，跳过发送任务 '{task_name}' 的完成通知")
            return {}
        
        tasks = []
        reason = self._format_task_end_reason(reason)
        
        # 创建所有渠道的通知任务
        for channel_name, notifier in self.channels.items():
            tasks.append(self._run_task_completion_notification(channel_name, notifier, task_name, reason, processed_count, recommended_count))
        
        # 并发执行所有通知任务
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        result_dict = {}
        for channel_name, success in results:
            display_name = self.channel_name_map.get(channel_name, channel_name)
            result_dict[display_name] = success
        
        return result_dict
    
    async def _run_task_completion_notification(self, channel_name: str, notifier, task_name: str, reason: str, processed_count: int, recommended_count: int) -> tuple:
        """运行单个渠道的任务完成通知"""
        try:
            success = await notifier.send_task_completion_notification(task_name, reason, processed_count, recommended_count)
            return (channel_name, success)
        except Exception as e:
            print(f"   -> 发送 {channel_name} 任务完成通知失败: {e}")
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
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
        if channel not in self.channels:
            print(f"未知的通知渠道: {channel}")
            return False
        elif hasattr(self.channels[channel], 'send_product_notification'):
            return await self.channels[channel].send_product_notification(product, reason)
        elif hasattr(self.channels[channel], 'send_product_notification'):
            # 向后兼容，考虑到可能有不同的方法名称
            return await self.channels[channel].send_product_notification(product, reason)
        else:
            print(f"渠道 '{channel}' 不支持产品通知")
            return False
    
    async def send_test_product_notification(self, channel: str) -> bool:
        """
        发送商品卡测试通知
        
        Args:
            channel (str): 渠道名称
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
        if channel not in self.channels:
            print(f"未知的通知渠道: {channel}")
            return False
        elif hasattr(self.channels[channel], 'send_product_notification'):
            # 创建测试用的商品数据
            test_product = {
                "商品信息": {
                    "商品标题": "测试商品",
                    "当前售价": "100.00元", 
                    "发布时间": "2023-01-01 10:00:00",
                    "商品图片列表": ["https://via.placeholder.com/100"],
                    "商品链接": "https://2.taobao.com/item.htm?id=test12345"
                },
                "ai_analysis": {
                    "reason": "这是一个测试商品，用于验证商品卡通知配置是否正确"
                }
            }
            return await self.channels[channel].send_product_notification(test_product, "测试商品推荐")
        else:
            print(f"渠道 '{channel}' 不支持商品通知")
            return False
    
    async def send_test_task_start_notification(self, channel: str) -> bool:
        """
        发送任务开始通知的测试
        
        Args:
            channel (str): 渠道名称
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
        if channel not in self.channels:
            print(f"未知的通知渠道: {channel}")
            return False
        elif hasattr(self.channels[channel], 'send_task_start_notification'):
            return await self.channels[channel].send_task_start_notification(
                "测试任务", "手动开始"
            )
        else:
            print(f"渠道 '{channel}' 不支持任务开始通知")
            return False
    
    async def send_test_task_start_notifications(self) -> Dict[str, bool]:
        """
        发送任务开始通知测试到所有配置的渠道
        
        Returns:
            Dict[str, bool]: 各渠道发送结果
        """
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
        tasks = []
        
        # 创建所有渠道的测试任务
        for channel_name, notifier in self.channels.items():
            if hasattr(notifier, 'send_task_start_notification'):
                tasks.append(self._run_test_task_start_notification(channel_name, notifier))
        
        # 并发执行所有测试任务
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        result_dict = {}
        for channel_name, success in results:
            display_name = self.channel_name_map.get(channel_name, channel_name)
            result_dict[display_name] = success
        
        return result_dict
    
    async def _run_test_task_start_notification(self, channel_name: str, notifier) -> tuple:
        """运行单个渠道的任务开始通知测试"""
        try:
            success = await notifier.send_task_start_notification(
                "测试任务", "手动开始"
            )
            return (channel_name, success)
        except Exception as e:
            print(f"   -> 发送 {channel_name} 任务开始通知测试失败: {e}")
            return (channel_name, False)
    
    async def send_test_task_completion_notification(self, channel: str) -> bool:
        """
        发送任务完成通知的测试
        
        Args:
            channel (str): 渠道名称
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
        if channel not in self.channels:
            print(f"未知的通知渠道: {channel}")
            return False
        elif hasattr(self.channels[channel], 'send_task_completion_notification'):
            return await self.channels[channel].send_task_completion_notification(
                "测试任务", "自动结束-结束原因：完成了全部设置商品分析", 10, 3
            )
        else:
            print(f"渠道 '{channel}' 不支持任务完成通知")
            return False
    
    async def send_test_task_completion_notifications(self) -> Dict[str, bool]:
        """
        发送任务完成通知测试到所有配置的渠道
        
        Returns:
            Dict[str, bool]: 各渠道发送结果
        """
        # 重新加载配置，确保使用最新的通知开关设置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
        tasks = []
        
        # 创建所有渠道的测试任务
        for channel_name, notifier in self.channels.items():
            if hasattr(notifier, 'send_task_completion_notification'):
                tasks.append(self._run_test_task_completion_notification(channel_name, notifier))
        
        # 并发执行所有测试任务
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        result_dict = {}
        for channel_name, success in results:
            display_name = self.channel_name_map.get(channel_name, channel_name)
            result_dict[display_name] = success
        
        return result_dict
    
    async def _run_test_task_completion_notification(self, channel_name: str, notifier) -> tuple:
        """运行单个渠道的任务完成通知测试"""
        try:
            success = await notifier.send_task_completion_notification(
                "测试任务", "自动结束-结束原因：完成了全部设置商品分析", 10, 3
            )
            return (channel_name, success)
        except Exception as e:
            print(f"   -> 发送 {channel_name} 任务完成通知测试失败: {e}")
            return (channel_name, False)
    
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
        # 重新加载配置，确保使用最新的通知配置
        from src.notifier.config import config as notifier_config
        notifier_config.reload()
        
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
            },
            "dingtalk": {
                "configured": bool(config["DINGTALK_WEBHOOK"]),
                "name": "钉钉机器人"
            }
        }


# 创建单例实例
notifier = Notifier()
