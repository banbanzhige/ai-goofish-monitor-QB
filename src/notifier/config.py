import json
import os
from dotenv import dotenv_values

class NotificationConfig:
    """通知配置管理类"""
    
    def __init__(self):
        self._config = self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 从.env文件加载配置
        env_config = dotenv_values(".env")
        
        # 加载并解析webhook headers
        webhook_headers = {}
        if env_config.get("WEBHOOK_HEADERS"):
            try:
                webhook_headers = json.loads(env_config["WEBHOOK_HEADERS"])
            except json.JSONDecodeError:
                webhook_headers = {}
        
        return {
            # 通知渠道配置
            "NTFY_TOPIC_URL": env_config.get("NTFY_TOPIC_URL", ""),
            "GOTIFY_URL": env_config.get("GOTIFY_URL", ""),
            "GOTIFY_TOKEN": env_config.get("GOTIFY_TOKEN", ""),
            "BARK_URL": env_config.get("BARK_URL", ""),
            "WX_BOT_URL": env_config.get("WX_BOT_URL", ""),
            "WX_CORP_ID": env_config.get("WX_CORP_ID", ""),
            "WX_AGENT_ID": env_config.get("WX_AGENT_ID", ""),
            "WX_SECRET": env_config.get("WX_SECRET", ""),
            "WX_TO_USER": env_config.get("WX_TO_USER", "@all"),
            "TELEGRAM_BOT_TOKEN": env_config.get("TELEGRAM_BOT_TOKEN", ""),
            "TELEGRAM_CHAT_ID": env_config.get("TELEGRAM_CHAT_ID", ""),
            "WEBHOOK_URL": env_config.get("WEBHOOK_URL", ""),
            
            # Webhook配置
            "WEBHOOK_METHOD": env_config.get("WEBHOOK_METHOD", "POST").upper(),
            "WEBHOOK_HEADERS": webhook_headers,
            "WEBHOOK_CONTENT_TYPE": env_config.get("WEBHOOK_CONTENT_TYPE", "JSON").upper(),
            "WEBHOOK_QUERY_PARAMETERS": env_config.get("WEBHOOK_QUERY_PARAMETERS", ""),
            "WEBHOOK_BODY": env_config.get("WEBHOOK_BODY", ""),
            
            # 其他配置
            "PCURL_TO_MOBILE": env_config.get("PCURL_TO_MOBILE", "true").lower() == "true",
        }
    
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
config = NotificationConfig()
