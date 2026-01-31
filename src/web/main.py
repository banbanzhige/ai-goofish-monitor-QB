import uvicorn
import os
import sys
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.version import VERSION
from src.web.auth import (
    AuthenticatedStaticFiles, 
    require_auth, 
    verify_user, 
    set_session_cookie, 
    clear_session_cookie,
    is_auth_required,
    get_current_user
)
from src.web.scheduler import _set_all_tasks_stopped_in_config, reload_scheduler_jobs
from src.web.task_manager import router as task_router, update_task_running_status
from src.web.log_manager import router as log_router
from src.web.result_manager import router as result_router
from src.web.settings_manager import router as settings_router
from src.web.notification_manager import router as notification_router
from src.web.ai_manager import router as ai_router
from src.web.account_manager import router as account_router
from src.web.bayes_api import router as bayes_router


# 日志写入函数
def write_log(message):
    """将日志消息写入到 fetcher.log 文件中"""
    os.makedirs("logs", exist_ok=True)
    log_file_path = os.path.join("logs", "fetcher.log")
    try:
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(message + '\n')
    except Exception as e:
        print(f"写入日志时出错: {e}")


# 重定向 print 函数
original_print = print


def print(*args, **kwargs):
    """重定向 print 函数，同时输出到控制台和日志文件"""
    message = ' '.join(map(str, args))
    original_print(*args, **kwargs)
    write_log(message)


# 全局变量
fetcher_processes = {}
login_process = None
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用的生命周期事件。"""
    await _set_all_tasks_stopped_in_config()
    await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)
    if not scheduler.running:
        scheduler.start()

    yield

    if scheduler.running:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [系统] [INFO] 正在关闭调度器...")
        scheduler.shutdown()

    if fetcher_processes:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [系统] [INFO] Web服务器正在关闭，正在终止所有数据收集脚本进程...")
        stop_tasks = [stop_task_process(task_id) for task_id in list(fetcher_processes.keys())]
        await asyncio.gather(*stop_tasks)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [系统] [INFO] 所有数据收集脚本进程已终止。")

    await _set_all_tasks_stopped_in_config()


async def stop_task_process(task_id: int):
    """停止任务进程的辅助函数"""
    from src.web.task_manager import stop_task_process as tm_stop_task_process
    await tm_stop_task_process(task_id, fetcher_processes)


app = FastAPI(title="咸鱼公开内容查看智能处理程序", lifespan=lifespan)

# 挂载静态文件（无需认证，因为登录页面和主页都需要访问）
app.mount("/static", StaticFiles(directory="static"), name="static")
# 挂载图片静态文件（无需认证，因为登录页面需要访问）
app.mount("/images", StaticFiles(directory="images"), name="images")

# 配置模板
templates = Jinja2Templates(directory="templates")


# ============== 认证中间件 ==============

async def check_auth(request: Request):
    """检查认证状态，未登录抛出异常"""
    if not is_auth_required():
        return {"user_id": "anonymous", "username": "anonymous"}
    
    user = get_current_user(request)
    if not user:
        raise Exception("Not authenticated")
    return user


# ============== 登录相关路由（无需认证）==============

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """渲染登录页面"""
    # 如果已登录，重定向到主页
    if is_auth_required():
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/", status_code=302)
    else:
        # 不需要认证时直接跳转主页
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request, "version": VERSION})


@app.post("/login")
async def do_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """处理登录请求"""
    user = verify_user(username, password)
    
    if user:
        # 登录成功，设置Cookie并重定向
        response = RedirectResponse(url="/", status_code=302)
        set_session_cookie(response, user)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [系统] [INFO] 用户 {username} 登录成功")
        return response
    else:
        # 登录失败
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [系统] [WARN] 登录失败: 用户名 {username}")
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "用户名或密码错误"}
        )


@app.get("/logout")
async def logout(request: Request):
    """登出，清除Cookie"""
    user = get_current_user(request)
    username = user.get("username", "unknown") if user else "unknown"
    
    response = RedirectResponse(url="/login", status_code=302)
    clear_session_cookie(response)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [系统] [INFO] 用户 {username} 已登出")
    return response


# ============== 健康检查（无需认证）==============

@app.get("/health")
async def health_check():
    """健康检查端点，不需要认证"""
    return {"status": "healthy", "message": "服务正常运行"}


# ============== 需要认证的路由 ==============

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """提供 Web UI 的主页面。"""
    if is_auth_required():
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("index.html", {"request": request, "version": VERSION})


@app.get("/auth/status")
async def auth_status(request: Request):
    """检查认证状态"""
    user = get_current_user(request)
    if user:
        return {"authenticated": True, "username": user.get("username")}
    return {"authenticated": False}


@app.get("/api/version")
async def get_version(request: Request):
    """获取当前系统版本信息。"""
    if is_auth_required():
        user = get_current_user(request)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "未登录"})
    
    from src.version import get_current_version_info
    return {
        "version": VERSION,
        "info": get_current_version_info()
    }


# ============== API路由中间件 ==============

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """认证中间件：检查API请求的认证状态"""
    path = request.url.path
    
    # 不需要认证的路径
    public_paths = ["/login", "/logout", "/health", "/favicon.ico", "/images/", "/static/"]
    
    if any(path.startswith(p) for p in public_paths):
        return await call_next(request)
    
    # 如果不需要认证，放行
    if not is_auth_required():
        return await call_next(request)
    
    # 检查主页路径
    if path == "/":
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
    
    # 检查API路径
    if path.startswith("/api/"):
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"detail": "未登录，请先登录"}
            )
    
    return await call_next(request)


# 注册API路由（认证由中间件处理）
app.include_router(task_router)
app.include_router(log_router)
app.include_router(result_router)
app.include_router(settings_router)
app.include_router(notification_router)
app.include_router(ai_router)
app.include_router(account_router)
app.include_router(bayes_router)


if __name__ == "__main__":
    from src.config import SERVER_PORT
    server_port = SERVER_PORT()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    print(f"启动 Web 管理界面，请在浏览器访问 http://127.0.0.1:{server_port}")
    sys.stdout.flush()
    uvicorn.run(app, host="0.0.0.0", port=server_port, log_level="warning")
