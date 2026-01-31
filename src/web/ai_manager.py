from fastapi import APIRouter
import src.config  # 直接导入模块，而不是导入特定符号
from openai import OpenAI
import httpx


router = APIRouter()


def _resolve_tokens_config(settings: dict) -> tuple[str, int]:
    """解析tokens字段名与上限，优先使用入参，缺失时回退到当前配置。"""
    param_name = (settings.get("AI_MAX_TOKENS_PARAM_NAME") or src.config.AI_MAX_TOKENS_PARAM_NAME() or "").strip()
    raw_limit = settings.get("AI_MAX_TOKENS_LIMIT")
    if raw_limit in (None, ""):
        limit = src.config.AI_MAX_TOKENS_LIMIT()
    else:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = src.config.AI_MAX_TOKENS_LIMIT()
    # 测试请求不需要太大上限，避免不必要的开销
    test_limit = max(1, min(limit, 10))
    return param_name, test_limit


@router.post("/api/settings/ai/test")
async def test_ai_settings(settings: dict):
    """测试AI模型设置是否有效。"""
    try:
        client_params = {
            "api_key": settings.get("OPENAI_API_KEY", ""),
            "base_url": settings.get("OPENAI_BASE_URL", ""),
            "timeout": httpx.Timeout(30.0),
        }

        # 代理配置允许从入参或当前环境变量读取，便于与“代理设置”Tab联动
        proxy_url = settings.get("PROXY_URL") or src.config.PROXY_URL() or ""
        proxy_ai_enabled = settings.get("PROXY_AI_ENABLED")
        if proxy_ai_enabled is None:
            proxy_ai_enabled = src.config.PROXY_AI_ENABLED()

        if proxy_ai_enabled and proxy_url:
            client_params["http_client"] = httpx.Client(proxy=proxy_url)
        elif proxy_url and not proxy_ai_enabled:
            print("LOG: 检测到代理地址但AI代理未开启，本次AI测试将直连。")

        mode_name = settings.get("OPENAI_MODEL_NAME", "")
        print(
            f"LOG: 后端容器AI测试 BASE_URL: {client_params['base_url']}, "
            f"MODEL_NAME: {mode_name}, PROXY_URL: {proxy_url}, PROXY_AI_ENABLED: {proxy_ai_enabled}"
        )

        client = OpenAI(**client_params)

        tokens_param_name, tokens_test_limit = _resolve_tokens_config(settings)
        request_kwargs = {
            "model": mode_name,
            "messages": [
                {"role": "user", "content": "Hello, this is a test message to verify the connection."}
            ],
        }
        if tokens_param_name:
            request_kwargs[tokens_param_name] = tokens_test_limit

        response = client.chat.completions.create(
            **src.config.get_ai_request_params(**request_kwargs)
        )

        return {
            "success": True,
            "message": "AI模型连接测试成功！",
            "response": response.choices[0].message.content if response.choices else "No response"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"AI模型连接测试失败: {str(e)}"
        }


@router.post("/api/settings/ai/test/backend")
async def test_ai_settings_backend():
    """测试AI模型设置是否有效（从后端容器内发起）。"""
    try:
        # 直接访问 src.config 模块中的 client 变量
        if not src.config.client:
            # print("DEBUG: 后端AI客户端未初始化，尝试重新初始化...")
            success = src.config.reload_config()
            if not success or not src.config.client:
                return {
                    "success": False,
                    "message": "后端AI客户端未初始化，请检查.env配置文件中的AI设置。"
                }

        # print(f"LOG: 后端容器AI测试 BASE_URL: {src.config.BASE_URL()}, MODEL_NAME: {src.config.MODEL_NAME()}")
        tokens_param_name = src.config.AI_MAX_TOKENS_PARAM_NAME()
        tokens_limit = src.config.AI_MAX_TOKENS_LIMIT()
        tokens_test_limit = max(1, min(tokens_limit, 10))
        request_kwargs = {
            "model": src.config.MODEL_NAME(),
            "messages": [
                {"role": "user", "content": "Hello, this is a test message from backend container to verify connection."}
            ],
        }
        if tokens_param_name:
            request_kwargs[tokens_param_name] = tokens_test_limit
        response = await src.config.client.chat.completions.create(
            **src.config.get_ai_request_params(**request_kwargs)
        )

        return {
            "success": True,
            "message": "后端AI模型连接测试成功！容器网络正常。",
            "response": response.choices[0].message.content if response.choices else "No response"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"后端AI模型连接测试失败: {str(e)}。这表明容器内网络可能存在问题。"
        }
