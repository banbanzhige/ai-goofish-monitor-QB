"""
认证模块 - 支持Form POST + Cookie Session认证
保持.env凭据配置，预留多用户扩展接口
"""
import os
import time
import hashlib
import hmac
import json
import base64
from typing import Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


# 配置
SECRET_KEY = os.getenv("SECRET_KEY", "xianyu-monitor-default-secret-key-change-me")
SESSION_COOKIE_NAME = "session_token"
SESSION_EXPIRE_SECONDS = 7 * 24 * 60 * 60  # 7天


def get_auth_credentials():
    """从环境变量获取认证凭据"""
    username = os.getenv("WEB_USERNAME", "admin")
    password = os.getenv("WEB_PASSWORD", "admin123")
    username = username or "admin"
    password = password or "admin123"
    return username, password


def is_auth_required() -> bool:
    """检查是否需要认证"""
    username, password = get_auth_credentials()
    # 如果用户名和密码都为空，则不需要认证
    return bool(username and password)


def verify_user(username: str, password: str) -> Optional[dict]:
    """
    验证用户凭据
    现阶段从.env读取，未来可扩展为数据库查询
    返回用户信息字典或None
    """
    expected_username, expected_password = get_auth_credentials()
    
    if username == expected_username and password == expected_password:
        return {
            "user_id": "admin",  # 预留多用户扩展
            "username": username,
            "role": "admin"  # 预留权限扩展
        }
    return None


def _sign_data(data: str) -> str:
    """对数据进行HMAC签名"""
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def create_session_token(user_data: dict) -> str:
    """
    创建签名的session token
    格式: base64(json_data).signature
    """
    session_data = {
        **user_data,
        "login_time": int(time.time()),
        "expires": int(time.time()) + SESSION_EXPIRE_SECONDS
    }
    json_data = json.dumps(session_data, ensure_ascii=False)
    encoded_data = base64.urlsafe_b64encode(json_data.encode('utf-8')).decode('utf-8')
    signature = _sign_data(encoded_data)
    return f"{encoded_data}.{signature}"


def verify_session_token(token: str) -> Optional[dict]:
    """
    验证并解析session token
    返回用户数据或None
    """
    if not token or '.' not in token:
        return None
    
    try:
        encoded_data, signature = token.rsplit('.', 1)
        
        # 验证签名
        expected_signature = _sign_data(encoded_data)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        
        # 解析数据
        json_data = base64.urlsafe_b64decode(encoded_data.encode('utf-8')).decode('utf-8')
        session_data = json.loads(json_data)
        
        # 检查过期
        if session_data.get('expires', 0) < int(time.time()):
            return None
        
        return session_data
    except Exception:
        return None


def get_current_user(request: Request) -> Optional[dict]:
    """
    从Cookie获取当前登录用户
    返回用户数据或None
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return verify_session_token(token)


def require_auth(request: Request) -> Optional[dict]:
    """
    检查认证状态，未登录则返回None
    用于路由依赖
    """
    if not is_auth_required():
        return {"user_id": "anonymous", "username": "anonymous", "role": "admin"}
    return get_current_user(request)


def set_session_cookie(response: Response, user_data: dict):
    """设置session cookie"""
    token = create_session_token(user_data)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_EXPIRE_SECONDS,
        httponly=True,
        samesite="lax"
    )


def clear_session_cookie(response: Response):
    """清除session cookie"""
    response.delete_cookie(key=SESSION_COOKIE_NAME)


# ============== 兼容旧的Basic Auth（静态文件用）==============

class AuthenticatedStaticFiles(StaticFiles):
    """自定义静态文件处理器，支持Cookie认证"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        # 如果不需要认证，直接放行
        if not is_auth_required():
            await super().__call__(scope, receive, send)
            return

        # 从Cookie检查认证
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode()
        
        # 解析Cookie
        session_token = None
        for cookie in cookie_header.split(";"):
            cookie = cookie.strip()
            if cookie.startswith(f"{SESSION_COOKIE_NAME}="):
                session_token = cookie[len(SESSION_COOKIE_NAME) + 1:]
                break
        
        if session_token and verify_session_token(session_token):
            await super().__call__(scope, receive, send)
            return
        
        # 未认证，返回401
        await send({
            "type": "http.response.start",
            "status": 302,
            "headers": [
                (b"location", b"/login"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b"",
        })


# ============== 旧版Basic Auth兼容（可删除）==============

def verify_credentials():
    """
    旧版Basic Auth验证函数（已弃用）
    保留此函数签名以便渐进式迁移
    """
    pass
