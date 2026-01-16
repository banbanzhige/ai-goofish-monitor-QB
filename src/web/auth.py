import os
import base64
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Depends, status, HTTPException
from fastapi.staticfiles import StaticFiles


security = HTTPBasic()


def get_auth_credentials():
    """从环境变量获取认证凭据"""
    username = os.getenv("WEB_USERNAME", "admin")
    password = os.getenv("WEB_PASSWORD", "admin123")
    username = username or "admin"
    password = password or "admin123"
    return username, password


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """验证Basic认证凭据，如果用户名和密码都为空则允许匿名访问"""
    username, password = get_auth_credentials()

    if not username and not password:
        return "anonymous"

    if credentials.username == username and credentials.password == password:
        return credentials.username
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Basic"},
        )


class AuthenticatedStaticFiles(StaticFiles):
    """自定义静态文件处理器，添加认证"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        expected_username, expected_password = get_auth_credentials()
        if not expected_username and not expected_password:
            await super().__call__(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode()

        if not authorization.startswith("Basic "):
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"www-authenticate", b"Basic realm=Authorization Required"),
                    (b"content-type", b"text/plain"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b"Authentication required",
            })
            return

        try:
            credentials = base64.b64decode(authorization[6:]).decode()
            username, password = credentials.split(":", 1)

            if username != expected_username or password != expected_password:
                raise ValueError("Invalid credentials")

        except Exception:
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"www-authenticate", b"Basic realm=Authorization Required"),
                    (b"content-type", b"text/plain"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b"Authentication failed",
            })
            return

        await super().__call__(scope, receive, send)
