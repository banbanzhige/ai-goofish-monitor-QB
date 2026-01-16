from fastapi import APIRouter
from src.config import client, BASE_URL, MODEL_NAME, get_ai_request_params
from openai import OpenAI
import httpx


router = APIRouter()


@router.post("/api/settings/ai/test")
async def test_ai_settings(settings: dict):
    """测试AI模型设置是否有效。"""
    try:
        client_params = {
            "api_key": settings.get("OPENAI_API_KEY", ""),
            "base_url": settings.get("OPENAI_BASE_URL", ""),
            "timeout": httpx.Timeout(30.0),
        }

        proxy_url = settings.get("PROXY_URL", "")
        if proxy_url:
            client_params["http_client"] = httpx.Client(proxy=proxy_url)

        mode_name = settings.get("OPENAI_MODEL_NAME", "")
        print(f"LOG: 后端容器AI测试 BASE_URL: {client_params['base_url']}, MODEL_NAME: {mode_name}, PROXY_URL: {proxy_url}")

        client = OpenAI(**client_params)

        response = client.chat.completions.create(
            **get_ai_request_params(
                model=mode_name,
                messages=[
                    {"role": "user", "content": "Hello, this is a test message to verify the connection."}
                ],
                max_tokens=10
            )
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
        if not client:
            return {
                "success": False,
                "message": "后端AI客户端未初始化，请检查.env配置文件中的AI设置。"
            }

        print(f"LOG: 后端容器AI测试 BASE_URL: {BASE_URL()}, MODEL_NAME: {MODEL_NAME()}")
        response = await client.chat.completions.create(
            **get_ai_request_params(
                model=MODEL_NAME(),
                messages=[
                    {"role": "user", "content": "Hello, this is a test message from backend container to verify connection."}
                ],
                max_tokens=10
            )
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
