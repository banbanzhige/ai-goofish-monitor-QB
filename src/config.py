import os
import sys
from dotenv import load_dotenv, dotenv_values
from openai import AsyncOpenAI
import httpx

# Load .env file at the very beginning
load_dotenv(override=True)

# --- File Paths & Directories ---
IMAGE_SAVE_DIR = "images"
CONFIG_FILE = "config.json"
os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)

# 任务隔离的临时图片目录前缀
TASK_IMAGE_DIR_PREFIX = "task_images_"

# --- API URL Patterns ---
API_URL_PATTERN = "h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search"
DETAIL_API_URL_PATTERN = "h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail"

# --- Headers ---
IMAGE_DOWNLOAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0',
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# --- Dynamic Configuration Loader ---
def load_env_config():
    """Load configuration from .env file, ensuring fresh values"""
    # Clear any existing cached values (if any) and reload
    load_dotenv(override=True)
    return dotenv_values(".env")

def get_env_value(key, default=None, type_converter=str):
    """Get the latest value from environment variables"""
    value = os.getenv(key, default)
    if value is not None and type_converter is not str:
        try:
            return type_converter(value)
        except (ValueError, TypeError):
            return default
    return value

def get_bool_env_value(key, default=False):
    """Get boolean value from environment variables"""
    return get_env_value(key, str(default)).lower() in ['true', 'yes', '1']

# --- Environment Variables Accessors ---
# These functions will always return the latest value from the environment
def API_KEY():
    return os.getenv("OPENAI_API_KEY")

def BASE_URL():
    return os.getenv("OPENAI_BASE_URL")

def MODEL_NAME():
    return os.getenv("OPENAI_MODEL_NAME")


def PROXY_URL():
    return os.getenv("PROXY_URL")

def PROXY_AI_ENABLED():
    return get_bool_env_value("PROXY_AI_ENABLED", False)

def PROXY_NTFY_ENABLED():
    return get_bool_env_value("PROXY_NTFY_ENABLED", False)

def PROXY_GOTIFY_ENABLED():
    return get_bool_env_value("PROXY_GOTIFY_ENABLED", False)

def PROXY_BARK_ENABLED():
    return get_bool_env_value("PROXY_BARK_ENABLED", False)

def PROXY_WX_BOT_ENABLED():
    return get_bool_env_value("PROXY_WX_BOT_ENABLED", False)

def PROXY_WX_APP_ENABLED():
    return get_bool_env_value("PROXY_WX_APP_ENABLED", False)

def PROXY_TELEGRAM_ENABLED():
    return get_bool_env_value("PROXY_TELEGRAM_ENABLED", False)

def PROXY_WEBHOOK_ENABLED():
    return get_bool_env_value("PROXY_WEBHOOK_ENABLED", False)

def PROXY_DINGTALK_ENABLED():
    return get_bool_env_value("PROXY_DINGTALK_ENABLED", False)

def NTFY_TOPIC_URL():
    return os.getenv("NTFY_TOPIC_URL")

def GOTIFY_URL():
    return os.getenv("GOTIFY_URL")

def GOTIFY_TOKEN():
    return os.getenv("GOTIFY_TOKEN")

def BARK_URL():
    return os.getenv("BARK_URL")

def WX_BOT_URL():
    return os.getenv("WX_BOT_URL")

def WX_CORP_ID():
    return os.getenv("WX_CORP_ID")

def WX_AGENT_ID():
    return os.getenv("WX_AGENT_ID")

def WX_SECRET():
    return os.getenv("WX_SECRET")

def WX_TO_USER():
    return os.getenv("WX_TO_USER", "@all")

def TELEGRAM_BOT_TOKEN():
    return os.getenv("TELEGRAM_BOT_TOKEN")

def TELEGRAM_CHAT_ID():
    return os.getenv("TELEGRAM_CHAT_ID")

def WEBHOOK_URL():
    return os.getenv("WEBHOOK_URL")

def WEBHOOK_METHOD():
    return os.getenv("WEBHOOK_METHOD", "POST").upper()

def WEBHOOK_HEADERS():
    return os.getenv("WEBHOOK_HEADERS")

def WEBHOOK_CONTENT_TYPE():
    return os.getenv("WEBHOOK_CONTENT_TYPE", "JSON").upper()

def WEBHOOK_QUERY_PARAMETERS():
    return os.getenv("WEBHOOK_QUERY_PARAMETERS")

def WEBHOOK_BODY():
    return os.getenv("WEBHOOK_BODY")

def PCURL_TO_MOBILE():
    return get_bool_env_value("PCURL_TO_MOBILE", True)

def RUN_HEADLESS():
    return get_bool_env_value("RUN_HEADLESS", True)

def LOGIN_IS_EDGE():
    return get_bool_env_value("LOGIN_IS_EDGE", False)

def RUNNING_IN_DOCKER():
    return get_bool_env_value("RUNNING_IN_DOCKER", False)

def AI_DEBUG_MODE():
    return get_bool_env_value("AI_DEBUG_MODE", False)

def AI_MAX_TOKENS_PARAM_NAME():
    """获取最大输出tokens字段名，允许用户按模型自定义（如max_tokens/max_completion_tokens）。"""
    return (get_env_value("AI_MAX_TOKENS_PARAM_NAME", "max_tokens") or "").strip()

def AI_MAX_TOKENS_LIMIT():
    """获取最大输出tokens上限，做最小容错以避免非法值导致请求失败。"""
    # 默认上限提升到20000，贴合当前多模态与长输出场景
    limit = get_env_value("AI_MAX_TOKENS_LIMIT", 20000, int)
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        return 20000
    # 非正数视为未配置，回退到安全默认值
    return limit_int if limit_int > 0 else 20000

def SKIP_AI_ANALYSIS():
    return get_bool_env_value("SKIP_AI_ANALYSIS", False)

def ENABLE_THINKING():
    return get_bool_env_value("ENABLE_THINKING", False)

def ENABLE_RESPONSE_FORMAT():
    return get_bool_env_value("ENABLE_RESPONSE_FORMAT", True)

def AI_VISION_ENABLED():
    return get_bool_env_value("AI_VISION_ENABLED", False)

def SERVER_PORT():
    return int(get_env_value("SERVER_PORT", 8000))

# --- Client Initialization ---
def initialize_ai_client():
    """
    初始化或重新初始化AI客户端，使用最新的配置值
    """
    global client
    try:
        # 从环境变量获取最新的值
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        model_name = os.getenv("OPENAI_MODEL_NAME")
        proxy_url = os.getenv("PROXY_URL")
        proxy_ai_enabled = get_bool_env_value("PROXY_AI_ENABLED", False)

        # 检查配置是否齐全
        if not all([base_url, model_name]):
            print("[异常]API接口文件未填写，AI相关功能可能无法使用，请在Web管理界面填写或手动修改.env文件")
            client = None
            return False

        # 仅在开启AI代理时为AI客户端显式注入代理，避免影响其他请求
        client_params = {
            "api_key": api_key,
            "base_url": base_url,
        }
        if proxy_ai_enabled and proxy_url:
            client_params["http_client"] = httpx.AsyncClient(proxy=proxy_url, timeout=30.0)
            print(f"正在为AI请求使用HTTP/S代理: {proxy_url}")
        elif proxy_url and not proxy_ai_enabled:
            print("检测到代理地址但AI代理开关未开启，AI请求将直连。")

        # 创建客户端
        client = AsyncOpenAI(**client_params)
        print(f"AI客户端已成功初始化 (BASE_URL: {base_url}, MODEL_NAME: {model_name})")
        return True
    except Exception as e:
        print(f"初始化 OpenAI 客户端时出错: {e}")
        client = None
        return False

def save_env_settings(settings: dict, setting_keys: list):
    """保存配置到.env文件"""
    env_file = ".env"
    env_lines = []

    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()

    existing_settings = {}
    for line in env_lines:
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.split('=', 1)
            existing_settings[key.strip()] = value.strip()

    existing_settings.update(settings)

    bool_keys = {
        "LOGIN_IS_EDGE",
        "RUN_HEADLESS",
        "AI_DEBUG_MODE",
        "ENABLE_THINKING",
        "ENABLE_RESPONSE_FORMAT",
        "AI_VISION_ENABLED",
        "PCURL_TO_MOBILE",
        "NOTIFY_AFTER_TASK_COMPLETE",
        # 代理相关开关
        "PROXY_AI_ENABLED",
        "PROXY_NTFY_ENABLED",
        "PROXY_GOTIFY_ENABLED",
        "PROXY_BARK_ENABLED",
        "PROXY_WX_BOT_ENABLED",
        "PROXY_WX_APP_ENABLED",
        "PROXY_TELEGRAM_ENABLED",
        "PROXY_WEBHOOK_ENABLED",
        "PROXY_DINGTALK_ENABLED",
    }

    with open(env_file, 'w', encoding='utf-8') as f:
        for key in setting_keys:
            value = existing_settings.get(key, "")
            if key in bool_keys:
                f.write(f"{key}={str(value).lower()}\n")
            else:
                f.write(f"{key}={value}\n")

        for key, value in existing_settings.items():
            if key not in setting_keys:
                f.write(f"{key}={value}\n")
    
    # 更新 os.environ 中的值
    for key, value in settings.items():
        os.environ[key] = str(value).lower() if key in bool_keys else str(value)

def reload_config():
    """Reload all configuration and restart AI client if needed"""
    # print("DEBUG: 开始重新加载配置")
    
    # 强制重新加载 .env 文件
    load_dotenv(override=True)  # Reload .env with override=True
    
    # print(f"DEBUG: 重新加载后的配置 - OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}, "
    #       f"OPENAI_BASE_URL: {os.getenv('OPENAI_BASE_URL')}, "
    #       f"OPENAI_MODEL_NAME: {os.getenv('OPENAI_MODEL_NAME')}")
    
    result = initialize_ai_client()
    # print(f"DEBUG: AI客户端初始化结果: {result}")
    return result

# 初始客户端初始化
client = None
initialize_ai_client()

# 检查关键配置
if 'prompt_generator.py' in sys.argv[0]:
    if not all([os.getenv("OPENAI_BASE_URL"), os.getenv("OPENAI_MODEL_NAME")]):
        sys.exit("错误：请确保在 .env 文件中完整设置了 OPENAI_BASE_URL 和 OPENAI_MODEL_NAME。(OPENAI_API_KEY 对于某些服务是可选的)")

def get_ai_request_params(**kwargs):
    """
    构建AI请求参数，使用最新的环境变量值
    """
    if get_bool_env_value("ENABLE_THINKING", False):
        kwargs["extra_body"] = {"enable_thinking": False}
    
    # 如果禁用response_format，则移除该参数
    if not get_bool_env_value("ENABLE_RESPONSE_FORMAT", True) and "response_format" in kwargs:
        del kwargs["response_format"]

    # 统一注入tokens上限配置：允许用户自定义字段名，且不覆盖调用方显式传入的值
    tokens_param_name = AI_MAX_TOKENS_PARAM_NAME()
    tokens_limit = AI_MAX_TOKENS_LIMIT()
    if tokens_param_name and tokens_param_name not in kwargs:
        kwargs[tokens_param_name] = tokens_limit
    
    return kwargs
