import os
import sys
from dotenv import load_dotenv, dotenv_values
from openai import AsyncOpenAI

# Load .env file at the very beginning
load_dotenv(override=True)

# --- File Paths & Directories ---
STATE_FILE = "xianyu_state.json"
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

def SKIP_AI_ANALYSIS():
    return get_bool_env_value("SKIP_AI_ANALYSIS", False)

def ENABLE_THINKING():
    return get_bool_env_value("ENABLE_THINKING", False)

def ENABLE_RESPONSE_FORMAT():
    return get_bool_env_value("ENABLE_RESPONSE_FORMAT", True)

def SEND_URL_FORMAT_IMAGE():
    return get_bool_env_value("SEND_URL_FORMAT_IMAGE", True)

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

        # 检查配置是否齐全
        if not all([base_url, model_name]):
            print("[异常]API接口文件未填写，AI相关功能可能无法使用，请在Web管理界面填写或手动修改.env文件")
            client = None
            return False

        # 配置代理
        if proxy_url:
            # 设置环境变量，httpx会自动使用这些代理设置
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
            print(f"正在为AI请求使用HTTP/S代理: {proxy_url}")

        # 创建客户端
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        print(f"AI客户端已成功初始化 (BASE_URL: {base_url}, MODEL_NAME: {model_name})")
        return True
    except Exception as e:
        print(f"初始化 OpenAI 客户端时出错: {e}")
        client = None
        return False

def reload_config():
    """Reload all configuration and restart AI client if needed"""
    # Clear the existing environment variables to ensure fresh values
    for key in list(os.environ.keys()):
        if key.startswith('OPENAI_') or key == 'PROXY_URL':
            del os.environ[key]
    
    load_dotenv(override=True)  # Reload .env with override=True
    return initialize_ai_client()  # Reinitialize AI client with new config

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
    
    return kwargs
