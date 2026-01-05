import uvicorn
import json
import aiofiles
import os
import glob
import asyncio
import signal
import sys
import base64
from contextlib import asynccontextmanager
from dotenv import dotenv_values
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from src.prompt_utils import generate_criteria, update_config_with_new_task
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# 导入版本信息
from src.version import VERSION, get_current_version

from src.file_operator import FileOperator
from src.task import get_task, update_task


class Task(BaseModel):
    task_name: str
    enabled: bool
    keyword: str
    description: str
    max_pages: int
    personal_only: bool
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: str
    ai_prompt_criteria_file: str
    is_running: Optional[bool] = False
    generating_ai_criteria: Optional[bool] = False  # Add this field for AI criteria generation status


class TaskUpdate(BaseModel):
    task_name: Optional[str] = None
    enabled: Optional[bool] = None
    keyword: Optional[str] = None
    description: Optional[str] = None
    max_pages: Optional[int] = None
    personal_only: Optional[bool] = None
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: Optional[str] = None
    ai_prompt_criteria_file: Optional[str] = None
    is_running: Optional[bool] = None
    generating_ai_criteria: Optional[bool] = None  # Add this field to match Task model


class TaskGenerateRequest(BaseModel):
    task_name: str
    keyword: str
    description: str
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    max_pages: int = 3
    cron: Optional[str] = None


class PromptUpdate(BaseModel):
    content: str


class LoginStateUpdate(BaseModel):
    content: str


class NotificationSettings(BaseModel):
    NTFY_TOPIC_URL: Optional[str] = None
    NTFY_ENABLED: Optional[bool] = False
    GOTIFY_URL: Optional[str] = None
    GOTIFY_TOKEN: Optional[str] = None
    GOTIFY_ENABLED: Optional[bool] = False
    BARK_URL: Optional[str] = None
    BARK_ENABLED: Optional[bool] = False
    WX_BOT_URL: Optional[str] = None
    WX_BOT_ENABLED: Optional[bool] = False
    WX_CORP_ID: Optional[str] = None
    WX_AGENT_ID: Optional[str] = None
    WX_SECRET: Optional[str] = None
    WX_TO_USER: Optional[str] = None
    WX_APP_ENABLED: Optional[bool] = False
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_ENABLED: Optional[bool] = False
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_ENABLED: Optional[bool] = False
    WEBHOOK_METHOD: Optional[str] = "POST"
    WEBHOOK_HEADERS: Optional[str] = None
    WEBHOOK_CONTENT_TYPE: Optional[str] = "JSON"
    WEBHOOK_QUERY_PARAMETERS: Optional[str] = None
    WEBHOOK_BODY: Optional[str] = None
    PCURL_TO_MOBILE: Optional[bool] = True
    NOTIFY_AFTER_TASK_COMPLETE: Optional[bool] = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    管理应用的生命周期事件。
    启动时：重置任务状态，加载并启动调度器。
    关闭时：确保终止所有子进程和调度器。
    """
    # 启动
    await _set_all_tasks_stopped_in_config()
    await reload_scheduler_jobs()
    if not scheduler.running:
        scheduler.start()

    yield

    # 关闭
    if scheduler.running:
        print("正在关闭调度器...")
        scheduler.shutdown()

    global fetcher_processes
    if fetcher_processes:
        print("Web服务器正在关闭，正在终止所有数据收集脚本进程...")
        stop_tasks = [stop_task_process(task_id) for task_id in list(fetcher_processes.keys())]
        await asyncio.gather(*stop_tasks)
        print("所有数据收集脚本进程已终止。")

    await _set_all_tasks_stopped_in_config()


def load_notification_settings():
    """从.env文件加载通知设置"""
    from dotenv import dotenv_values
    config = dotenv_values(".env")

    return {
        "NTFY_TOPIC_URL": config.get("NTFY_TOPIC_URL", ""),
        "NTFY_ENABLED": config.get("NTFY_ENABLED", "false").lower() == "true",
        "GOTIFY_URL": config.get("GOTIFY_URL", ""),
        "GOTIFY_TOKEN": config.get("GOTIFY_TOKEN", ""),
        "GOTIFY_ENABLED": config.get("GOTIFY_ENABLED", "false").lower() == "true",
        "BARK_URL": config.get("BARK_URL", ""),
        "BARK_ENABLED": config.get("BARK_ENABLED", "false").lower() == "true",
        "WX_BOT_URL": config.get("WX_BOT_URL", ""),
        "WX_BOT_ENABLED": config.get("WX_BOT_ENABLED", "false").lower() == "true",
        "WX_CORP_ID": config.get("WX_CORP_ID", ""),
        "WX_AGENT_ID": config.get("WX_AGENT_ID", ""),
        "WX_SECRET": config.get("WX_SECRET", ""),
        "WX_TO_USER": config.get("WX_TO_USER", ""),
        "WX_APP_ENABLED": config.get("WX_APP_ENABLED", "false").lower() == "true",
        "TELEGRAM_BOT_TOKEN": config.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": config.get("TELEGRAM_CHAT_ID", ""),
        "TELEGRAM_ENABLED": config.get("TELEGRAM_ENABLED", "false").lower() == "true",
        "WEBHOOK_URL": config.get("WEBHOOK_URL", ""),
        "WEBHOOK_ENABLED": config.get("WEBHOOK_ENABLED", "false").lower() == "true",
        "WEBHOOK_METHOD": config.get("WEBHOOK_METHOD", "POST"),
        "WEBHOOK_HEADERS": config.get("WEBHOOK_HEADERS", ""),
        "WEBHOOK_CONTENT_TYPE": config.get("WEBHOOK_CONTENT_TYPE", "JSON"),
        "WEBHOOK_QUERY_PARAMETERS": config.get("WEBHOOK_QUERY_PARAMETERS", ""),
        "WEBHOOK_BODY": config.get("WEBHOOK_BODY", ""),
        "PCURL_TO_MOBILE": config.get("PCURL_TO_MOBILE", "true").lower() == "true",
        "NOTIFY_AFTER_TASK_COMPLETE": config.get("NOTIFY_AFTER_TASK_COMPLETE", "true").lower() == "true"
    }


def save_notification_settings(settings: dict):
    """将通知设置保存到.env文件"""
    env_file = ".env"
    env_lines = []

    # 读取现有的.env文件
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()

    # 更新或添加通知设置
    setting_keys = [
        "NTFY_TOPIC_URL", "NTFY_ENABLED", "GOTIFY_URL", "GOTIFY_TOKEN", "GOTIFY_ENABLED",
        "BARK_URL", "BARK_ENABLED", "WX_BOT_URL", "WX_BOT_ENABLED", "WX_CORP_ID", "WX_AGENT_ID", 
        "WX_SECRET", "WX_TO_USER", "WX_APP_ENABLED", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", 
        "TELEGRAM_ENABLED", "WEBHOOK_URL", "WEBHOOK_ENABLED", "WEBHOOK_METHOD", "WEBHOOK_HEADERS", 
        "WEBHOOK_CONTENT_TYPE", "WEBHOOK_QUERY_PARAMETERS", "WEBHOOK_BODY", "PCURL_TO_MOBILE", "NOTIFY_AFTER_TASK_COMPLETE"
    ]

    # 创建现有设置的字典
    existing_settings = {}
    for line in env_lines:
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.split('=', 1)
            existing_settings[key.strip()] = value.strip()

    # 使用新设置更新
    existing_settings.update(settings)

    # 写回文件
    with open(env_file, 'w', encoding='utf-8') as f:
        for key in setting_keys:
            value = existing_settings.get(key, "")
            if key == "PCURL_TO_MOBILE":
                f.write(f"{key}={str(value).lower()}\n")
            else:
                f.write(f"{key}={value}\n")

        # 写入不是通知设置的其他现有设置
        for key, value in existing_settings.items():
            if key not in setting_keys:
                f.write(f"{key}={value}\n")


def load_ai_settings():
    """从.env文件加载AI模型设置"""
    from dotenv import dotenv_values
    config = dotenv_values(".env")

    return {
        "OPENAI_API_KEY": config.get("OPENAI_API_KEY", ""),
        "OPENAI_BASE_URL": config.get("OPENAI_BASE_URL", ""),
        "OPENAI_MODEL_NAME": config.get("OPENAI_MODEL_NAME", ""),
        "PROXY_URL": config.get("PROXY_URL", "")
    }


def save_ai_settings(settings: dict):
    """将AI模型设置保存到.env文件"""
    env_file = ".env"
    env_lines = []

    # 读取现有的.env文件
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()

    # 更新或添加AI设置
    setting_keys = [
        "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL_NAME", "PROXY_URL"
    ]

    # 创建现有设置的字典
    existing_settings = {}
    for line in env_lines:
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.split('=', 1)
            existing_settings[key.strip()] = value.strip()

    # 使用新设置更新
    existing_settings.update(settings)

    # 写回文件
    with open(env_file, 'w', encoding='utf-8') as f:
        for key in setting_keys:
            value = existing_settings.get(key, "")
            f.write(f"{key}={value}\n")

        # 写入不是AI设置的其他现有设置
        for key, value in existing_settings.items():
            if key not in setting_keys:
                f.write(f"{key}={value}\n")


app = FastAPI(title="咸鱼公开内容查看智能处理程序", lifespan=lifespan)

# --- 认证配置 ---
security = HTTPBasic()

# 从环境变量读取认证凭据
def get_auth_credentials():
    """从环境变量获取认证凭据"""
    username = os.getenv("WEB_USERNAME", "admin")
    password = os.getenv("WEB_PASSWORD", "admin123")
    # 如果环境变量的值为空字符串，使用默认值
    username = username or "admin"
    password = password or "admin123"
    return username, password

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """验证Basic认证凭据，如果用户名和密码都为空则允许匿名访问"""
    username, password = get_auth_credentials()
    
    # 如果配置的用户名和密码都为空，则允许直接访问，无需认证
    if not username and not password:
        return "anonymous"
    
    # 否则检查用户名和密码是否匹配
    if credentials.username == username and credentials.password == password:
        return credentials.username
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Basic"},
        )

#  ---用于进程和调度器管理的全局变量---
fetcher_processes = {}  # 将单个进程变量改为字典，以管理多个任务进程 {task_id: process}
login_process = None     # 跟踪当前运行的登录进程
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

# 自定义静态文件处理器，添加认证
class AuthenticatedStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        # 检查配置的用户名和密码是否都为空，如果是则直接允许访问，无需认证
        expected_username, expected_password = get_auth_credentials()
        if not expected_username and not expected_password:
            # 无需认证，直接处理静态文件
            await super().__call__(scope, receive, send)
            return
            
        # 需要认证的情况
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

        # 验证凭据
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

        # 认证成功，继续处理静态文件
        await super().__call__(scope, receive, send)

# Mount static files with authentication
app.mount("/static", AuthenticatedStaticFiles(directory="static"), name="static")

# Mount logo directory with authentication
app.mount("/logo", AuthenticatedStaticFiles(directory="logo"), name="logo")

# Setup templates
templates = Jinja2Templates(directory="templates")

# --- 调度器功能 ---
async def run_single_task(task_id: int, task_name: str):
    """
    由调度器调用的函数，用于启动单个公开内容查看任务。
    """
    print(f"定时任务触发: 正在为任务 '{task_name}' 启动公开内容查看脚本...")
    log_file_handle = None
    try:
        # 更新任务状态为“运行中”
        await update_task_running_status(task_id, True)

        # 确保日志目录存在，并以追加模式打开日志文件
        os.makedirs("logs", exist_ok=True)
        log_file_path = os.path.join("logs", "fetcher.log")
        log_file_handle = open(log_file_path, 'a', encoding='utf-8')

        # 使用与Web服务器相同的Python解释器来运行爬虫脚本
        # 将 stdout 和 stderr 重定向到日志文件
        # 在非 Windows 系统上，使用 setsid 创建新进程组，以便能终止整个进程树
        preexec_fn = os.setsid if sys.platform != "win32" else None
        # 为子进程强制设置 UTF-8 输出，确保日志统一为 UTF-8 编码
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "collector.py", "--task-name", task_name,
            stdout=log_file_handle,
            stderr=log_file_handle,
            preexec_fn=preexec_fn,
            env=child_env
        )

        # 等待进程结束
        await process.wait()
        if process.returncode == 0:
            print(f"定时任务 '{task_name}' 执行成功。日志已写入 {log_file_path}")
        else:
            print(f"定时任务 '{task_name}' 执行失败。返回码: {process.returncode}。详情请查看 {log_file_path}")

    except Exception as e:
        print(f"启动定时任务 '{task_name}' 时发生错误: {e}")
    finally:
        # 确保文件句柄被关闭
        if log_file_handle:
            log_file_handle.close()
        # 任务结束后，更新状态为“已停止”
        await update_task_running_status(task_id, False)


async def _set_all_tasks_stopped_in_config():
    """读取配置文件，将所有任务的 is_running 状态和 generating_ai_criteria 状态设置为 false。"""
    try:
        # 使用 aiofiles 异步读写
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            if not content.strip():
                return
            tasks = json.loads(content)

        # 检查是否有任何任务的状态需要被更新
        needs_update = any(task.get('is_running') or task.get('generating_ai_criteria') for task in tasks)

        if needs_update:
            for task in tasks:
                task['is_running'] = False
                task['generating_ai_criteria'] = False

            async with aiofiles.open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(tasks, ensure_ascii=False, indent=2))
            print("所有任务状态已在配置文件中重置为“已停止”，生成状态已重置为“未生成”。")

    except FileNotFoundError:
        # 配置文件不存在，无需操作
        pass
    except Exception as e:
        print(f"重置任务状态时出错: {e}")


async def reload_scheduler_jobs():
    """
    重新加载所有定时任务。清空现有任务，并从 config.json 重新创建。
    """
    print("正在重新加载定时任务调度器...")
    sys.stdout.flush()  # 立即刷新输出缓冲区
    scheduler.remove_all_jobs()
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            if not content.strip():  # 检查文件内容是否为空
                tasks = []
            else:
                tasks = json.loads(content)

        for i, task in enumerate(tasks):
            task_name = task.get("task_name")
            cron_str = task.get("cron")
            is_enabled = task.get("enabled", False)

            if task_name and cron_str and is_enabled:
                try:
                    # 使用 CronTrigger.from_crontab 更稳健
                    trigger = CronTrigger.from_crontab(cron_str)
                    scheduler.add_job(
                        run_single_task,
                        trigger=trigger,
                        args=[i, task_name],
                        id=f"task_{i}",
                        name=f"Scheduled: {task_name}",
                        replace_existing=True
                    )
                    print(f"  -> 已为任务 '{task_name}' 添加定时规则: '{cron_str}'")
                except ValueError as e:
                    print(f"  -> [警告] 任务 '{task_name}' 的 Cron 表达式 '{cron_str}' 无效，已跳过: {e}")

    except FileNotFoundError:
        # 配置文件不存在是首次使用的正常现象，不显示警告
        pass
    except Exception as e:
        print(f"[错误] 重新加载定时任务时发生错误: {e}")

    print("定时任务加载完成。")
    sys.stdout.flush()  # 立即刷新输出缓冲区
    if scheduler.get_jobs():
        print("当前已调度的任务:")
        scheduler.print_jobs()
        sys.stdout.flush()  # 立即刷新输出缓冲区


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
    """
    提供 Web UI 的主页面。
    """
    return templates.TemplateResponse("index.html", {"request": request, "version": VERSION})


@app.get("/api/version")
async def get_version(username: str = Depends(verify_credentials)):
    """
    获取当前系统版本信息。
    """
    from src.version import get_current_version_info
    return {
        "version": VERSION,
        "info": get_current_version_info()
    }

# --- API 端点 ---

CONFIG_FILE = "config.json"

@app.get("/api/tasks")
async def get_tasks(username: str = Depends(verify_credentials)):
    """
    读取并返回 config.json 中的所有任务。
    """
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            tasks = json.loads(content)
            # 为每个任务添加一个唯一的 id
            for i, task in enumerate(tasks):
                task['id'] = i
            return tasks
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"配置文件 {CONFIG_FILE} 未找到。")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"配置文件 {CONFIG_FILE} 格式错误。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取任务配置时发生错误: {e}")


# Define a new Pydantic model for AI task generation with reference file
class TaskGenerateRequestWithReference(BaseModel):
    task_name: str
    keyword: str
    description: str
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    max_pages: int = 3
    cron: Optional[str] = None
    reference_file: Optional[str] = None  # New field for reference file

@app.post("/api/tasks/generate", response_model=dict)
async def generate_task(req: TaskGenerateRequestWithReference, username: str = Depends(verify_credentials)):
    """
    使用 AI 生成一个新的分析标准文件，并据此创建一个新任务。
    """
    print(f"收到 AI 任务生成请求: {req.task_name}")

    # 1. 为标准文件生成唯一的文件名，使用任务名称并添加适当后缀
    # 处理任务名称中的特殊字符
    safe_task_name = "".join(c for c in req.task_name.replace(' ', '_') if c.isalnum() or c in "_-").rstrip()
    # 生成包含"_requirement"后缀的文件名，并存储到/requirement目录
    requirement_filename = f"requirement/{safe_task_name}_requirement.txt"
    
    # 2. 创建包含详细购买需求的文件内容
    try:
        # 确保目录存在
        os.makedirs("requirement", exist_ok=True)
        
        # 生成包含详细购买需求的内容
        generated_criteria = req.description
        
        # 将内容保存到requirement目录
        async with aiofiles.open(requirement_filename, 'w', encoding='utf-8') as f:
            await f.write(generated_criteria)
        print(f"新的需求文件已保存到: {requirement_filename}")
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"保存需求文件失败: {e}")

    # 3. 创建新任务对象，初始指向requirement目录的文件
    new_task = {
        "task_name": req.task_name,
        "enabled": True,
        "keyword": req.keyword,
        "max_pages": req.max_pages,
        "personal_only": req.personal_only,
        "min_price": req.min_price,
        "max_price": req.max_price,
        "cron": req.cron,
        "description": req.description,
        "ai_prompt_base_file": "prompts/base_prompt.txt",
        "ai_prompt_criteria_file": requirement_filename,
        "is_running": False
    }

    # 5. 确保任务名称唯一
    from src.task import add_task, Task
    
    try:
        # Read existing tasks
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            existing_tasks = json.loads(await f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        existing_tasks = []
    
    # Ensure unique task name with auto-incrementing copy count
    original_name = new_task["task_name"]
    base_name = original_name
    copy_count = 0
    
    # Extract base name and copy count from original if it already ends with (副本) or (副本n)
    import re
    # 匹配中文格式：原名称 (副本) 或 原名称 (副本n)
    match = re.match(r'^(.+?)(?:\s+\((副本)(\d+)?\))?$', original_name)
    if match:
        base_name = match.group(1)
        if match.group(3):  # 如果已有数字后缀
            copy_count = int(match.group(3))
        elif match.group(2):  # 如果只有"副本"没有数字
            copy_count = 1
    
    # Check for existing task names
    while True:
        # Format the task name - always use Chinese "(副本n)" format
        if copy_count == 0:
            current_name = original_name
        else:
            current_name = f"{base_name} (副本{copy_count})"
        
        # Check if name exists
        exists = any(existing_task['task_name'] == current_name for existing_task in existing_tasks)
        if not exists:
            # Update the task name
            new_task["task_name"] = current_name
            break
        
        # Increment copy count and try again
        copy_count += 1
    
    # Create Task object and add it
    task_obj = Task(**new_task)
    success = await add_task(task_obj)
    if not success:
        # 如果更新失败，最好能把刚刚创建的文件删掉，以保持一致性
        if os.path.exists(requirement_filename):
            os.remove(requirement_filename)
        if 'criteria_filename' in locals() and os.path.exists(criteria_filename):
            os.remove(criteria_filename)
        raise HTTPException(status_code=500, detail="更新配置文件 config.json 失败。")

    # 重新加载调度器以包含新任务
    await reload_scheduler_jobs()

    # 6. 返回成功创建的任务（包含ID）
    async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        tasks = json.loads(await f.read())
    
    # Find the newly created task by task_name
    new_task_with_id = None
    for idx, t in enumerate(tasks):
        if t['task_name'] == task_obj.task_name:
            new_task_with_id = t.copy()
            new_task_with_id['id'] = idx
            break

    return {"message": "AI 任务创建成功。", "task": new_task_with_id}


@app.post("/api/tasks", response_model=dict)
async def create_task(task: Task, username: str = Depends(verify_credentials)):
    """
    创建一个新任务并将其添加到 config.json。
    如果是复制任务，会复制原任务的 criteria 文件并自动重命名
    """
    # Delegate to add_task function from src.task to ensure unique task names
    from src.task import add_task
    
    # Check if this is a copy operation (we need to duplicate the criteria/requirement file)
    # Copy the file with new name if it's not the default base prompt
    original_criteria_file = task.ai_prompt_criteria_file
    
    # Only copy the file if it's not the base prompt
    if original_criteria_file != "prompts/base_prompt.txt":
        # Extract new filename based on unique task name that will be generated
        # First get the unique task name (this will be set by add_task)
        import re
        
        # Read existing tasks to determine what the unique name will be
        try:
            async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                existing_tasks = json.loads(await f.read())
        except (FileNotFoundError, json.JSONDecodeError):
            existing_tasks = []
        
        # Apply the same unique name generation logic as in add_task
        original_name = task.task_name
        base_name = original_name
        copy_count = 0
        
        # 匹配中文格式：原名称 (副本) 或 原名称 (副本n)
        match = re.match(r'^(.+?)(?:\s+\((副本)(\d+)?\))?$', original_name)
        if match:
            base_name = match.group(1)
            if match.group(3):  # 如果已有数字后缀
                copy_count = int(match.group(3))
            elif match.group(2):  # 如果只有"副本"没有数字
                copy_count = 1
        
        # Generate unique task name - always use Chinese "(副本n)" format
        while True:
            if copy_count == 0:
                current_name = original_name
            else:
                current_name = f"{base_name} (副本{copy_count})"
            
            exists = any(existing_task['task_name'] == current_name for existing_task in existing_tasks)
            if not exists:
                unique_task_name = current_name
                break
            
            # Increment copy count and try again
            copy_count += 1
        
        # Generate new filename based on unique task name
        safe_task_name = "".join(c for c in unique_task_name.lower().replace(' ', '_') if c.isalnum() or c in "_-").rstrip()
        
    # Determine if the original file is a requirement or criteria file
    is_requirement_file = original_criteria_file.startswith("requirement/")
    
    # Copy both requirement and criteria files if they exist
    try:
        # Check if original is a requirement file or criteria file
        if is_requirement_file:
            # Original is a requirement file
            # Generate new requirement file path
            new_requirement_file = f"requirement/{safe_task_name}_requirement.txt"
            
            # Generate corresponding criteria file path
            new_criteria_file_candidate = f"criteria/{safe_task_name}_criteria.txt"
            
            # Copy the requirement file
            async with aiofiles.open(original_criteria_file, 'r', encoding='utf-8') as src:
                requirement_content = await src.read()
            
            os.makedirs("requirement", exist_ok=True)
            async with aiofiles.open(new_requirement_file, 'w', encoding='utf-8') as dst:
                await dst.write(requirement_content)
            
            # Check if there's a corresponding criteria file for the original requirement
            original_criteria_file_candidate = original_criteria_file.replace("requirement/", "criteria/").replace("_requirement.txt", "_criteria.txt")
            if os.path.exists(original_criteria_file_candidate):
                # Copy the criteria file too
                async with aiofiles.open(original_criteria_file_candidate, 'r', encoding='utf-8') as src:
                    criteria_content = await src.read()
                
                os.makedirs("criteria", exist_ok=True)
                async with aiofiles.open(new_criteria_file_candidate, 'w', encoding='utf-8') as dst:
                    await dst.write(criteria_content)
                
                # Update the task to use the new criteria file
                task.ai_prompt_criteria_file = new_criteria_file_candidate
            else:
                # No corresponding criteria file, use the new requirement file
                task.ai_prompt_criteria_file = new_requirement_file
        else:
            # Original is a criteria file
            # Generate new criteria file path
            new_criteria_file = f"criteria/{safe_task_name}_criteria.txt"
            
            # Generate corresponding requirement file path
            new_requirement_file_candidate = f"requirement/{safe_task_name}_requirement.txt"
            
            # Copy the criteria file
            async with aiofiles.open(original_criteria_file, 'r', encoding='utf-8') as src:
                criteria_content = await src.read()
            
            os.makedirs("criteria", exist_ok=True)
            async with aiofiles.open(new_criteria_file, 'w', encoding='utf-8') as dst:
                await dst.write(criteria_content)
            
            # Check if there's a corresponding requirement file for the original criteria
            original_requirement_file_candidate = original_criteria_file.replace("criteria/", "requirement/").replace("_criteria.txt", "_requirement.txt")
            if os.path.exists(original_requirement_file_candidate):
                # Copy the requirement file too
                async with aiofiles.open(original_requirement_file_candidate, 'r', encoding='utf-8') as src:
                    requirement_content = await src.read()
                
                os.makedirs("requirement", exist_ok=True)
                async with aiofiles.open(new_requirement_file_candidate, 'w', encoding='utf-8') as dst:
                    await dst.write(requirement_content)
            
            # Update the task to use the new criteria file
            task.ai_prompt_criteria_file = new_criteria_file
            
    except Exception as e:
        # If copying fails, fall back to using the original file
        print(f"Warning: Failed to copy criteria/requirement file: {e}")
    
    success = await add_task(task)
    if not success:
        # If task creation fails and we created a new criteria file, clean it up
        if 'new_criteria_file' in locals() and os.path.exists(new_criteria_file):
            try:
                os.remove(new_criteria_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"写入配置文件时发生错误。")
    
    # Get the created task with proper ID
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())
        
        created_task = None
        for idx, t in enumerate(tasks):
            if t['task_name'] == task.task_name:
                created_task = t.copy()
                created_task['id'] = idx
                break
        
        await reload_scheduler_jobs()
        return {"message": "任务创建成功。", "task": created_task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入配置文件时发生错误: {e}")


from fastapi import BackgroundTasks  # Add this import if not already present

@app.patch("/api/tasks/{task_id}", response_model=dict)
async def update_task_api(task_id: int, task_update: TaskUpdate, background_tasks: BackgroundTasks, username: str = Depends(verify_credentials)):
    """
    更新指定ID任务的属性。
    """
    task = await get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到。")

    # 更新数据
    update_data = task_update.model_dump(exclude_unset=True)

    if not update_data:
        return JSONResponse(content={"message": "数据无变化，未执行更新。"}, status_code=200)

    # 如果有description更新，则异步生成AI标准
    if 'description' in update_data:
        # 更新generating_ai_criteria状态为true
        update_data['generating_ai_criteria'] = True
        
        # 创建一个异步任务来生成AI标准
        async def generate_ai_criteria_background(task_id: int, task: dict, user_description: str, reference_file: str = "prompts/base_prompt.txt"):
            import re
            # 检查task是否是Pydantic模型实例
            if hasattr(task, '__dict__'):
                # 如果是模型实例，使用属性访问
                safe_task_name = re.sub(r'[^\w\s_-]', '', task.task_name.replace(' ', '_'))
            else:
                # 如果是字典，使用索引访问
                safe_task_name = re.sub(r'[^\w\s_-]', '', task['task_name'].replace(' ', '_'))
            criteria_filename = f"criteria/{safe_task_name}_criteria.txt"
            
            try:
                generated_criteria = await generate_criteria(
                    user_description=user_description,
                    reference_file_path=reference_file
                )
                
                if generated_criteria:
                    # 将生成的内容保存到criteria目录
                    os.makedirs("criteria", exist_ok=True)
                    async with aiofiles.open(criteria_filename, 'w', encoding='utf-8') as f:
                        await f.write(generated_criteria)
                    
                    print(f"新的标准文件已保存到: {criteria_filename}")
                    
                    # 更新任务状态和文件路径
                    task['ai_prompt_criteria_file'] = criteria_filename
                    task['generating_ai_criteria'] = False
                    
                    await update_task(task_id, task)
            except Exception as e:
                print(f"调用AI生成标准时出错: {e}")
                # 更新状态为生成失败
                task['generating_ai_criteria'] = False
                await update_task(task_id, task)
        
        # 添加后台任务
        # 将task转换为字典后传递，避免Pydantic模型在后台任务中使用字典索引访问出错
        background_tasks.add_task(
            generate_ai_criteria_background, 
            task_id, 
            task.model_dump(),  # 传递字典而不是模型实例
            update_data['description']
        )

    # 如果任务从“启用”变为“禁用”，且正在运行，则先停止它
    if 'enabled' in update_data and not update_data['enabled']:
        # 更新is_running为false立即返回给前端
        update_data['is_running'] = False
        
        if fetcher_processes.get(task_id):
            print(f"任务 '{task['task_name']}' 已被禁用，正在停止其进程...")
            # 后台停止进程，不等待
            asyncio.create_task(stop_task_process(task_id))
        else:
            # 如果进程不存在，但is_running是true，直接更新配置
            task['is_running'] = False

    # Apply updates
    task_dict = task.model_dump()  # 将Pydantic模型转换为字典
    task_dict.update(update_data)  # 使用字典的update()方法更新数据
    task = Task(**task_dict)  # 将字典转换回Pydantic模型

    success = await update_task(task_id, task)

    if not success:
        raise HTTPException(status_code=500, detail=f"写入配置文件时发生错误")

    return {"message": "任务更新请求已提交。" if 'description' in update_data else "任务更新成功。", "task": task}

async def start_task_process(task_id: int, task_name: str):
    """内部函数：启动一个指定的任务进程。"""
    global fetcher_processes
    if fetcher_processes.get(task_id) and fetcher_processes[task_id].returncode is None:
        print(f"任务 '{task_name}' (ID: {task_id}) 已在运行中。")
        return

    try:
        os.makedirs("logs", exist_ok=True)
        log_file_path = os.path.join("logs", "fetcher.log")
        log_file_handle = open(log_file_path, 'a', encoding='utf-8')

        preexec_fn = os.setsid if sys.platform != "win32" else None
        # 为子进程强制设置 UTF-8 输出，确保日志统一为 UTF-8 编码
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "collector.py", "--task-name", task_name,
            stdout=log_file_handle,
            stderr=log_file_handle,
            preexec_fn=preexec_fn,
            env=child_env
        )
        fetcher_processes[task_id] = process
        print(f"启动任务 '{task_name}' (PID: {process.pid})，日志输出到 {log_file_path}")

        # 更新配置文件中的状态
        await update_task_running_status(task_id, True)
        
        # 创建一个后台任务来等待进程完成并更新状态
        async def monitor_process():
            try:
                await process.wait()
                print(f"任务 '{task_name}' (ID: {task_id}) 进程已结束，返回码: {process.returncode}")
            finally:
                # 无论进程如何结束，都更新状态
                await update_task_running_status(task_id, False)
                # 清理进程字典
                if task_id in fetcher_processes:
                    del fetcher_processes[task_id]
        
        # 启动监控后台任务
        asyncio.create_task(monitor_process())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动任务 '{task_name}' 进程时出错: {e}")


async def stop_task_process(task_id: int):
    """内部函数：停止一个指定的任务进程。"""
    global fetcher_processes
    process = fetcher_processes.get(task_id)
    if not process or process.returncode is not None:
        print(f"任务ID {task_id} 没有正在运行的进程。")
        # 确保配置文件状态正确
        await update_task_running_status(task_id, False)
        if task_id in fetcher_processes:
            del fetcher_processes[task_id]
        return

    try:
        if sys.platform != "win32":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()

        await process.wait()
        print(f"任务进程 {process.pid} (ID: {task_id}) 已终止。")
    except ProcessLookupError:
        print(f"试图终止的任务进程 (ID: {task_id}) 已不存在。")
    except Exception as e:
        print(f"停止任务进程 (ID: {task_id}) 时出错: {e}")
    finally:
        await update_task_running_status(task_id, False)


async def update_task_running_status(task_id: int, is_running: bool):
    """更新 config.json 中指定任务的 is_running 状态。"""
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())

        if 0 <= task_id < len(tasks):
            tasks[task_id]['is_running'] = is_running
            async with aiofiles.open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(tasks, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"更新任务 {task_id} 状态时出错: {e}")


@app.post("/api/tasks/start/{task_id}", response_model=dict)
async def start_single_task(task_id: int, username: str = Depends(verify_credentials)):
    """启动单个任务。"""
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")

        task = tasks[task_id]
        if not task.get("enabled", False):
            raise HTTPException(status_code=400, detail="任务已被禁用，无法启动。")

        await start_task_process(task_id, task['task_name'])
        return {"message": f"任务 '{task['task_name']}' 已启动。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/stop/{task_id}", response_model=dict)
async def stop_single_task(task_id: int, username: str = Depends(verify_credentials)):
    """停止单个任务。"""
    await stop_task_process(task_id)
    return {"message": f"任务ID {task_id} 已发送停止信号。"}




@app.get("/api/logs")
async def get_logs(from_pos: int = 0, task_name: str = None, username: str = Depends(verify_credentials)):
    """
    获取爬虫日志文件的内容。支持从指定位置增量读取和任务名称筛选。
    """
    log_file_path = os.path.join("logs", "fetcher.log")
    if not os.path.exists(log_file_path):
        return JSONResponse(content={"new_content": "日志文件不存在或尚未创建。", "new_pos": 0})

    try:
        # 使用二进制模式打开以精确获取文件大小和位置
        async with aiofiles.open(log_file_path, 'rb') as f:
            await f.seek(0, os.SEEK_END)
            file_size = await f.tell()

            # 如果客户端的位置已经是最新的，直接返回
            if from_pos >= file_size:
                return {"new_content": "", "new_pos": file_size}

            await f.seek(from_pos)
            new_bytes = await f.read()

        # 解码获取的字节（统一按 UTF-8 解码，容错处理尾部可能出现的半个多字节字符）
        new_content = new_bytes.decode('utf-8', errors='replace')

        # 如果提供了任务名称，筛选包含该任务名称的日志行
        if task_name:
            filtered_lines = []
            for line in new_content.split('\n'):
                if task_name in line:
                    filtered_lines.append(line)
            new_content = '\n'.join(filtered_lines)

        return {"new_content": new_content, "new_pos": file_size}

    except Exception as e:
        # 返回错误信息，同时保持位置不变，以便下次重试
        return JSONResponse(
            status_code=500,
            content={"new_content": f"\n读取日志文件时出错: {e}", "new_pos": from_pos}
        )


@app.delete("/api/logs", response_model=dict)
async def clear_logs(username: str = Depends(verify_credentials)):
    """
    清空日志文件内容。
    """
    log_file_path = os.path.join("logs", "fetcher.log")
    if not os.path.exists(log_file_path):
        return {"message": "日志文件不存在，无需清空。"}

    try:
        # 使用 'w' 模式打开文件会清空内容
        async with aiofiles.open(log_file_path, 'w', encoding='utf-8') as f:
            await f.write("")
        return {"message": "日志已成功清空。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空日志文件时出错: {e}")


@app.delete("/api/tasks/{task_id}", response_model=dict)
async def delete_task(task_id: int, username: str = Depends(verify_credentials)):
    """
    从 config.json 中删除指定ID的任务。
    """
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"读取或解析配置文件失败: {e}")

    if not (0 <= task_id < len(tasks)):
        raise HTTPException(status_code=404, detail="任务未找到。")

    # 如果任务正在运行，先停止它
    if fetcher_processes.get(task_id):
        await stop_task_process(task_id)

    deleted_task = tasks.pop(task_id)

    # 尝试删除关联的 criteria 文件和对应的 requirement 文件
    criteria_file = deleted_task.get("ai_prompt_criteria_file")
    if criteria_file and os.path.exists(criteria_file):
        try:
            os.remove(criteria_file)
            print(f"成功删除关联的分析标准文件: {criteria_file}")
        except OSError as e:
            # 如果文件删除失败，只记录日志，不中断主流程
            print(f"警告: 删除文件 {criteria_file} 失败: {e}")
    
    # 检查是否有对应的requirement文件需要删除
    if criteria_file:
        # 检查是否是criteria目录下的文件
        if criteria_file.startswith("criteria/"):
            # 生成对应的requirement文件路径
            requirement_file = criteria_file.replace("criteria/", "requirement/").replace("_criteria.txt", "_requirement.txt")
            if os.path.exists(requirement_file):
                try:
                    os.remove(requirement_file)
                    print(f"成功删除关联的需求文件: {requirement_file}")
                except OSError as e:
                    print(f"警告: 删除文件 {requirement_file} 失败: {e}")
        # 检查是否是requirement目录下的文件
        elif criteria_file.startswith("requirement/"):
            # 生成对应的criteria文件路径
            criteria_file_candidate = criteria_file.replace("requirement/", "criteria/").replace("_requirement.txt", "_criteria.txt")
            if os.path.exists(criteria_file_candidate):
                try:
                    os.remove(criteria_file_candidate)
                    print(f"成功删除关联的分析标准文件: {criteria_file_candidate}")
                except OSError as e:
                    print(f"警告: 删除文件 {criteria_file_candidate} 失败: {e}")

    try:
        async with aiofiles.open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(tasks, ensure_ascii=False, indent=2))

        await reload_scheduler_jobs()

        return {"message": "任务删除成功。", "task_name": deleted_task.get("task_name")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入配置文件时发生错误: {e}")


@app.get("/api/results/files")
async def list_result_files(username: str = Depends(verify_credentials)):
    """
    列出所有生成的 .jsonl 结果文件。
    """
    jsonl_dir = "jsonl"
    if not os.path.isdir(jsonl_dir):
        return {"files": []}
    files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
    return {"files": files}


@app.delete("/api/results/files/{filename}", response_model=dict)
async def delete_result_file(filename: str, username: str = Depends(verify_credentials)):
    """
    删除指定的结果文件。
    """
    # 处理"所有结果"的情况
    if filename == "all":
        jsonl_dir = "jsonl"
        if not os.path.isdir(jsonl_dir):
            return {"message": "结果文件目录未找到。"}
        
        # 获取所有.jsonl文件
        files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
        if not files:
            return {"message": "没有结果文件需要删除。"}
        
        # 删除所有.jsonl文件
        deleted_count = 0
        for file in files:
            try:
                filepath = os.path.join(jsonl_dir, file)
                os.remove(filepath)
                deleted_count += 1
            except Exception as e:
                print(f"删除文件 {file} 时出错: {e}")
        
        return {"message": f"已成功删除 {deleted_count} 个结果文件。"}
    
    # 处理单个文件的情况
    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    filepath = os.path.join("jsonl", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="结果文件未找到。")

    try:
        os.remove(filepath)
        return {"message": f"结果文件 '{filename}' 已成功删除。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除结果文件时出错: {e}")


# 定义用于删除商品的请求模型
class DeleteResultItemRequest(BaseModel):
    filename: str
    item: dict

@app.post("/api/results/delete", response_model=dict)
async def delete_result_item(request: DeleteResultItemRequest, username: str = Depends(verify_credentials)):
    """
    从指定结果文件中删除指定的商品记录。
    """
    try:
        filename = request.filename
        item_to_delete = request.item
        
        # 处理"所有结果"的情况
        if filename == "all":
            jsonl_dir = "jsonl"
            if not os.path.isdir(jsonl_dir):
                raise HTTPException(status_code=404, detail="结果文件目录未找到。")
            
            # 获取所有.jsonl文件
            files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
            if not files:
                raise HTTPException(status_code=404, detail="没有结果文件需要删除。")
            
            deleted_from_file = None
            found_record = False
            
            # 遍历所有文件查找要删除的记录
            for file in files:
                filepath = os.path.join(jsonl_dir, file)
                
                # 读取当前文件的所有记录
                records = []
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            record = json.loads(line)
                            records.append(record)
                        except json.JSONDecodeError:
                            continue
                
                # 查找匹配的记录
                import re
                # 从要删除的商品信息中提取商品ID
                item_link = item_to_delete.get('商品信息', {}).get('商品链接', '')
                match = re.search(r'id=(\d+)', item_link)
                item_id_to_delete = match.group(1) if match else ''
                
                for i, record in enumerate(records):
                    # 从当前记录的商品链接中提取商品ID
                    record_link = record.get('商品信息', {}).get('商品链接', '')
                    match = re.search(r'id=(\d+)', record_link)
                    record_item_id = match.group(1) if match else ''
                    
                    # 比较商品ID来匹配记录
                    if record_item_id == item_id_to_delete:
                        # 删除记录
                        deleted_record = records.pop(i)
                        
                        # 写回更新后的记录
                        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                            for record in records:
                                await f.write(json.dumps(record, ensure_ascii=False) + '\n')
                        
                        found_record = True
                        deleted_from_file = file
                        break
                
                if found_record:
                    break
            
            if found_record:
                return {"message": f"商品记录已成功删除。", "file": deleted_from_file}
            else:
                raise HTTPException(status_code=404, detail="商品记录未找到。")
        
        # 处理单个文件的情况
        if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="无效的文件名。")
        
        filepath = os.path.join("jsonl", filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="结果文件未找到。")
        
        # 读取所有记录
        records = []
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            async for line in f:
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError:
                    continue
        
        # 查找匹配的记录
        found = False
        import re
        # 从要删除的商品信息中提取商品ID
        item_link = item_to_delete.get('商品信息', {}).get('商品链接', '')
        match = re.search(r'id=(\d+)', item_link)
        item_id_to_delete = match.group(1) if match else ''
        
        for i, record in enumerate(records):
            # 从当前记录的商品链接中提取商品ID
            record_link = record.get('商品信息', {}).get('商品链接', '')
            match = re.search(r'id=(\d+)', record_link)
            record_item_id = match.group(1) if match else ''
            
            # 比较商品ID来匹配记录
            if record_item_id == item_id_to_delete:
                # 删除记录
                deleted_record = records.pop(i)
                
                # 写回更新后的记录
                async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                    for record in records:
                        await f.write(json.dumps(record, ensure_ascii=False) + '\n')
                return {"message": f"商品记录已成功删除。"}
        
        # 如果没有找到记录
        raise HTTPException(status_code=404, detail="商品记录未找到。")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除商品记录时出错: {e}")


@app.get("/api/results/{filename}")
async def get_result_file_content(filename: str, page: int = 1, limit: int = 20, recommended_only: bool = False, task_name: str = None, keyword: str = None, ai_criteria: str = None, sort_by: str = "crawl_time", sort_order: str = "desc", manual_keyword: str = None, username: str = Depends(verify_credentials)):
    """
    读取指定的 .jsonl 文件内容，支持分页、筛选和排序。
    如果 filename 是 "all"，则返回所有结果文件的内容。
    """
    results = []
    
    # 处理"所有结果"的情况
    if filename == "all":
        jsonl_dir = "jsonl"
        if not os.path.isdir(jsonl_dir):
            raise HTTPException(status_code=404, detail="结果文件目录未找到。")
        
        # 获取所有.jsonl文件
        files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
        
        # 读取所有文件内容
        for file in files:
            filepath = os.path.join(jsonl_dir, file)
            try:
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            record = json.loads(line)
                            results.append(record)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"读取文件 {file} 时出错: {e}")
                continue
    else:
        # 处理单个文件的情况
        if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="无效的文件名。")
    
        filepath = os.path.join("jsonl", filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="结果文件未找到。")
    
        try:
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                async for line in f:
                    try:
                        record = json.loads(line)
                        results.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取结果文件时出错: {e}")
    
    # 应用所有筛选条件
    filtered_results = []
    for record in results:
        match = True
        
        # 推荐商品筛选
        if recommended_only:
            if record.get("ai_analysis", {}).get("is_recommended") is not True:
                match = False
        
        # 任务名称筛选
        if task_name and task_name != "all":
            if record.get("任务名称") != task_name:
                match = False
        
        # 搜索关键字筛选
        if keyword and keyword != "all":
            if record.get("搜索关键字") != keyword:
                match = False
        
        # AI标准筛选
        if ai_criteria and ai_criteria != "all":
            if record.get("AI标准") != ai_criteria:
                match = False
        
        # 手动关键词筛选
        if manual_keyword:
            manual_keyword_lower = manual_keyword.lower()
            # 检查商品标题、描述等字段是否包含关键词
            商品信息 = record.get("商品信息", {})
            商品标题 = 商品信息.get("商品标题", "").lower()
            商品描述 = 商品信息.get("商品描述", "").lower()
            卖家昵称 = 商品信息.get("卖家昵称", "").lower()
            当前售价 = 商品信息.get("当前售价", "").lower()
            AI建议 = record.get("ai_analysis", {}).get("reason", "").lower()
            
            # 检查所有相关字段是否包含关键词
            if manual_keyword_lower not in 商品标题 and \
               manual_keyword_lower not in 商品描述 and \
               manual_keyword_lower not in 卖家昵称 and \
               manual_keyword_lower not in 当前售价 and \
               manual_keyword_lower not in AI建议:
                match = False
        
        if match:
            filtered_results.append(record)

    # --- 排序逻辑 ---
    def get_sort_key(item):
        info = item.get("商品信息", {})
        if sort_by == "publish_time":
            # 根据顺序将“未知时间”放在末尾或开头来处理它
            return info.get("发布时间", "0000-00-00 00:00")
        elif sort_by == "price":
            price_str = str(info.get("当前售价", "0")).replace("¥", "").replace(",", "").strip()
            try:
                return float(price_str)
            except (ValueError, TypeError):
                return 0.0 # 无法解析价格时的默认值
        else: # 默认为公开信息浏览时间
            return item.get("公开信息浏览时间", "")

    is_reverse = (sort_order == "desc")
    filtered_results.sort(key=get_sort_key, reverse=is_reverse)

    total_items = len(filtered_results)
    start = (page - 1) * limit
    end = start + limit
    paginated_results = filtered_results[start:end]

    return {
        "total_items": total_items,
        "page": page,
        "limit": limit,
        "items": paginated_results
    }


@app.get("/api/settings/status")
async def get_system_status(username: str = Depends(verify_credentials)):
    """
    检查系统关键文件和配置的状态。
    """
    global fetcher_processes
    env_config = dotenv_values(".env")

    # 检查是否有任何任务进程仍在运行
    running_pids = []
    for task_id, process in list(fetcher_processes.items()):
        if process.returncode is None:
            running_pids.append(process.pid)
        else:
            # 进程已结束，从字典中清理
            print(f"检测到任务进程 {process.pid} (ID: {task_id}) 已结束，返回码: {process.returncode}。")
            del fetcher_processes[task_id]
            # 异步更新配置文件状态
            asyncio.create_task(update_task_running_status(task_id, False))
    status = {
        "scraper_running": len(running_pids) > 0,
        "login_state_file": {
            "exists": os.path.exists("xianyu_state.json"),
            "path": "xianyu_state.json"
        },
        "env_file": {
            "exists": os.path.exists(".env"),
            "openai_api_key_set": bool(env_config.get("OPENAI_API_KEY")),
            "openai_base_url_set": bool(env_config.get("OPENAI_BASE_URL")),
            "openai_model_name_set": bool(env_config.get("OPENAI_MODEL_NAME")),
            "ntfy_topic_url_set": bool(env_config.get("NTFY_TOPIC_URL")),
            "gotify_url_set": bool(env_config.get("GOTIFY_URL")),
            "gotify_token_set": bool(env_config.get("GOTIFY_TOKEN")),
            "bark_url_set": bool(env_config.get("BARK_URL")),
            "wx_bot_url_set": bool(env_config.get("WX_BOT_URL")),
            "wx_corp_id_set": bool(env_config.get("WX_CORP_ID")),
            "wx_agent_id_set": bool(env_config.get("WX_AGENT_ID")),
            "wx_secret_set": bool(env_config.get("WX_SECRET")),
            "telegram_bot_token_set": bool(env_config.get("TELEGRAM_BOT_TOKEN")),
            "telegram_chat_id_set": bool(env_config.get("TELEGRAM_CHAT_ID")),
            "webhook_url_set": bool(env_config.get("WEBHOOK_URL")),
        }
    }
    return status


PROMPTS_DIR = "prompts"

@app.get("/api/prompts")
async def list_prompts(username: str = Depends(verify_credentials)):
    """
    列出 prompts/ 目录下的所有 .txt 文件。
    """
    if not os.path.isdir(PROMPTS_DIR):
        return []
    return [f for f in os.listdir(PROMPTS_DIR) if f.endswith(".txt")]

class NewPromptRequest(BaseModel):
    filename: str
    content: str

@app.post("/api/prompts")
async def create_new_prompt(new_prompt: NewPromptRequest, username: str = Depends(verify_credentials)):
    """
    创建一个新的 prompt 文件。
    """
    if "/" in new_prompt.filename or ".." in new_prompt.filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    
    if not new_prompt.filename.endswith(".txt"):
        new_prompt.filename += ".txt"
    
    filepath = os.path.join(PROMPTS_DIR, new_prompt.filename)
    
    if os.path.exists(filepath):
        raise HTTPException(status_code=400, detail="该文件名已存在。")
    
    try:
        os.makedirs(PROMPTS_DIR, exist_ok=True)
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(new_prompt.content)
        return {"message": f"Prompt 文件 '{new_prompt.filename}' 创建成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Prompt 文件时出错: {e}")


@app.get("/api/prompts/{filename}")
async def get_prompt_content(filename: str, username: str = Depends(verify_credentials)):
    """
    获取指定 prompt 文件的内容。
    """
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    
    # 不需要额外解码，FastAPI 已经自动解码了
    # filename = filename.encode('latin-1').decode('utf-8')
    
    filepath = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": filename, "content": content}


# --- 标准文件API端点 ---
CRITERIA_DIR = "criteria"

@app.get("/api/criteria")
async def list_criteria_files(username: str = Depends(verify_credentials)):
    """
    列出 criteria/ 目录下的所有 .txt 文件。
    """
    if not os.path.isdir(CRITERIA_DIR):
        return []
    return [f for f in os.listdir(CRITERIA_DIR) if f.endswith(".txt")]


@app.get("/api/criteria/{filename}")
async def get_criteria_content(filename: str, username: str = Depends(verify_credentials)):
    """
    获取指定 criteria 文件的内容。
    """
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    
    # 不需要额外解码，FastAPI 已经自动解码了
    # filename = filename.encode('latin-1').decode('utf-8')
    
    # 检查文件是否在requirement目录中
    requirement_path = os.path.join("requirement", filename)
    if os.path.exists(requirement_path):
        async with aiofiles.open(requirement_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        return {"filename": filename, "content": content}
    
    # 否则检查criteria目录
    filepath = os.path.join(CRITERIA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"DEBUG: Criteria file not found at: {filepath} or {requirement_path}")
        raise HTTPException(status_code=404, detail="Criteria 文件未找到。")

    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": filename, "content": content}


@app.put("/api/criteria/{filename}")
async def update_criteria_content(filename: str, prompt_update: PromptUpdate, username: str = Depends(verify_credentials)):
    """
    更新指定 criteria 文件的内容。
    """
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    
    # 不需要额外解码，FastAPI 已经自动解码了
    # filename = filename.encode('latin-1').decode('utf-8')
    
    # 检查文件是否在requirement目录中
    requirement_path = os.path.join("requirement", filename)
    if os.path.exists(requirement_path):
        try:
            async with aiofiles.open(requirement_path, 'w', encoding='utf-8') as f:
                await f.write(prompt_update.content)
            return {"message": f"Requirement 文件 '{filename}' 更新成功。"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入 Requirement 文件时出错: {e}")
    
    # 否则检查criteria目录
    filepath = os.path.join(CRITERIA_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Criteria 文件未找到。")

    try:
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(prompt_update.content)
        return {"message": f"Criteria 文件 '{filename}' 更新成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Criteria 文件时出错: {e}")


@app.put("/api/prompts/{filename}")
async def update_prompt_content(filename: str, prompt_update: PromptUpdate, username: str = Depends(verify_credentials)):
    """
    更新指定 prompt 文件的内容。
    """
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    filepath = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    try:
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(prompt_update.content)
        return {"message": f"Prompt 文件 '{filename}' 更新成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Prompt 文件时出错: {e}")


@app.delete("/api/prompts/{filename}")
async def delete_prompt(filename: str, username: str = Depends(verify_credentials)):
    """
    删除指定的 prompt 文件。
    """
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    
    filepath = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt 文件未找到。")

    try:
        os.remove(filepath)
        return {"message": f"Prompt 文件 '{filename}' 删除成功。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Prompt 文件时出错: {e}")


@app.post("/api/login-state", response_model=dict)
async def update_login_state(data: LoginStateUpdate, username: str = Depends(verify_credentials)):
    """
    接收前端发送的登录状态JSON字符串，并保存到 xianyu_state.json。
    """
    state_file = "xianyu_state.json"
    try:
        # 验证是否是有效的JSON
        json.loads(data.content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="提供的内容不是有效的JSON格式。")

    try:
        async with aiofiles.open(state_file, 'w', encoding='utf-8') as f:
            await f.write(data.content)
        return {"message": f"登录状态文件 '{state_file}' 已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入登录状态文件时出错: {e}")


@app.delete("/api/login-state", response_model=dict)
async def delete_login_state(username: str = Depends(verify_credentials)):
    """
    删除 xianyu_state.json 文件。
    """
    state_file = "xianyu_state.json"
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
            return {"message": "登录状态文件已成功删除。"}
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"删除登录状态文件时出错: {e}")
    return {"message": "登录状态文件不存在，无需删除。"}


# 重新定义清理函数，不使用嵌套函数
async def _cleanup_login_process(process):
    """清理登录进程的后台任务"""
    await process.wait()
    global login_process
    login_process = None
    print(f"自动登录程序 (PID: {process.pid}) 已结束。")

@app.post("/api/manual-login", response_model=dict)
async def start_manual_login(username: str = Depends(verify_credentials)):
    """
    启动自动登录程序 login.py
    """
    global login_process
    
    try:
        # 检查是否已有登录进程在运行
        if login_process is not None and login_process.returncode is None:
            return {"message": "已有登录进程在运行中，请等待其完成或关闭后再尝试。"}
        
        # 使用 asyncio 启动 login.py 进程
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "login.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=child_env
        )
        
        # 保存进程引用
        login_process = process
        
        # 不等待进程结束，让它在后台运行
        print(f"自动登录程序已启动，PID: {process.pid}")
        
        # 创建一个后台任务来清理进程引用
        asyncio.create_task(_cleanup_login_process(process))
        
        return {"message": "自动登录程序已成功启动，请在服务器上查看浏览器窗口并完成登录。"}
    except Exception as e:
        # 确保进程引用被清理
        login_process = None
        raise HTTPException(status_code=500, detail=f"启动自动登录程序时出错: {str(e)}")


@app.get("/api/settings/notifications", response_model=dict)
async def get_notification_settings(username: str = Depends(verify_credentials)):
    """
    获取通知设置。
    """
    return load_notification_settings()


@app.put("/api/settings/notifications", response_model=dict)
async def update_notification_settings(settings: NotificationSettings, username: str = Depends(verify_credentials)):
    """
    更新通知设置。
    """
    try:
        # 将 Pydantic 模型转换为字典，排除值为 None 的字段
        settings_dict = settings.model_dump(exclude_none=True)
        save_notification_settings(settings_dict)
        
        # 配置已更新，需要重新加载所有相关配置
        from src.notifier import config as notifier_config
        notifier_config.reload()
        
        # Reload main config and AI client
        from src.config import reload_config
        reload_config()
        
        return {"message": "通知设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新通知设置时出错: {e}")


# Define a new Pydantic model for the generic settings
class GenericSettings(BaseModel):
    LOGIN_IS_EDGE: Optional[bool] = None
    RUN_HEADLESS: Optional[bool] = None
    AI_DEBUG_MODE: Optional[bool] = None
    ENABLE_THINKING: Optional[bool] = None
    ENABLE_RESPONSE_FORMAT: Optional[bool] = None
    SEND_URL_FORMAT_IMAGE: Optional[bool] = None
    SERVER_PORT: Optional[int] = None
    WEB_USERNAME: Optional[str] = None
    WEB_PASSWORD: Optional[str] = None


def load_generic_settings():
    """从.env文件加载通用设置"""
    from dotenv import dotenv_values
    config = dotenv_values(".env")

    return {
        "LOGIN_IS_EDGE": config.get("LOGIN_IS_EDGE", "false").lower() == "true",
        "RUN_HEADLESS": config.get("RUN_HEADLESS", "true").lower() == "true",
        "AI_DEBUG_MODE": config.get("AI_DEBUG_MODE", "false").lower() == "true",
        "ENABLE_THINKING": config.get("ENABLE_THINKING", "false").lower() == "true",
        "ENABLE_RESPONSE_FORMAT": config.get("ENABLE_RESPONSE_FORMAT", "true").lower() == "true",
        "SEND_URL_FORMAT_IMAGE": config.get("SEND_URL_FORMAT_IMAGE", "true").lower() == "true",
        "SERVER_PORT": int(config.get("SERVER_PORT", 8000)),
        "WEB_USERNAME": config.get("WEB_USERNAME", "admin"),
        "WEB_PASSWORD": config.get("WEB_PASSWORD", "admin123")
    }


def save_generic_settings(settings: dict):
    """将通用设置保存到.env文件"""
    env_file = ".env"
    env_lines = []

    # 读取现有的.env文件
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()

    # 更新或添加通用设置
    setting_keys = [
        "LOGIN_IS_EDGE", "RUN_HEADLESS", "AI_DEBUG_MODE", "ENABLE_THINKING", 
        "ENABLE_RESPONSE_FORMAT", "SEND_URL_FORMAT_IMAGE", "SERVER_PORT", "WEB_USERNAME", "WEB_PASSWORD"
    ]

    # 创建现有设置的字典
    existing_settings = {}
    for line in env_lines:
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.split('=', 1)
            existing_settings[key.strip()] = value.strip()

    # 使用新设置更新
    existing_settings.update(settings)

    # 写回文件
    with open(env_file, 'w', encoding='utf-8') as f:
        for key in setting_keys:
            value = existing_settings.get(key, "")
            if key in ["LOGIN_IS_EDGE", "RUN_HEADLESS", "AI_DEBUG_MODE", "ENABLE_THINKING", "ENABLE_RESPONSE_FORMAT", "SEND_URL_FORMAT_IMAGE"]:
                f.write(f"{key}={str(value).lower()}\n")
            else:
                f.write(f"{key}={value}\n")

        # 写入不是通用设置的其他现有设置
        for key, value in existing_settings.items():
            if key not in setting_keys:
                f.write(f"{key}={value}\n")


@app.get("/api/settings/generic", response_model=dict)
async def get_generic_settings(username: str = Depends(verify_credentials)):
    """
    获取通用设置。
    """
    return load_generic_settings()


@app.put("/api/settings/generic", response_model=dict)
async def update_generic_settings(settings: GenericSettings, username: str = Depends(verify_credentials)):
    """
    更新通用设置。
    """
    try:
        # 将 Pydantic 模型转换为字典，排除值为 None 的字段
        settings_dict = settings.model_dump(exclude_none=True)
        save_generic_settings(settings_dict)
        
        # Reload main config after update
        from src.config import reload_config
        reload_config()
        
        return {"message": "通用设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新通用设置时出错: {e}")


@app.get("/api/settings/ai", response_model=dict)
async def get_ai_settings(username: str = Depends(verify_credentials)):
    """
    获取AI模型设置。
    """
    return load_ai_settings()


@app.put("/api/settings/ai", response_model=dict)
async def update_ai_settings(settings: dict, username: str = Depends(verify_credentials)):
    """
    更新AI模型设置。
    """
    try:
        save_ai_settings(settings)
        # 重新初始化AI客户端以使用新的配置
        from src.config import reload_config
        reload_config()
        return {"message": "AI模型设置已成功更新。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新AI模型设置时出错: {e}")


@app.post("/api/settings/ai/test", response_model=dict)
async def test_ai_settings(settings: dict, username: str = Depends(verify_credentials)):
    """
    测试AI模型设置是否有效。
    """
    try:
        from openai import OpenAI
        import httpx

        # 创建OpenAI客户端
        client_params = {
            "api_key": settings.get("OPENAI_API_KEY", ""),
            "base_url": settings.get("OPENAI_BASE_URL", ""),
            "timeout": httpx.Timeout(30.0),
        }

        # 如果有代理设置
        proxy_url = settings.get("PROXY_URL", "")
        if proxy_url:
            client_params["http_client"] = httpx.Client(proxy=proxy_url)

        mode_name = settings.get("OPENAI_MODEL_NAME", "")
        print(f"LOG: 后端容器AI测试 BASE_URL: {client_params['base_url']}, MODEL_NAME: {mode_name}, PROXY_URL: {proxy_url}")

        client = OpenAI(**client_params)

        from src.config import get_ai_request_params
        
        # 测试连接
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


# Import the notification functions from ai_handler.py
from src.ai_handler import send_all_notifications, send_test_notification, send_test_task_completion_notification, send_test_product_notification

# Define a new Pydantic model for the notification request
class NotificationRequest(BaseModel):
    商品信息: dict
    ai_analysis: Optional[dict] = None  # Allow ai_analysis to be optional

@app.post("/api/notifications/send", response_model=dict)
async def send_notification_api(item_data: NotificationRequest, username: str = Depends(verify_credentials)):
    """
    发送通知到所有已配置的渠道。
    """
    try:
        # 将商品信息和 ai_analysis 合并到一个数据结构中
        # 这与通知系统期望的 JSONL 格式匹配
        product_data = item_data.model_dump()  # 这将同时包含 商品信息 和 ai_analysis（如果存在的话）
        
        # 从产品数据中提取实际的 AI 分析理由
        ai_reason = ""
        
        # 首先检查 ai_analysis 是否直接在 product_data 中（手动通知的情况）
        if 'ai_analysis' in product_data and product_data['ai_analysis']:
            ai_reason = product_data['ai_analysis'].get('reason', '')
        
        # 如果找到了理由，就使用它；否则，如果 商品信息 中有 AI 理由，就使用它
        if not ai_reason and '商品信息' in product_data:
            # 检查 ai_analysis 是否在 商品信息 内部
            if 'ai_analysis' in product_data['商品信息'] and product_data['商品信息']['ai_analysis']:
                ai_reason = product_data['商品信息']['ai_analysis'].get('reason', '')
        
        # 使用实际的 AI 理由发送通知
        if ai_reason:
            # 如果找到了 AI 理由，就使用它
            result = await send_all_notifications(product_data, ai_reason)
        else:
            # 如果没有找到 AI 理由，就回退到手动通知理由
            result = await send_all_notifications(product_data, "用户手动发送通知")
        
        return {"message": "通知已发送到所有已配置的渠道。", "channels": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送通知时出错: {e}")

# 为测试通知请求定义一个新的Pydantic模型
class TestNotificationRequest(BaseModel):
    channel: str  # 指定要测试的渠道

@app.post("/api/notifications/test", response_model=dict)
async def send_test_notification_api(request: TestNotificationRequest, username: str = Depends(verify_credentials)):
    """
    向指定渠道发送测试通知。
    """
    try:
        # 渠道名称映射，用于统一显示
        channel_name_map = {
            "ntfy": "Ntfy",
            "gotify": "Gotify", 
            "bark": "Bark",
            "wx_bot": "企业微信机器人",
            "wx_app": "企业微信应用",
            "telegram": "Telegram",
            "webhook": "Webhook"
        }
        channel_display_name = channel_name_map.get(request.channel, request.channel)
        
        # 使用指定的渠道调用send_test_notification函数
        result = await send_test_notification(request.channel)
        if result:
            return {"message": f"测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        else:
            return {"message": f"测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送测试通知时出错: {e}")


# 为测试任务完成通知请求定义一个新的Pydantic模型
class TestTaskCompletionNotificationRequest(BaseModel):
    channel: str  # 指定要测试的渠道

@app.post("/api/notifications/test-task-completion", response_model=dict)
async def send_test_task_completion_notification_api(request: TestTaskCompletionNotificationRequest, username: str = Depends(verify_credentials)):
    """
    向指定渠道发送任务完成通知的测试。
    """
    try:
        # 渠道名称映射，用于统一显示
        channel_name_map = {
            "ntfy": "Ntfy",
            "gotify": "Gotify", 
            "bark": "Bark",
            "wx_bot": "企业微信机器人",
            "wx_app": "企业微信应用",
            "telegram": "Telegram",
            "webhook": "Webhook"
        }
        channel_display_name = channel_name_map.get(request.channel, request.channel)
        
        # 使用指定的渠道调用send_test_task_completion_notification函数
        result = await send_test_task_completion_notification(request.channel)
        if result:
            return {"message": f"任务完成测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        else:
            return {"message": f"任务完成测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送任务完成测试通知时出错: {e}")


# 为测试商品卡通知请求定义一个新的Pydantic模型
class TestProductNotificationRequest(BaseModel):
    channel: str  # 指定要测试的渠道

@app.post("/api/notifications/test-product", response_model=dict)
async def send_test_product_notification_api(request: TestProductNotificationRequest, username: str = Depends(verify_credentials)):
    """
    向指定渠道发送商品卡测试通知。
    """
    try:
        # 渠道名称映射，用于统一显示
        channel_name_map = {
            "ntfy": "Ntfy",
            "gotify": "Gotify", 
            "bark": "Bark",
            "wx_bot": "企业微信机器人",
            "wx_app": "企业微信应用",
            "telegram": "Telegram",
            "webhook": "Webhook"
        }
        channel_display_name = channel_name_map.get(request.channel, request.channel)
        
        # 使用指定的渠道调用send_test_product_notification函数
        result = await send_test_product_notification(request.channel)
        if result:
            return {"message": f"商品卡测试通知已成功发送到 {channel_display_name} 渠道。", "success": True}
        else:
            return {"message": f"商品卡测试通知发送失败到 {channel_display_name} 渠道。", "success": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送商品卡测试通知时出错: {e}")

@app.post("/api/settings/ai/test/backend", response_model=dict)
async def test_ai_settings_backend(username: str = Depends(verify_credentials)):
    """
    测试AI模型设置是否有效（从后端容器内发起）。
    """
    try:
        from src.config import client, BASE_URL, MODEL_NAME, get_ai_request_params
        
        # 使用与spider_v2.py相同的AI客户端配置
        if not client:
            return {
                "success": False,
                "message": "后端AI客户端未初始化，请检查.env配置文件中的AI设置。"
            }

        print(f"LOG: 后端容器AI测试 BASE_URL: {BASE_URL()}, MODEL_NAME: {MODEL_NAME()}")
        # 测试连接
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


if __name__ == "__main__":
    # 从 .env 文件加载环境变量
    config = dotenv_values(".env")

    # 获取服务器端口，如果未设置则默认为 8000
    server_port = int(config.get("SERVER_PORT", 8000))

    # 设置默认编码
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"启动 Web 管理界面，请在浏览器访问 http://127.0.0.1:{server_port}")
    sys.stdout.flush()  # 立即刷新输出缓冲区

    # 启动 Uvicorn 服务器
    uvicorn.run(app, host="0.0.0.0", port=server_port, log_level="warning")
