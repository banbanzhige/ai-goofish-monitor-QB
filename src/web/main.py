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
from src.web.notification_manager_v2 import router as notification_router
from src.web.ai_manager import router as ai_router
from src.web.account_manager import router as account_router
from src.web.bayes_api import router as bayes_router
from src.web.user_manager import router as user_router, groups_router
from src.web.auth import is_multi_user_mode
from src.logging_config import setup_logging, get_logger
from src.storage import get_storage
from src.storage.utils import verify_password
from src.config import (
    LOG_LEVEL, LOG_CONSOLE_LEVEL, LOG_DIR, LOG_MAX_BYTES,
    LOG_BACKUP_COUNT, LOG_RETENTION_DAYS, LOG_JSON_FORMAT, LOG_ENABLE_LEGACY,
    DATABASE_URL, SCHEDULER_LOGIN_REQUIRED_IN_MULTI_USER, WEB_USERNAME
)

# 初始化日志系统
setup_logging(
    log_dir=LOG_DIR(),
    log_level=LOG_LEVEL(),
    console_level=LOG_CONSOLE_LEVEL(),
    max_bytes=LOG_MAX_BYTES(),
    backup_count=LOG_BACKUP_COUNT(),
    retention_days=LOG_RETENTION_DAYS(),
    enable_json=LOG_JSON_FORMAT(),
    enable_legacy=LOG_ENABLE_LEGACY()
)

# 获取logger
logger = get_logger(__name__, service="web")


# 全局变量
fetcher_processes = {}
login_process = None
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
scheduler_start_lock = asyncio.Lock()


def _defer_scheduler_start_until_login() -> bool:
    """多用户模式下，按配置决定是否延迟到登录后再启动调度器。"""
    return is_multi_user_mode() and SCHEDULER_LOGIN_REQUIRED_IN_MULTI_USER()


async def _ensure_scheduler_started(reason: str, username: str = "") -> None:
    """确保调度器已启动，避免重复启动并记录原因。"""
    async with scheduler_start_lock:
        if scheduler.running:
            return
        await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)
        scheduler.start()
        logger.info(
            "调度器已启动",
            extra={"event": "scheduler_started", "reason": reason, "username": username or None}
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用的生命周期事件。"""
    await _set_all_tasks_stopped_in_config()
    if _defer_scheduler_start_until_login():
        logger.info(
            "多用户模式已启用登录后启动调度器，启动阶段跳过自动加载任务",
            extra={"event": "scheduler_deferred_until_login"}
        )
    else:
        await _ensure_scheduler_started(reason="startup")

    yield

    if scheduler.running:
        logger.info("正在关闭调度器...", extra={"event": "scheduler_shutdown"})
        scheduler.shutdown()

    if fetcher_processes:
        logger.info("Web服务器正在关闭，正在终止所有数据收集脚本进程...", extra={"event": "tasks_shutdown"})
        stop_tasks = [stop_task_process(task_id) for task_id in list(fetcher_processes.keys())]
        await asyncio.gather(*stop_tasks)
        logger.info("所有数据收集脚本进程已终止。", extra={"event": "tasks_shutdown_complete"})

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
    
    def _get_database_status():
        """获取数据库连接状态"""
        if not is_multi_user_mode():
            return {
                "label": "数据库未启用",
                "desc": "本地模式无需数据库连接",
                "level": "info"
            }
        
        database_url = DATABASE_URL()
        if not database_url:
            return {
                "label": "数据库未配置",
                "desc": "请先在系统设置中配置数据库连接",
                "level": "error"
            }
        
        engine = None
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(
                database_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 3}
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {
                "label": "数据库连接正常",
                "desc": "PostgreSQL 可用",
                "level": "ok"
            }
        except Exception as e:
            logger.warning(
                "数据库连接失败",
                extra={"event": "database_connection_failed"},
                exc_info=e
            )
            return {
                "label": "数据库连接失败",
                "desc": "请检查账号密码或网络",
                "level": "error"
            }
        finally:
            if engine is not None:
                engine.dispose()

    def _get_super_admin_security_notice() -> str:
        """检测默认超级管理员密码风险提示。"""
        if not is_multi_user_mode():
            return ""

        try:
            storage = get_storage()
            default_username = (WEB_USERNAME() or "admin").strip() or "admin"
            default_user = storage.get_user_by_username(default_username)
            if not default_user:
                return ""
            password_hash = str(default_user.get("password_hash") or "")
            if password_hash and verify_password("admin123", password_hash):
                return "安全提醒：检测到超级管理员仍使用默认密码，请登录后尽快修改。"
        except Exception as e:
            logger.warning(
                "读取超级管理员密码风险状态失败",
                extra={"event": "super_admin_password_notice_check_failed"},
                exc_info=e
            )
        return ""

    storage_mode_label = "服务器模式" if is_multi_user_mode() else "本地模式"
    storage_mode_desc = "多用户 / PostgreSQL" if is_multi_user_mode() else "单用户 / 文件存储"
    db_status = _get_database_status()
    security_notice = _get_super_admin_security_notice()
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "version": VERSION,
            "storage_mode_label": storage_mode_label,
            "storage_mode_desc": storage_mode_desc,
            "db_status_label": db_status["label"],
            "db_status_desc": db_status["desc"],
            "db_status_level": db_status["level"],
            "security_notice": security_notice,
        }
    )


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
        if _defer_scheduler_start_until_login():
            try:
                await _ensure_scheduler_started(reason="login", username=username)
            except Exception as e:
                logger.error(
                    "登录后启动调度器失败",
                    extra={"event": "scheduler_start_after_login_failed", "username": username},
                    exc_info=e
                )
        logger.info(f"用户 {username} 登录成功", extra={"event": "user_login", "username": username})
        return response
    else:
        # 登录失败
        logger.warning(f"登录失败: 用户名 {username}", extra={"event": "login_failed", "username": username})
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
    logger.info(f"用户 {username} 已登出", extra={"event": "user_logout", "username": username})
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
    
    return templates.TemplateResponse(request, "index.html", {"version": VERSION})


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
app.include_router(user_router)
app.include_router(groups_router)


if __name__ == "__main__":
    from src.config import SERVER_PORT
    server_port = SERVER_PORT()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    logger.info(
        f"启动 Web 管理界面，请在浏览器访问 http://127.0.0.1:{server_port}",
        extra={"event": "web_server_start", "port": server_port}
    )
    sys.stdout.flush()
    uvicorn.run(app, host="0.0.0.0", port=server_port, log_level="warning")
