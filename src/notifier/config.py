import json
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict

from src.config import get_env_value, get_bool_env_value

class NotificationConfig:
    """通知配置管理类"""
    
    def __init__(self):
        self._runtime_overrides: ContextVar[Dict[str, Any] | None] = ContextVar(
            "notification_runtime_overrides",
            default=None
        )
        self._config = self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 从.env文件加载配置
        return {
            # 代理总开关与分渠道开关
            "PROXY_URL": get_env_value("PROXY_URL", ""),
            "PROXY_AI_ENABLED": get_bool_env_value("PROXY_AI_ENABLED", False),
            "PROXY_NTFY_ENABLED": get_bool_env_value("PROXY_NTFY_ENABLED", False),
            "PROXY_GOTIFY_ENABLED": get_bool_env_value("PROXY_GOTIFY_ENABLED", False),
            "PROXY_BARK_ENABLED": get_bool_env_value("PROXY_BARK_ENABLED", False),
            "PROXY_WX_BOT_ENABLED": get_bool_env_value("PROXY_WX_BOT_ENABLED", False),
            "PROXY_WX_APP_ENABLED": get_bool_env_value("PROXY_WX_APP_ENABLED", False),
            "PROXY_TELEGRAM_ENABLED": get_bool_env_value("PROXY_TELEGRAM_ENABLED", False),
            "PROXY_WEBHOOK_ENABLED": get_bool_env_value("PROXY_WEBHOOK_ENABLED", False),
            "PROXY_DINGTALK_ENABLED": get_bool_env_value("PROXY_DINGTALK_ENABLED", False),
            # 通知渠道配置
            "NTFY_TOPIC_URL": get_env_value("NTFY_TOPIC_URL", ""),
            "NTFY_ENABLED": get_bool_env_value("NTFY_ENABLED", False),
            "GOTIFY_URL": get_env_value("GOTIFY_URL", ""),
            "GOTIFY_TOKEN": get_env_value("GOTIFY_TOKEN", ""),
            "GOTIFY_ENABLED": get_bool_env_value("GOTIFY_ENABLED", False),
            "BARK_URL": get_env_value("BARK_URL", ""),
            "BARK_ENABLED": get_bool_env_value("BARK_ENABLED", False),
            "WX_BOT_URL": get_env_value("WX_BOT_URL", ""),
            "WX_BOT_ENABLED": get_bool_env_value("WX_BOT_ENABLED", False),
            "WX_CORP_ID": get_env_value("WX_CORP_ID", ""),
            "WX_AGENT_ID": get_env_value("WX_AGENT_ID", ""),
            "WX_SECRET": get_env_value("WX_SECRET", ""),
            "WX_TO_USER": get_env_value("WX_TO_USER", "@all"),
            "WX_APP_ENABLED": get_bool_env_value("WX_APP_ENABLED", False),
            "TELEGRAM_BOT_TOKEN": get_env_value("TELEGRAM_BOT_TOKEN", ""),
            "TELEGRAM_CHAT_ID": get_env_value("TELEGRAM_CHAT_ID", ""),
            "TELEGRAM_ENABLED": get_bool_env_value("TELEGRAM_ENABLED", False),
            "WEBHOOK_URL": get_env_value("WEBHOOK_URL", ""),
            "WEBHOOK_ENABLED": get_bool_env_value("WEBHOOK_ENABLED", False),
            
            # 钉钉配置
            "DINGTALK_WEBHOOK": get_env_value("DINGTALK_WEBHOOK", ""),
            "DINGTALK_SECRET": get_env_value("DINGTALK_SECRET", ""),
            "DINGTALK_ENABLED": get_bool_env_value("DINGTALK_ENABLED", False),
            
            # Webhook配置
            "WEBHOOK_METHOD": get_env_value("WEBHOOK_METHOD", "POST").upper(),
            "WEBHOOK_HEADERS": self._parse_webhook_headers(),
            "WEBHOOK_CONTENT_TYPE": get_env_value("WEBHOOK_CONTENT_TYPE", "JSON").upper(),
            "WEBHOOK_QUERY_PARAMETERS": get_env_value("WEBHOOK_QUERY_PARAMETERS", ""),
            "WEBHOOK_BODY": get_env_value("WEBHOOK_BODY", ""),
            
            # 其他配置
            "PCURL_TO_MOBILE": get_bool_env_value("PCURL_TO_MOBILE", True),
            "NOTIFY_AFTER_TASK_COMPLETE": get_bool_env_value("NOTIFY_AFTER_TASK_COMPLETE", True),
        }
    
    def _parse_webhook_headers(self):
        """解析webhook headers"""
        headers_str = get_env_value("WEBHOOK_HEADERS", "")
        if not headers_str:
            return {}
        
        try:
            import json
            return json.loads(headers_str)
        except Exception:
            return {}
    
    def reload(self):
        """重新加载配置"""
        self._config = self._load_config()
    
    def get(self, key, default=None):
        """获取配置项"""
        return self._config.get(key, default)
    
    def __getitem__(self, key):
        """支持字典式访问"""
        return self._config[key]
    
    def __contains__(self, key):
        """支持in操作符"""
        return key in self._config

# 单例模式
def _notification_get_effective_config(self) -> Dict[str, Any]:
    """获取当前上下文生效配置。"""
    overrides = self._runtime_overrides.get()
    if not overrides:
        return self._config
    effective = dict(self._config)
    effective.update(overrides)
    return effective


@contextmanager
def _notification_apply_overrides(self, overrides: Dict[str, Any] | None):
    """在当前上下文临时覆盖通知配置。"""
    if not overrides:
        yield
        return

    current = self._runtime_overrides.get() or {}
    merged = dict(current)
    merged.update(overrides)
    token = self._runtime_overrides.set(merged)
    try:
        yield
    finally:
        self._runtime_overrides.reset(token)


def _notification_get(self, key, default=None):
    return _notification_get_effective_config(self).get(key, default)


def _notification_getitem(self, key):
    return _notification_get_effective_config(self)[key]


def _notification_contains(self, key):
    return key in _notification_get_effective_config(self)


NotificationConfig._get_effective_config = _notification_get_effective_config
NotificationConfig.apply_overrides = _notification_apply_overrides
NotificationConfig.get = _notification_get
NotificationConfig.__getitem__ = _notification_getitem
NotificationConfig.__contains__ = _notification_contains

config = NotificationConfig()
