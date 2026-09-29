import os
import sys
import re
import tempfile
from dotenv import load_dotenv, dotenv_values
from openai import AsyncOpenAI
import httpx
from src.httpx_compat import create_sdk_http_client
from src.logging_config import get_logger
from src.portable.context import (
    PORTABLE_DATABASE_URL_ENVIRONMENT_VARIABLE,
    portable_app_env_path,
    portable_mode,
    portable_paths,
)

logger = get_logger(__name__, service="system")

# Freeze Launcher-controlled portable inputs before legacy dotenv behavior.
# A project .env can never switch the selected execution mode or root/DSN.
PORTABLE_MODE = portable_mode()
_PORTABLE_CONTROLLED_ENVIRONMENT = {
    key: value
    for key, value in os.environ.items()
    if key.startswith("GOOFISH_PORTABLE_")
}
# A migrated server may pass its restricted runtime DSN explicitly.  Capture it
# before the legacy .env loader (which intentionally uses override=True) runs.
_SERVER_APP_DATABASE_URL = os.environ.get("QB_SERVER_APP_DATABASE_URL", "")

# Only non-sensitive, non-instance preferences may persist in portable app.env.
# Database, credentials, roots, listener settings, and all service endpoints are
# process-managed by the Launcher and must never be written to this file.
PORTABLE_APP_ENV_ALLOWED_KEYS = frozenset({
    "LOG_BACKUP_COUNT",
    "LOG_CONSOLE_LEVEL",
    "LOG_ENABLE_LEGACY",
    "LOG_JSON_FORMAT",
    "LOG_LEVEL",
    "LOG_MAX_BYTES",
    "LOG_RETENTION_DAYS",
    "RUN_HEADLESS",
})
_PORTABLE_BOOLEAN_PREFERENCE_KEYS = frozenset({
    "LOG_ENABLE_LEGACY",
    "LOG_JSON_FORMAT",
    "RUN_HEADLESS",
})
_PORTABLE_NON_NEGATIVE_INTEGER_PREFERENCE_KEYS = frozenset({
    "LOG_BACKUP_COUNT",
    "LOG_RETENTION_DAYS",
})
_PORTABLE_POSITIVE_INTEGER_PREFERENCE_KEYS = frozenset({"LOG_MAX_BYTES"})
_PORTABLE_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"})
_PORTABLE_PROCESS_PREFERENCE_VALUES = {
    key: os.environ[key]
    for key in PORTABLE_APP_ENV_ALLOWED_KEYS
    if key in os.environ
}
_portable_file_preference_values: dict[str, str] = {}


def _normalize_portable_preference_value(key: str, value) -> str:
    """Validate and serialize a portable preference without dotenv injection."""

    if isinstance(value, bool):
        raw_value = "true" if value else "false"
    elif isinstance(value, (str, int)) and not isinstance(value, bool):
        raw_value = str(value)
    else:
        raise ValueError(f"便携版 app.env 字段 {key} 的值必须是标量")

    if "\x00" in raw_value or "\r" in raw_value or "\n" in raw_value:
        raise ValueError(f"便携版 app.env 字段 {key} 包含不允许的字符")
    normalized = raw_value.strip()

    if key in _PORTABLE_BOOLEAN_PREFERENCE_KEYS:
        boolean_values = {
            "1": "true", "true": "true", "yes": "true", "on": "true",
            "0": "false", "false": "false", "no": "false", "off": "false",
        }
        result = boolean_values.get(normalized.lower())
        if result is None:
            raise ValueError(f"便携版 app.env 字段 {key} 必须是布尔值")
        return result

    if key in _PORTABLE_NON_NEGATIVE_INTEGER_PREFERENCE_KEYS | _PORTABLE_POSITIVE_INTEGER_PREFERENCE_KEYS:
        if not normalized.isascii() or not normalized.isdecimal():
            raise ValueError(f"便携版 app.env 字段 {key} 必须是整数")
        number = int(normalized)
        if key in _PORTABLE_POSITIVE_INTEGER_PREFERENCE_KEYS and number <= 0:
            raise ValueError(f"便携版 app.env 字段 {key} 必须大于零")
        return str(number)

    if key in {"LOG_LEVEL", "LOG_CONSOLE_LEVEL"}:
        level = normalized.upper()
        if level not in _PORTABLE_LOG_LEVELS:
            raise ValueError(f"便携版 app.env 字段 {key} 不是有效日志级别")
        return level

    raise ValueError(f"便携版 app.env 字段 {key} 不受支持")


def _read_portable_app_env() -> dict[str, str]:
    """Read the sole portable preference file without dotenv discovery."""

    env_path = portable_app_env_path(environ=_PORTABLE_CONTROLLED_ENVIRONMENT)
    if not env_path.exists():
        return {}
    try:
        raw_values = dotenv_values(env_path)
    except (OSError, UnicodeError) as exc:
        logger.error(
            "读取便携版偏好配置失败",
            extra={"event": "portable_app_env_read_failed", "path": str(env_path)},
            exc_info=exc,
        )
        raise RuntimeError("无法读取便携版偏好配置") from exc

    invalid_keys = set(raw_values).difference(PORTABLE_APP_ENV_ALLOWED_KEYS)
    if invalid_keys:
        logger.error(
            "便携版偏好配置包含不允许的字段",
            extra={"event": "portable_app_env_invalid_keys", "keys": sorted(invalid_keys)},
        )
        raise ValueError("便携版 app.env 包含不允许的字段")
    try:
        return {
            key: _normalize_portable_preference_value(key, value)
            for key, value in raw_values.items()
        }
    except ValueError as exc:
        logger.error(
            "便携版偏好配置字段值无效",
            extra={"event": "portable_app_env_invalid_value"},
            exc_info=exc,
        )
        raise


def _load_portable_app_env() -> dict[str, str]:
    """Apply portable preferences only where the process has no explicit value."""

    global _portable_file_preference_values

    values = _read_portable_app_env()
    for key in _portable_file_preference_values:
        if key not in values and key not in _PORTABLE_PROCESS_PREFERENCE_VALUES:
            os.environ.pop(key, None)
    for key, value in values.items():
        if key not in _PORTABLE_PROCESS_PREFERENCE_VALUES:
            os.environ[key] = value
    _portable_file_preference_values = dict(values)
    return values


def _load_environment_config() -> dict[str, str]:
    """Load configuration while preserving the established legacy dotenv path."""

    if PORTABLE_MODE:
        return _load_portable_app_env()
    # Legacy behavior deliberately remains cwd-based and overrides the process.
    load_dotenv(override=True)
    # New portable controls are never accepted from legacy dotenv files.  The
    # pre-existing keys retain their historical override behavior above.
    for key in tuple(os.environ):
        if key.startswith("GOOFISH_PORTABLE_") and key not in _PORTABLE_CONTROLLED_ENVIRONMENT:
            os.environ.pop(key, None)
    os.environ.update(_PORTABLE_CONTROLLED_ENVIRONMENT)
    return dotenv_values(".env")


# Load configuration at the very beginning.  Portable mode never discovers a
# repository or parent .env and never overrides launcher-managed process values.
_load_environment_config()

# --- File Paths & Directories ---
if PORTABLE_MODE:
    _portable_paths = portable_paths(environ=_PORTABLE_CONTROLLED_ENVIRONMENT)
    IMAGE_SAVE_DIR = str(_portable_paths.data_path("results", "images"))
    CONFIG_FILE = str(_portable_paths.data_path("config", "config.json"))
else:
    IMAGE_SAVE_DIR = "images"
    CONFIG_FILE = "config.json"

try:
    os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)
except OSError as exc:
    logger.error(
        "创建图片保存目录失败",
        extra={"event": "image_save_directory_create_failed", "path": IMAGE_SAVE_DIR},
        exc_info=exc,
    )
    raise

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
    return _load_environment_config()

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


def normalize_database_url(url: str) -> str:
    """规范化 DATABASE_URL，修正常见的主机前缀错误"""
    if not url:
        return ""
    normalized = str(url).strip()
    # 修复主机误填 http(s):// 的情况（含有用户名或无用户名两种形式）
    normalized = normalized.replace("@http://", "@").replace("@https://", "@")
    normalized = re.sub(
        r"^(postgresql(?:\\+[^:]+)?|postgres)://https?://",
        r"\\1://",
        normalized,
        flags=re.IGNORECASE
    )
    return normalized

def _get_runtime_override_value(key: str):
    """读取任务运行时覆盖配置，支持子进程按用户注入隔离参数。"""
    runtime_key = f"GOOFISH_{key}"
    if runtime_key in os.environ:
        return os.environ.get(runtime_key)
    return None

# --- Environment Variables Accessors ---
# These functions will always return the latest value from the environment
def API_KEY():
    runtime_value = _get_runtime_override_value("OPENAI_API_KEY")
    if runtime_value is not None:
        return runtime_value
    return os.getenv("OPENAI_API_KEY")

def BASE_URL():
    runtime_value = _get_runtime_override_value("OPENAI_BASE_URL")
    if runtime_value is not None:
        return runtime_value
    return os.getenv("OPENAI_BASE_URL")

def MODEL_NAME():
    runtime_value = _get_runtime_override_value("OPENAI_MODEL_NAME")
    if runtime_value is not None:
        return runtime_value
    return os.getenv("OPENAI_MODEL_NAME")


def PROXY_URL():
    runtime_value = _get_runtime_override_value("PROXY_URL")
    if runtime_value is not None:
        return runtime_value
    return os.getenv("PROXY_URL")

def STORAGE_BACKEND():
    if PORTABLE_MODE:
        return "postgres"
    return (get_env_value("STORAGE_BACKEND", "local") or "local").lower()

def DATABASE_URL():
    if PORTABLE_MODE:
        return normalize_database_url(
            _PORTABLE_CONTROLLED_ENVIRONMENT.get(PORTABLE_DATABASE_URL_ENVIRONMENT_VARIABLE, "")
        )
    if _SERVER_APP_DATABASE_URL:
        return normalize_database_url(_SERVER_APP_DATABASE_URL)
    return normalize_database_url(get_env_value("DATABASE_URL", ""))

def ENCRYPTION_MASTER_KEY():
    return get_env_value("ENCRYPTION_MASTER_KEY", "")

def PROXY_AI_ENABLED():
    runtime_value = _get_runtime_override_value("PROXY_AI_ENABLED")
    if runtime_value is not None:
        return str(runtime_value).strip().lower() in ["true", "yes", "1", "on"]
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

def NTFY_TOPIC():
    return os.getenv("NTFY_TOPIC")

def NTFY_SERVER_URL():
    return os.getenv("NTFY_SERVER_URL")

def NTFY_TOKEN():
    return os.getenv("NTFY_TOKEN")

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

def WEB_USERNAME():
    return get_env_value("WEB_USERNAME", "admin")

def WEB_PASSWORD():
    return get_env_value("WEB_PASSWORD", "admin123")

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
    runtime_value = _get_runtime_override_value("AI_MAX_TOKENS_PARAM_NAME")
    if runtime_value is not None:
        return (runtime_value or "").strip()
    return (get_env_value("AI_MAX_TOKENS_PARAM_NAME", "max_tokens") or "").strip()

def AI_MAX_TOKENS_LIMIT():
    """获取最大输出tokens上限，做最小容错以避免非法值导致请求失败。"""
    runtime_value = _get_runtime_override_value("AI_MAX_TOKENS_LIMIT")
    if runtime_value is not None:
        limit = runtime_value
    else:
        limit = get_env_value("AI_MAX_TOKENS_LIMIT", 20000, int)
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        return 20000
    return limit_int if limit_int > 0 else 20000

def SKIP_AI_ANALYSIS():
    return get_bool_env_value("SKIP_AI_ANALYSIS", False)

def DB_DEDUP_ENABLED():
    """数据库去重主路径开关（PostgreSQL模式生效）。"""
    return get_bool_env_value("DB_DEDUP_ENABLED", True)

def DB_DEDUP_SCOPE():
    """数据库去重范围：owner 或 task。"""
    scope = str(get_env_value("DB_DEDUP_SCOPE", "owner") or "owner").strip().lower()
    return scope if scope in {"owner", "task"} else "owner"

def JSONL_FALLBACK_ON_DB_ERROR():
    """数据库写入失败时是否回退jsonl。"""
    return get_bool_env_value("JSONL_FALLBACK_ON_DB_ERROR", False)

def ENABLE_THINKING():
    return get_bool_env_value("ENABLE_THINKING", False)

def ENABLE_RESPONSE_FORMAT():
    return get_bool_env_value("ENABLE_RESPONSE_FORMAT", True)

def AI_PARAMETER_FALLBACK_ENABLED():
    """私有 worker 覆盖优先；缺省关闭且不接受任意非空值。"""
    value = _get_runtime_override_value("AI_PARAMETER_FALLBACK_ENABLED")
    if value is None:
        value = get_env_value("AI_PARAMETER_FALLBACK_ENABLED", "false")
    return str(value).strip().lower() == "true"


def AI_REASONING_FALLBACK_ENABLED():
    """兼容网关推理字段回退仅由明确的当前用户配置启用。"""
    value = _get_runtime_override_value("AI_REASONING_FALLBACK_ENABLED")
    if value is None:
        value = get_env_value("AI_REASONING_FALLBACK_ENABLED", "false")
    return str(value).strip().lower() == "true"


def AI_VISION_ENABLED():
    return get_bool_env_value("AI_VISION_ENABLED", False)

def SERVER_PORT():
    return int(get_env_value("SERVER_PORT", 8000))


def SCHEDULER_LOGIN_REQUIRED_IN_MULTI_USER():
    """多用户模式下是否要求登录后再启动调度器。"""
    return get_bool_env_value("SCHEDULER_LOGIN_REQUIRED_IN_MULTI_USER", True)

# --- Logging Configuration ---
def LOG_LEVEL():
    return get_env_value("LOG_LEVEL", "INFO").upper()

def LOG_CONSOLE_LEVEL():
    return get_env_value("LOG_CONSOLE_LEVEL", "INFO").upper()

def LOG_DIR():
    if PORTABLE_MODE:
        return str(portable_paths(environ=_PORTABLE_CONTROLLED_ENVIRONMENT).data_path("logs"))
    return get_env_value("LOG_DIR", "logs")

def LOG_MAX_BYTES():
    return int(get_env_value("LOG_MAX_BYTES", 10485760))  # 10MB

def LOG_BACKUP_COUNT():
    return int(get_env_value("LOG_BACKUP_COUNT", 10))

def LOG_RETENTION_DAYS():
    return int(get_env_value("LOG_RETENTION_DAYS", 7))

def LOG_JSON_FORMAT():
    return get_bool_env_value("LOG_JSON_FORMAT", True)

def LOG_ENABLE_LEGACY():
    return get_bool_env_value("LOG_ENABLE_LEGACY", True)


# --- Client Initialization ---
def initialize_ai_client():
    """
    初始化或重新初始化AI客户端，使用最新的配置值
    """
    global client
    try:
        # 从访问器读取最新值，支持任务运行时 GOOFISH_* 覆盖。
        api_key = API_KEY()
        base_url = BASE_URL()
        model_name = MODEL_NAME()
        proxy_url = PROXY_URL()
        proxy_ai_enabled = PROXY_AI_ENABLED()

        # 检查配置是否齐全
        if not all([base_url, model_name]):
            # PostgreSQL 多用户模式下允许全局 .env 不配置 AI，运行期优先使用用户私有配置
            if STORAGE_BACKEND() == "postgres":
                logger.info(
                    "未配置全局AI参数，PostgreSQL模式将优先使用用户私有AI配置",
                    extra={"event": "ai_config_incomplete_but_user_scoped"},
                )
            else:
                logger.warning(
                    "API 配置不完整，AI 相关功能可能不可用",
                    extra={"event": "ai_config_incomplete"},
                )
            client = None
            return False

        # 仅在开启AI代理时为AI客户端显式注入代理，避免影响其他请求
        client_params = {
            "api_key": api_key,
            "base_url": base_url,
        }
        if proxy_ai_enabled and proxy_url:
            client_params["http_client"] = httpx.AsyncClient(proxy=proxy_url, timeout=30.0)
            logger.info(
                "AI 请求启用代理",
                extra={"event": "ai_proxy_enabled", "proxy_url": proxy_url}
            )
        elif proxy_url and not proxy_ai_enabled:
            logger.info(
                "检测到代理地址但 AI 代理开关未开启，AI 请求将直连",
                extra={"event": "ai_proxy_configured_but_disabled"}
            )

        if "http_client" not in client_params:
            client_params["http_client"] = create_sdk_http_client()

        # 创建客户端
        client = AsyncOpenAI(**client_params)
        logger.info(
            "AI 客户端初始化成功",
            extra={"event": "ai_client_initialized", "base_url": base_url, "model_name": model_name}
        )
        return True
    except Exception as e:
        logger.error(
            "初始化 OpenAI 客户端失败",
            extra={"event": "ai_client_init_failed"},
            exc_info=e
        )
        client = None
        return False

def save_env_settings(settings: dict, setting_keys: list):
    """保存配置到.env文件"""
    if PORTABLE_MODE:
        requested_keys = set(settings).union(setting_keys)
        invalid_keys = requested_keys.difference(PORTABLE_APP_ENV_ALLOWED_KEYS)
        if invalid_keys:
            logger.error(
                "拒绝写入不允许的便携版偏好字段",
                extra={"event": "portable_app_env_write_rejected", "keys": sorted(invalid_keys)},
            )
            raise ValueError("便携版 app.env 只允许保存非敏感系统偏好")

        env_file = portable_app_env_path(environ=_PORTABLE_CONTROLLED_ENVIRONMENT)
        try:
            normalized_settings = {
                key: _normalize_portable_preference_value(key, value)
                for key, value in settings.items()
            }
        except ValueError as exc:
            logger.error(
                "拒绝写入无效的便携版偏好字段值",
                extra={"event": "portable_app_env_write_rejected"},
                exc_info=exc,
            )
            raise

        existing_settings = _read_portable_app_env()
        existing_settings.update(normalized_settings)
        temporary_file = None
        try:
            env_file.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_file = tempfile.mkstemp(
                prefix=".app-env-",
                suffix=".tmp",
                dir=env_file.parent,
                text=True,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file_handle:
                for key in sorted(existing_settings):
                    value = existing_settings[key]
                    file_handle.write(f"{key}={value}\n")
            os.replace(temporary_file, env_file)
        except OSError as exc:
            logger.error(
                "写入便携版偏好配置失败",
                extra={"event": "portable_app_env_write_failed", "path": str(env_file)},
                exc_info=exc,
            )
            raise RuntimeError("无法写入便携版偏好配置") from exc
        finally:
            if temporary_file and os.path.exists(temporary_file):
                try:
                    os.unlink(temporary_file)
                except OSError as exc:
                    logger.warning(
                        "未能清理便携版偏好配置临时文件",
                        extra={"event": "portable_app_env_temp_cleanup_failed"},
                        exc_info=exc,
                    )

        global _portable_file_preference_values
        _portable_file_preference_values = dict(existing_settings)
        for key, value in normalized_settings.items():
            if key not in _PORTABLE_PROCESS_PREFERENCE_VALUES:
                os.environ[key] = value
        return

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
        "SCHEDULER_LOGIN_REQUIRED_IN_MULTI_USER",
        "RUN_HEADLESS",
        "AI_DEBUG_MODE",
        "ENABLE_THINKING",
        "ENABLE_RESPONSE_FORMAT",
        "AI_PARAMETER_FALLBACK_ENABLED",
        "AI_REASONING_FALLBACK_ENABLED",
        "AI_VISION_ENABLED",
        "DB_DEDUP_ENABLED",
        "JSONL_FALLBACK_ON_DB_ERROR",
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
    
    # Portable mode reloads only its explicit preference file.  Legacy retains
    # the existing cwd .env override semantics.
    _load_environment_config()
    
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





