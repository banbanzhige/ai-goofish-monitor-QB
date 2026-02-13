import asyncio
import json
import os
from typing import Dict, Any, Optional, List

from src.config import STORAGE_BACKEND
from src.logging_config import get_logger
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
from src.storage import get_storage


logger = get_logger(__name__, service="notifier")


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
def _notifier_is_postgres_mode() -> bool:
    """判断是否处于多用户数据库模式。"""
    return STORAGE_BACKEND() == "postgres"


def _notifier_normalize_text(value: Any) -> str:
    """将输入值规范化为去空白字符串。"""
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _notifier_to_bool(value: Any, default: bool = False) -> bool:
    """将输入值转换为布尔值。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _notifier_normalize_text(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _notifier_parse_headers(value: Any) -> Dict[str, str]:
    """解析 Webhook headers，确保返回字典。"""
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return {}
        try:
            payload = json.loads(value)
            if isinstance(payload, dict):
                return {str(k): str(v) for k, v in payload.items()}
        except Exception:
            return {}
    return {}


def _notifier_resolve_owner_id(owner_id: Optional[str] = None) -> Optional[str]:
    """解析当前通知请求归属的用户ID。"""
    if owner_id:
        normalized = _notifier_normalize_text(owner_id)
        if normalized:
            return normalized
    env_owner_id = _notifier_normalize_text(os.getenv("GOOFISH_OWNER_ID", ""))
    return env_owner_id or None


def _notifier_resolve_bound_task(
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
) -> Optional[str]:
    """解析当前通知请求绑定的任务标识（兼容历史 bound_account 参数）。"""
    if bound_task:
        normalized = _notifier_normalize_text(bound_task)
        if normalized:
            return normalized
    if bound_account:
        normalized = _notifier_normalize_text(bound_account)
        if normalized:
            return normalized
    return None


def _notifier_extract_bound_task(config_payload: Dict[str, Any]) -> str:
    """从配置内容中提取绑定任务标识（兼容旧绑定账号字段）。"""
    binding = (
        config_payload.get("bound_task")
        or config_payload.get("bound_task_name")
        or config_payload.get("task_name")
        or config_payload.get("bound_account")
        or config_payload.get("bound_account_name")
        or config_payload.get("account_name")
        or config_payload.get("platform_account")
    )
    return _notifier_normalize_text(binding)


def _notifier_build_overrides(channel: str, raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """把用户通知配置转换为渠道运行时配置键。"""
    cfg = raw_config if isinstance(raw_config, dict) else {}
    overrides: Dict[str, Any] = {}

    if "pcurl_to_mobile" in cfg:
        overrides["PCURL_TO_MOBILE"] = _notifier_to_bool(cfg.get("pcurl_to_mobile"), default=True)
    if "notify_after_task_complete" in cfg:
        overrides["NOTIFY_AFTER_TASK_COMPLETE"] = _notifier_to_bool(cfg.get("notify_after_task_complete"), default=True)

    if channel == "ntfy":
        overrides.update(
            {
                "NTFY_ENABLED": True,
                "NTFY_TOPIC_URL": _notifier_normalize_text(
                    cfg.get("topic_url") or cfg.get("ntfy_topic_url") or cfg.get("url")
                ),
            }
        )
    elif channel == "gotify":
        overrides.update(
            {
                "GOTIFY_ENABLED": True,
                "GOTIFY_URL": _notifier_normalize_text(cfg.get("url") or cfg.get("gotify_url")),
                "GOTIFY_TOKEN": _notifier_normalize_text(cfg.get("token") or cfg.get("gotify_token")),
            }
        )
    elif channel == "bark":
        overrides.update(
            {
                "BARK_ENABLED": True,
                "BARK_URL": _notifier_normalize_text(cfg.get("url") or cfg.get("bark_url")),
            }
        )
    elif channel == "wx_bot":
        overrides.update(
            {
                "WX_BOT_ENABLED": True,
                "WX_BOT_URL": _notifier_normalize_text(cfg.get("url") or cfg.get("wx_bot_url")),
            }
        )
    elif channel == "wx_app":
        overrides.update(
            {
                "WX_APP_ENABLED": True,
                "WX_CORP_ID": _notifier_normalize_text(cfg.get("corp_id") or cfg.get("wx_corp_id")),
                "WX_AGENT_ID": _notifier_normalize_text(cfg.get("agent_id") or cfg.get("wx_agent_id")),
                "WX_SECRET": _notifier_normalize_text(cfg.get("secret") or cfg.get("wx_secret")),
                "WX_TO_USER": _notifier_normalize_text(cfg.get("to_user") or cfg.get("wx_to_user") or "@all"),
            }
        )
    elif channel == "telegram":
        overrides.update(
            {
                "TELEGRAM_ENABLED": True,
                "TELEGRAM_BOT_TOKEN": _notifier_normalize_text(cfg.get("bot_token") or cfg.get("telegram_bot_token")),
                "TELEGRAM_CHAT_ID": _notifier_normalize_text(cfg.get("chat_id") or cfg.get("telegram_chat_id")),
            }
        )
    elif channel == "webhook":
        method = _notifier_normalize_text(cfg.get("method") or cfg.get("webhook_method") or "POST").upper()
        content_type = _notifier_normalize_text(
            cfg.get("content_type") or cfg.get("webhook_content_type") or "JSON"
        ).upper()
        overrides.update(
            {
                "WEBHOOK_ENABLED": True,
                "WEBHOOK_URL": _notifier_normalize_text(cfg.get("url") or cfg.get("webhook_url")),
                "WEBHOOK_METHOD": method if method in {"POST", "GET"} else "POST",
                "WEBHOOK_HEADERS": _notifier_parse_headers(cfg.get("headers") or cfg.get("webhook_headers")),
                "WEBHOOK_CONTENT_TYPE": content_type if content_type in {"JSON", "FORM"} else "JSON",
                "WEBHOOK_QUERY_PARAMETERS": _notifier_normalize_text(
                    cfg.get("query_parameters") or cfg.get("webhook_query_parameters")
                ),
                "WEBHOOK_BODY": _notifier_normalize_text(cfg.get("body") or cfg.get("webhook_body")),
            }
        )
    elif channel == "dingtalk":
        overrides.update(
            {
                "DINGTALK_ENABLED": True,
                "DINGTALK_WEBHOOK": _notifier_normalize_text(cfg.get("webhook") or cfg.get("dingtalk_webhook")),
                "DINGTALK_SECRET": _notifier_normalize_text(cfg.get("secret") or cfg.get("dingtalk_secret")),
            }
        )

    return overrides


def _notifier_load_user_targets(
    self,
    owner_id: str,
    event_type: str,
    channel: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
    config_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """加载用户生效的通知配置目标列表。"""
    try:
        storage = get_storage()
        user_configs = storage.get_user_notification_configs(owner_id)
    except Exception as exc:
        logger.error(
            "读取用户通知配置失败",
            extra={"event": "user_notification_config_load_failed", "owner_id": owner_id},
            exc_info=exc,
        )
        return []

    normalized_channel = _notifier_normalize_text(channel)
    normalized_bound_task = _notifier_normalize_text(bound_task) or _notifier_normalize_text(bound_account)
    normalized_config_id = _notifier_normalize_text(config_id)
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for item in user_configs:
        item_channel = _notifier_normalize_text(item.get("channel_type"))
        if item_channel not in self.channels:
            continue
        if normalized_channel and item_channel != normalized_channel:
            continue
        if normalized_config_id and _notifier_normalize_text(item.get("id")) != normalized_config_id:
            continue

        if not normalized_config_id and not _notifier_to_bool(item.get("is_enabled"), default=True):
            continue
        if event_type == "product" and not normalized_config_id and not _notifier_to_bool(item.get("notify_on_recommend"), default=True):
            continue
        if event_type == "task_completion" and not normalized_config_id and not _notifier_to_bool(item.get("notify_on_complete"), default=True):
            continue

        item_config = item.get("config") if isinstance(item.get("config"), dict) else {}
        item_bound_task = _notifier_extract_bound_task(item_config)
        bucket = grouped.setdefault(item_channel, {"exact": [], "default": []})

        if normalized_config_id:
            bucket["exact"].append(item)
            continue

        if normalized_bound_task:
            if item_bound_task and item_bound_task == normalized_bound_task:
                bucket["exact"].append(item)
            elif not item_bound_task:
                bucket["default"].append(item)
        else:
            if not item_bound_task:
                bucket["default"].append(item)

    targets: List[Dict[str, Any]] = []
    for item_channel, bucket in grouped.items():
        selected = bucket["exact"] if bucket["exact"] else bucket["default"]
        for item in selected:
            item_config = item.get("config") if isinstance(item.get("config"), dict) else {}
            target_name = _notifier_normalize_text(item.get("name")) or self.channel_name_map.get(item_channel, item_channel)
            targets.append(
                {
                    "channel": item_channel,
                    "display_name": self.channel_name_map.get(item_channel, item_channel),
                    "target_name": target_name,
                    "config_id": _notifier_normalize_text(item.get("id")),
                    "overrides": _notifier_build_overrides(item_channel, item_config),
                }
            )

    return targets


def _notifier_build_local_targets(self, channel: Optional[str] = None) -> List[Dict[str, Any]]:
    """构造本地模式下的通知目标列表。"""
    targets: List[Dict[str, Any]] = []
    if channel:
        target_channel = _notifier_normalize_text(channel)
        if target_channel in self.channels:
            targets.append(
                {
                    "channel": target_channel,
                    "display_name": self.channel_name_map.get(target_channel, target_channel),
                    "target_name": self.channel_name_map.get(target_channel, target_channel),
                    "config_id": "",
                    "overrides": None,
                }
            )
        return targets

    for item_channel in self.channels.keys():
        targets.append(
            {
                "channel": item_channel,
                "display_name": self.channel_name_map.get(item_channel, item_channel),
                "target_name": self.channel_name_map.get(item_channel, item_channel),
                "config_id": "",
                "overrides": None,
            }
        )
    return targets


async def _notifier_dispatch_targets(
    self,
    targets: List[Dict[str, Any]],
    method_name: str,
    *args: Any,
) -> Dict[str, bool]:
    """并发发送通知并按渠道聚合结果。"""

    async def _run_target(target: Dict[str, Any]) -> tuple[str, bool]:
        channel_name = target.get("channel")
        notifier_impl = self.channels.get(channel_name)
        if not notifier_impl:
            return target.get("display_name") or str(channel_name), False

        try:
            if target.get("overrides"):
                with config.apply_overrides(target["overrides"]):
                    success = await getattr(notifier_impl, method_name)(*args)
            else:
                success = await getattr(notifier_impl, method_name)(*args)
            return target.get("display_name") or str(channel_name), bool(success)
        except Exception as exc:
            logger.error(
                "通知发送失败",
                extra={
                    "event": "notification_dispatch_failed",
                    "channel": channel_name,
                    "target_name": target.get("target_name"),
                    "config_id": target.get("config_id"),
                    "method_name": method_name,
                },
                exc_info=exc,
            )
            return target.get("display_name") or str(channel_name), False

    results = await asyncio.gather(*[_run_target(target) for target in targets]) if targets else []
    merged: Dict[str, bool] = {}
    for display_name, success in results:
        merged[display_name] = merged.get(display_name, True) and bool(success)
    return merged


async def _notifier_send_test_notification(
    self,
    channel: str,
    owner_id: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
    config_id: Optional[str] = None,
) -> bool:
    """发送单渠道测试通知。"""
    if channel not in self.channels:
        return False

    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(owner_id)
        if not resolved_owner:
            logger.warning("多用户模式发送测试通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return False
        targets = _notifier_load_user_targets(
            self,
            resolved_owner,
            event_type="test",
            channel=channel,
            bound_task=_notifier_resolve_bound_task(bound_task, bound_account),
            config_id=config_id,
        )
        if not targets:
            return False
        result = await _notifier_dispatch_targets(self, targets, "send_test_notification")
        display_name = self.channel_name_map.get(channel, channel)
        return bool(result.get(display_name))

    config.reload()
    target = _notifier_build_local_targets(self, channel=channel)
    result = await _notifier_dispatch_targets(self, target, "send_test_notification")
    display_name = self.channel_name_map.get(channel, channel)
    return bool(result.get(display_name))


async def _notifier_send_test_notifications(self) -> Dict[str, bool]:
    """发送所有渠道测试通知。"""
    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(None)
        if not resolved_owner:
            logger.warning("多用户模式批量测试通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return {}
        targets = _notifier_load_user_targets(self, resolved_owner, event_type="test")
        return await _notifier_dispatch_targets(self, targets, "send_test_notification")

    config.reload()
    targets = _notifier_build_local_targets(self)
    return await _notifier_dispatch_targets(self, targets, "send_test_notification")


async def _notifier_send_product_notification(
    self,
    product: Dict[str, Any],
    reason: str,
    owner_id: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
) -> Dict[str, bool]:
    """发送商品推荐通知。"""
    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(owner_id)
        if not resolved_owner:
            logger.warning("多用户模式发送商品通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return {}
        targets = _notifier_load_user_targets(
            self,
            resolved_owner,
            event_type="product",
            bound_task=_notifier_resolve_bound_task(bound_task, bound_account),
        )
        return await _notifier_dispatch_targets(self, targets, "send_product_notification", product, reason)

    config.reload()
    targets = _notifier_build_local_targets(self)
    return await _notifier_dispatch_targets(self, targets, "send_product_notification", product, reason)


async def _notifier_send_task_start_notification(
    self,
    task_name: str,
    reason: str,
    owner_id: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
) -> Dict[str, bool]:
    """发送任务开始通知。"""
    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(owner_id)
        if not resolved_owner:
            logger.warning("多用户模式发送任务开始通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return {}
        targets = _notifier_load_user_targets(
            self,
            resolved_owner,
            event_type="task_start",
            bound_task=_notifier_resolve_bound_task(bound_task, bound_account),
        )
        return await _notifier_dispatch_targets(self, targets, "send_task_start_notification", task_name, reason)

    config.reload()
    targets = _notifier_build_local_targets(self)
    return await _notifier_dispatch_targets(self, targets, "send_task_start_notification", task_name, reason)


async def _notifier_send_task_completion_notification(
    self,
    task_name: str,
    reason: str,
    processed_count: int = 0,
    recommended_count: int = 0,
    owner_id: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
) -> Dict[str, bool]:
    """发送任务完成通知。"""
    normalized_reason = self._format_task_end_reason(reason)

    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(owner_id)
        if not resolved_owner:
            logger.warning("多用户模式发送任务完成通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return {}
        targets = _notifier_load_user_targets(
            self,
            resolved_owner,
            event_type="task_completion",
            bound_task=_notifier_resolve_bound_task(bound_task, bound_account),
        )
        return await _notifier_dispatch_targets(
            self,
            targets,
            "send_task_completion_notification",
            task_name,
            normalized_reason,
            processed_count,
            recommended_count,
        )

    config.reload()
    if not config.get("NOTIFY_AFTER_TASK_COMPLETE", True):
        return {}
    targets = _notifier_build_local_targets(self)
    return await _notifier_dispatch_targets(
        self,
        targets,
        "send_task_completion_notification",
        task_name,
        normalized_reason,
        processed_count,
        recommended_count,
    )


async def _notifier_send_to_channel(
    self,
    channel: str,
    product: Dict[str, Any],
    reason: str,
    owner_id: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
    config_id: Optional[str] = None,
) -> bool:
    """发送商品通知到指定渠道。"""
    if channel not in self.channels:
        return False
    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(owner_id)
        if not resolved_owner:
            logger.warning("多用户模式发送单渠道通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return False
        targets = _notifier_load_user_targets(
            self,
            resolved_owner,
            event_type="product",
            channel=channel,
            bound_task=_notifier_resolve_bound_task(bound_task, bound_account),
            config_id=config_id,
        )
        result = await _notifier_dispatch_targets(self, targets, "send_product_notification", product, reason)
        display_name = self.channel_name_map.get(channel, channel)
        return bool(result.get(display_name))

    config.reload()
    targets = _notifier_build_local_targets(self, channel=channel)
    result = await _notifier_dispatch_targets(self, targets, "send_product_notification", product, reason)
    display_name = self.channel_name_map.get(channel, channel)
    return bool(result.get(display_name))


async def _notifier_send_test_product_notification(
    self,
    channel: str,
    owner_id: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
    config_id: Optional[str] = None,
) -> bool:
    """发送商品卡测试通知。"""
    test_product = {
        "商品信息": {
            "商品标题": "测试商品",
            "当前售价": "100.00元",
            "发布时间": "2023-01-01 10:00:00",
            "商品图片列表": ["https://via.placeholder.com/100"],
            "商品链接": "https://2.taobao.com/item.htm?id=test12345",
        },
        "ai_analysis": {"reason": "这是一个测试商品，用于验证商品通知配置是否正确"},
    }
    return await _notifier_send_to_channel(
        self,
        channel=channel,
        product=test_product,
        reason="测试商品推荐",
        owner_id=owner_id,
        bound_task=bound_task,
        bound_account=bound_account,
        config_id=config_id,
    )


async def _notifier_send_test_task_start_notification(
    self,
    channel: str,
    owner_id: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
    config_id: Optional[str] = None,
) -> bool:
    """发送任务开始测试通知。"""
    if channel not in self.channels:
        return False

    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(owner_id)
        if not resolved_owner:
            logger.warning("多用户模式发送任务开始测试通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return False
        targets = _notifier_load_user_targets(
            self,
            resolved_owner,
            event_type="test",
            channel=channel,
            bound_task=_notifier_resolve_bound_task(bound_task, bound_account),
            config_id=config_id,
        )
        result = await _notifier_dispatch_targets(self, targets, "send_task_start_notification", "测试任务", "手动开始")
        display_name = self.channel_name_map.get(channel, channel)
        return bool(result.get(display_name))

    config.reload()
    targets = _notifier_build_local_targets(self, channel=channel)
    result = await _notifier_dispatch_targets(self, targets, "send_task_start_notification", "测试任务", "手动开始")
    display_name = self.channel_name_map.get(channel, channel)
    return bool(result.get(display_name))


async def _notifier_send_test_task_completion_notification(
    self,
    channel: str,
    owner_id: Optional[str] = None,
    bound_task: Optional[str] = None,
    bound_account: Optional[str] = None,
    config_id: Optional[str] = None,
) -> bool:
    """发送任务完成测试通知。"""
    if channel not in self.channels:
        return False

    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(owner_id)
        if not resolved_owner:
            logger.warning("多用户模式发送任务完成测试通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return False
        targets = _notifier_load_user_targets(
            self,
            resolved_owner,
            event_type="test",
            channel=channel,
            bound_task=_notifier_resolve_bound_task(bound_task, bound_account),
            config_id=config_id,
        )
        result = await _notifier_dispatch_targets(
            self,
            targets,
            "send_task_completion_notification",
            "测试任务",
            "自动结束-结束原因：完成了全部设置商品分析",
            10,
            3,
        )
        display_name = self.channel_name_map.get(channel, channel)
        return bool(result.get(display_name))

    config.reload()
    targets = _notifier_build_local_targets(self, channel=channel)
    result = await _notifier_dispatch_targets(
        self,
        targets,
        "send_task_completion_notification",
        "测试任务",
        "自动结束-结束原因：完成了全部设置商品分析",
        10,
        3,
    )
    display_name = self.channel_name_map.get(channel, channel)
    return bool(result.get(display_name))


async def _notifier_send_test_task_start_notifications(self) -> Dict[str, bool]:
    """批量发送任务开始测试通知。"""
    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(None)
        if not resolved_owner:
            logger.warning("多用户模式批量任务开始测试通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return {}
        targets = _notifier_load_user_targets(self, resolved_owner, event_type="test")
        return await _notifier_dispatch_targets(self, targets, "send_task_start_notification", "测试任务", "手动开始")

    config.reload()
    targets = _notifier_build_local_targets(self)
    return await _notifier_dispatch_targets(self, targets, "send_task_start_notification", "测试任务", "手动开始")


async def _notifier_send_test_task_completion_notifications(self) -> Dict[str, bool]:
    """批量发送任务完成测试通知。"""
    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(None)
        if not resolved_owner:
            logger.warning("多用户模式批量任务完成测试通知缺少owner_id", extra={"event": "notification_owner_missing"})
            return {}
        targets = _notifier_load_user_targets(self, resolved_owner, event_type="test")
        return await _notifier_dispatch_targets(
            self,
            targets,
            "send_task_completion_notification",
            "测试任务",
            "自动结束-结束原因：完成了全部设置商品分析",
            10,
            3,
        )

    config.reload()
    targets = _notifier_build_local_targets(self)
    return await _notifier_dispatch_targets(
        self,
        targets,
        "send_task_completion_notification",
        "测试任务",
        "自动结束-结束原因：完成了全部设置商品分析",
        10,
        3,
    )


def _notifier_list_configured_channels(self, owner_id: Optional[str] = None) -> List[str]:
    """列出当前生效配置的渠道。"""
    if _notifier_is_postgres_mode():
        resolved_owner = _notifier_resolve_owner_id(owner_id)
        if not resolved_owner:
            return []
        targets = _notifier_load_user_targets(self, resolved_owner, event_type="test")
        return sorted({target.get("channel") for target in targets if target.get("channel")})

    configured_channels = []
    for channel, channel_config in self._get_channel_configurations().items():
        if channel_config["configured"]:
            configured_channels.append(channel)
    return configured_channels


Notifier.send_test_notification = _notifier_send_test_notification
Notifier.send_test_notifications = _notifier_send_test_notifications
Notifier.send_product_notification = _notifier_send_product_notification
Notifier.send_task_start_notification = _notifier_send_task_start_notification
Notifier.send_task_completion_notification = _notifier_send_task_completion_notification
Notifier.send_to_channel = _notifier_send_to_channel
Notifier.send_test_product_notification = _notifier_send_test_product_notification
Notifier.send_test_task_start_notification = _notifier_send_test_task_start_notification
Notifier.send_test_task_completion_notification = _notifier_send_test_task_completion_notification
Notifier.send_test_task_start_notifications = _notifier_send_test_task_start_notifications
Notifier.send_test_task_completion_notifications = _notifier_send_test_task_completion_notifications
Notifier.list_configured_channels = _notifier_list_configured_channels


notifier = Notifier()
