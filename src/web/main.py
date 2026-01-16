import uvicorn
import os
import sys
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.version import VERSION
from src.web.auth import verify_credentials, AuthenticatedStaticFiles
from src.web.scheduler import _set_all_tasks_stopped_in_config, reload_scheduler_jobs
from src.web.task_manager import router as task_router, update_task_running_status
from src.web.log_manager import router as log_router
from src.web.result_manager import router as result_router
from src.web.settings_manager import router as settings_router
from src.web.notification_manager import router as notification_router
from src.web.ai_manager import router as ai_router


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

# 挂载静态文件
app.mount("/static", AuthenticatedStaticFiles(directory="static"), name="static")
app.mount("/logo", AuthenticatedStaticFiles(directory="logo"), name="logo")

# 配置模板
templates = Jinja2Templates(directory="templates")

# 注册路由
app.include_router(task_router, dependencies=[Depends(verify_credentials)])
app.include_router(log_router, dependencies=[Depends(verify_credentials)])
app.include_router(result_router, dependencies=[Depends(verify_credentials)])
app.include_router(settings_router, dependencies=[Depends(verify_credentials)])
app.include_router(notification_router, dependencies=[Depends(verify_credentials)])
app.include_router(ai_router, dependencies=[Depends(verify_credentials)])


@app.get("/health")
async def health_check():
    """健康检查端点，不需要认证"""
    return {"status": "healthy", "message": "服务正常运行"}


@app.get("/auth/status")
async def auth_status(username: str = Depends(verify_credentials)):
    """检查认证状态"""
    return {"authenticated": True, "username": username}


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, username: str = Depends(verify_credentials)):
    """提供 Web UI 的主页面。"""
    return templates.TemplateResponse("index.html", {"request": request, "version": VERSION})


@app.get("/api/version")
async def get_version(username: str = Depends(verify_credentials)):
    """获取当前系统版本信息。"""
    from src.version import get_current_version_info
    return {
        "version": VERSION,
        "info": get_current_version_info()
    }


if __name__ == "__main__":
    from src.config import SERVER_PORT
    server_port = SERVER_PORT()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    print(f"启动 Web 管理界面，请在浏览器访问 http://127.0.0.1:{server_port}")
    sys.stdout.flush()
    uvicorn.run(app, host="0.0.0.0", port=server_port, log_level="warning")
