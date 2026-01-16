import os
import re
import asyncio
import aiofiles
import json
import sys
import signal
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from src.web.models import Task, TaskUpdate, TaskGenerateRequestWithReference
from src.utils import write_log
from src.web.scheduler import reload_scheduler_jobs
from src.prompt_utils import generate_criteria
from src.task import add_task, get_task, update_task
from src.notifier import notifier
from src.scraper import get_task_stats, delete_task_stats_file


router = APIRouter()
CONFIG_FILE = "config.json"


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


async def start_task_process(task_id: int, task_name: str, fetcher_processes):
    """内部函数：启动一个指定的任务进程。"""
    if fetcher_processes.get(task_id) and fetcher_processes[task_id].returncode is None:
        print(f"任务 '{task_name}' (ID: {task_id}) 已在运行中。")
        return

    try:
        os.makedirs("logs", exist_ok=True)
        log_file_path = os.path.join("logs", "fetcher.log")
        log_file_handle = open(log_file_path, 'a', encoding='utf-8')

        preexec_fn = os.setsid if sys.platform != "win32" else None
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "collector.py", "--task-name", task_name, "--start-reason", "manual",
            stdout=log_file_handle,
            stderr=log_file_handle,
            preexec_fn=preexec_fn,
            env=child_env
        )
        fetcher_processes[task_id] = process
        print(f"启动任务 '{task_name}' (PID: {process.pid})，日志输出到 {log_file_path}")

        await update_task_running_status(task_id, True)

        async def monitor_process():
            try:
                await process.wait()
                print(f"任务 '{task_name}' (ID: {task_id}) 进程已结束，返回码: {process.returncode}")
            finally:
                await update_task_running_status(task_id, False)
                if task_id in fetcher_processes:
                    del fetcher_processes[task_id]

        asyncio.create_task(monitor_process())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动任务 '{task_name}' 进程时出错: {e}")


async def stop_task_process(task_id: int, fetcher_processes):
    """内部函数：停止一个指定的任务进程。"""
    process = fetcher_processes.get(task_id)
    if not process or process.returncode is not None:
        print(f"任务ID {task_id} 没有正在运行的进程。")
        await update_task_running_status(task_id, False)
        if task_id in fetcher_processes:
            del fetcher_processes[task_id]
        return

    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())
        task_name = tasks[task_id]['task_name']
    except Exception as e:
        print(f"获取任务ID {task_id} 的任务名称时出错: {e}")
        task_name = f"任务ID {task_id}"

    try:
        if sys.platform != "win32":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()

        await process.wait()
        print(f"任务进程 {process.pid} (ID: {task_id}) 已终止。")

        try:
            processed_count, recommended_count = get_task_stats(task_name)
            await notifier.send_task_completion_notification(task_name, "手动停止-结束原因：用户手动停止任务", processed_count, recommended_count)
            delete_task_stats_file(task_name)
        except ImportError as e:
            print(f"导入通知模块失败: {e}")
        except Exception as e:
            print(f"发送任务停止通知失败: {e}")
    except ProcessLookupError:
        print(f"试图终止的任务进程 (ID: {task_id}) 已不存在。")
    except Exception as e:
        print(f"停止任务进程 (ID: {task_id}) 时出错: {e}")
    finally:
        await update_task_running_status(task_id, False)


@router.get("/api/tasks")
async def get_tasks():
    """读取并返回 config.json 中的所有任务。"""
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            tasks = json.loads(content)
            for i, task in enumerate(tasks):
                task['id'] = i
            return tasks
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"配置文件 {CONFIG_FILE} 未找到。")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"配置文件 {CONFIG_FILE} 格式错误。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取任务配置时发生错误: {e}")


@router.post("/api/tasks/generate")
async def generate_task(req: TaskGenerateRequestWithReference):
    """使用 AI 生成一个新的分析标准文件，并据此创建一个新任务。"""
    print(f"收到 AI 任务生成请求: {req.task_name}")

    safe_task_name = "".join(c for c in req.task_name.replace(' ', '_') if c.isalnum() or c in "_-").rstrip()
    requirement_filename = f"requirement/{safe_task_name}_requirement.txt"

    try:
        os.makedirs("requirement", exist_ok=True)
        generated_criteria = req.description
        async with aiofiles.open(requirement_filename, 'w', encoding='utf-8') as f:
            await f.write(generated_criteria)
        print(f"新的需求文件已保存到: {requirement_filename}")
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"保存需求文件失败: {e}")

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

    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            existing_tasks = json.loads(await f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        existing_tasks = []

    original_name = new_task["task_name"]
    base_name = original_name
    copy_count = 0

    match = re.match(r'^(.+?)(?:\s+\((副本)(\d+)?\))?$', original_name)
    if match:
        base_name = match.group(1)
        if match.group(3):
            copy_count = int(match.group(3))
        elif match.group(2):
            copy_count = 1

    while True:
        if copy_count == 0:
            current_name = original_name
        else:
            current_name = f"{base_name} (副本{copy_count})"

        exists = any(existing_task['task_name'] == current_name for existing_task in existing_tasks)
        if not exists:
            new_task["task_name"] = current_name
            break

        copy_count += 1

    task_obj = Task(**new_task)
    success = await add_task(task_obj)
    if not success:
        if os.path.exists(requirement_filename):
            os.remove(requirement_filename)
        if 'criteria_filename' in locals() and os.path.exists(criteria_filename):
            os.remove(criteria_filename)
        raise HTTPException(status_code=500, detail="更新配置文件 config.json 失败。")

    from src.web.main import scheduler, fetcher_processes
    await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)

    async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        tasks = json.loads(await f.read())

    new_task_with_id = None
    for idx, t in enumerate(tasks):
        if t['task_name'] == task_obj.task_name:
            new_task_with_id = t.copy()
            new_task_with_id['id'] = idx
            break

    return {"message": "AI 任务创建成功。", "task": new_task_with_id}


@router.post("/api/tasks")
async def create_task(task: Task):
    """创建一个新任务并将其添加到 config.json。"""
    original_criteria_file = task.ai_prompt_criteria_file

    if original_criteria_file != "prompts/base_prompt.txt":
        try:
            async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                existing_tasks = json.loads(await f.read())
        except (FileNotFoundError, json.JSONDecodeError):
            existing_tasks = []

        original_name = task.task_name
        base_name = original_name
        copy_count = 0

        match = re.match(r'^(.+?)(?:\s+\((副本)(\d+)?\))?$', original_name)
        if match:
            base_name = match.group(1)
            if match.group(3):
                copy_count = int(match.group(3))
            elif match.group(2):
                copy_count = 1

        while True:
            if copy_count == 0:
                current_name = original_name
            else:
                current_name = f"{base_name} (副本{copy_count})"

            exists = any(existing_task['task_name'] == current_name for existing_task in existing_tasks)
            if not exists:
                unique_task_name = current_name
                break

            copy_count += 1

        safe_task_name = "".join(c for c in unique_task_name.lower().replace(' ', '_') if c.isalnum() or c in "_-").rstrip()

        is_requirement_file = original_criteria_file.startswith("requirement/")

        try:
            if is_requirement_file:
                new_requirement_file = f"requirement/{safe_task_name}_requirement.txt"
                new_criteria_file_candidate = f"criteria/{safe_task_name}_criteria.txt"

                async with aiofiles.open(original_criteria_file, 'r', encoding='utf-8') as src:
                    requirement_content = await src.read()

                os.makedirs("requirement", exist_ok=True)
                async with aiofiles.open(new_requirement_file, 'w', encoding='utf-8') as dst:
                    await dst.write(requirement_content)

                original_criteria_file_candidate = original_criteria_file.replace("requirement/", "criteria/").replace("_requirement.txt", "_criteria.txt")
                if os.path.exists(original_criteria_file_candidate):
                    async with aiofiles.open(original_criteria_file_candidate, 'r', encoding='utf-8') as src:
                        criteria_content = await src.read()

                    os.makedirs("criteria", exist_ok=True)
                    async with aiofiles.open(new_criteria_file_candidate, 'w', encoding='utf-8') as dst:
                        await dst.write(criteria_content)

                    task.ai_prompt_criteria_file = new_criteria_file_candidate
                else:
                    task.ai_prompt_criteria_file = new_requirement_file
            else:
                new_criteria_file = f"criteria/{safe_task_name}_criteria.txt"
                new_requirement_file_candidate = f"requirement/{safe_task_name}_requirement.txt"

                async with aiofiles.open(original_criteria_file, 'r', encoding='utf-8') as src:
                    criteria_content = await src.read()

                os.makedirs("criteria", exist_ok=True)
                async with aiofiles.open(new_criteria_file, 'w', encoding='utf-8') as dst:
                    await dst.write(criteria_content)

                original_requirement_file_candidate = original_criteria_file.replace("criteria/", "requirement/").replace("_criteria.txt", "_requirement.txt")
                if os.path.exists(original_requirement_file_candidate):
                    async with aiofiles.open(original_requirement_file_candidate, 'r', encoding='utf-8') as src:
                        requirement_content = await src.read()

                    os.makedirs("requirement", exist_ok=True)
                    async with aiofiles.open(new_requirement_file_candidate, 'w', encoding='utf-8') as dst:
                        await dst.write(requirement_content)

                task.ai_prompt_criteria_file = new_criteria_file

        except Exception as e:
            print(f"Warning: Failed to copy criteria/requirement file: {e}")

    success = await add_task(task)
    if not success:
        if 'new_criteria_file' in locals() and os.path.exists(new_criteria_file):
            try:
                os.remove(new_criteria_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"写入配置文件时发生错误。")

    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())

        created_task = None
        for idx, t in enumerate(tasks):
            if t['task_name'] == task.task_name:
                created_task = t.copy()
                created_task['id'] = idx
                break

        from src.web.main import scheduler, fetcher_processes
        await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)
        return {"message": "任务创建成功。", "task": created_task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入配置文件时发生错误: {e}")


@router.patch("/api/tasks/{task_id}")
async def update_task_api(task_id: int, task_update: TaskUpdate, background_tasks: BackgroundTasks):
    """更新指定ID任务的属性。"""
    task = await get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到。")

    update_data = task_update.model_dump(exclude_unset=True)

    if not update_data:
        return JSONResponse(content={"message": "数据无变化，未执行更新。"}, status_code=200)

    if 'description' in update_data:
        update_data['generating_ai_criteria'] = True

        async def generate_ai_criteria_background(task_id: int, task: dict, user_description: str, reference_file: str = "prompts/base_prompt.txt"):
            if hasattr(task, '__dict__'):
                safe_task_name = re.sub(r'[^\w\s_-]', '', task.task_name.replace(' ', '_'))
            else:
                safe_task_name = re.sub(r'[^\w\s_-]', '', task['task_name'].replace(' ', '_'))
            criteria_filename = f"criteria/{safe_task_name}_criteria.txt"

            try:
                generated_criteria = await generate_criteria(
                    user_description=user_description,
                    reference_file_path=reference_file
                )

                if generated_criteria:
                    os.makedirs("criteria", exist_ok=True)
                    async with aiofiles.open(criteria_filename, 'w', encoding='utf-8') as f:
                        await f.write(generated_criteria)

                    print(f"新的标准文件已保存到: {criteria_filename}")

                    task['ai_prompt_criteria_file'] = criteria_filename
                    task['generating_ai_criteria'] = False

                    await update_task(task_id, task)
            except Exception as e:
                print(f"调用AI生成标准时出错: {e}")
                task['generating_ai_criteria'] = False
                await update_task(task_id, task)

        background_tasks.add_task(
            generate_ai_criteria_background,
            task_id,
            task.model_dump(),
            update_data['description']
        )

    if 'enabled' in update_data and not update_data['enabled']:
        update_data['is_running'] = False

        from src.web.main import fetcher_processes
        if fetcher_processes.get(task_id):
            print(f"任务 '{task.task_name}' 已被禁用，正在停止其进程...")
            asyncio.create_task(stop_task_process(task_id, fetcher_processes))
        else:
            task.is_running = False

    task_dict = task.model_dump()
    task_dict.update(update_data)
    task = Task(**task_dict)

    success = await update_task(task_id, task)

    if not success:
        raise HTTPException(status_code=500, detail=f"写入配置文件时发生错误")

    from src.web.main import scheduler, fetcher_processes
    await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)

    return {"message": "任务更新请求已提交。" if 'description' in update_data else "任务更新成功。", "task": task}


@router.post("/api/tasks/start/{task_id}")
async def start_single_task(task_id: int):
    """启动单个任务。"""
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")

        task = tasks[task_id]
        if not task.get("enabled", False):
            raise HTTPException(status_code=400, detail="任务已被禁用，无法启动。")

        from src.web.main import fetcher_processes
        await start_task_process(task_id, task['task_name'], fetcher_processes)
        return {"message": f"任务 '{task['task_name']}' 已启动。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/tasks/stop/{task_id}")
async def stop_single_task(task_id: int):
    """停止单个任务。"""
    from src.web.main import fetcher_processes
    await stop_task_process(task_id, fetcher_processes)
    return {"message": f"任务ID {task_id} 已发送停止信号。"}


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """从 config.json 中删除指定ID的任务。"""
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"读取或解析配置文件失败: {e}")

    if not (0 <= task_id < len(tasks)):
        raise HTTPException(status_code=404, detail="任务未找到。")

    from src.web.main import fetcher_processes
    if fetcher_processes.get(task_id):
        await stop_task_process(task_id, fetcher_processes)

    deleted_task = tasks.pop(task_id)

    criteria_file = deleted_task.get("ai_prompt_criteria_file")
    if criteria_file and os.path.exists(criteria_file):
        try:
            os.remove(criteria_file)
            print(f"成功删除关联的分析标准文件: {criteria_file}")
        except OSError as e:
            print(f"警告: 删除文件 {criteria_file} 失败: {e}")

    if criteria_file:
        if criteria_file.startswith("criteria/"):
            requirement_file = criteria_file.replace("criteria/", "requirement/").replace("_criteria.txt", "_requirement.txt")
            if os.path.exists(requirement_file):
                try:
                    os.remove(requirement_file)
                    print(f"成功删除关联的需求文件: {requirement_file}")
                except OSError as e:
                    print(f"警告: 删除文件 {requirement_file} 失败: {e}")
        elif criteria_file.startswith("requirement/"):
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

        from src.web.main import scheduler, fetcher_processes
        await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)

        return {"message": "任务删除成功。", "task_name": deleted_task.get("task_name")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入配置文件时发生错误: {e}")


# ============== 定时任务管理 API ==============

@router.get("/api/scheduled-jobs")
async def get_scheduled_jobs_api():
    """获取所有调度中的定时任务列表。"""
    from src.web.main import scheduler
    from src.web.scheduler import get_scheduled_jobs
    
    jobs = get_scheduled_jobs(scheduler)
    return {"jobs": jobs}


@router.post("/api/scheduled-jobs/{job_id}/skip")
async def skip_scheduled_job(job_id: str):
    """跳过指定任务的本次执行，计算下一轮执行时间。"""
    from src.web.main import scheduler
    from datetime import datetime, timezone, timedelta
    
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"定时任务 {job_id} 未找到。")
    
    try:
        # 获取当前下次执行时间
        current_next_run = None
        if hasattr(job, 'next_run_time') and job.next_run_time:
            current_next_run = job.next_run_time
        elif hasattr(job.trigger, 'get_next_fire_time'):
            now = datetime.now(timezone.utc)
            current_next_run = job.trigger.get_next_fire_time(None, now)
        
        if not current_next_run:
            raise HTTPException(status_code=400, detail="无法获取当前执行时间")
        
        # 计算跳过本次后的下一轮执行时间
        # 通过 trigger.get_next_fire_time(current_time, now) 获取下一轮
        skipped_next_run = job.trigger.get_next_fire_time(
            current_next_run, 
            current_next_run + timedelta(seconds=1)
        )
        
        # 使用 modify_job 更新 next_run_time
        scheduler.modify_job(job_id, next_run_time=skipped_next_run)
        
        next_run_str = skipped_next_run.isoformat() if skipped_next_run else None
        
        return {"message": "已跳过本次执行", "next_run_time": next_run_str}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"跳过任务执行时出错: {e}")


@router.post("/api/scheduled-jobs/{job_id}/run-now")
async def run_scheduled_job_now(job_id: str):
    """立即执行指定的定时任务。"""
    from src.web.main import scheduler, fetcher_processes
    from src.web.scheduler import run_single_task
    
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"定时任务 {job_id} 未找到。")
    
    try:
        # 获取任务参数
        task_id = int(job_id.replace("task_", ""))
        task_name = job.args[1] if len(job.args) > 1 else job.name.replace("Scheduled: ", "")
        
        # 直接调用任务执行函数
        await run_single_task(task_id, task_name, fetcher_processes, update_task_running_status)
        
        return {"message": f"任务 '{task_name}' 已开始执行"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"立即执行任务时出错: {e}")


@router.patch("/api/scheduled-jobs/{task_id}/cron")
async def update_scheduled_job_cron(task_id: int, cron_data: dict):
    """修改指定任务的 cron 表达式，并同步到 config.json 和调度器。"""
    from src.web.main import scheduler, fetcher_processes
    from apscheduler.triggers.cron import CronTrigger
    
    new_cron = cron_data.get("cron", "").strip()
    
    # 验证 cron 表达式格式
    if new_cron:
        try:
            CronTrigger.from_crontab(new_cron)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的 Cron 表达式: {e}")
    
    # 更新 config.json
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())
        
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")
        
        tasks[task_id]['cron'] = new_cron
        
        async with aiofiles.open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(tasks, ensure_ascii=False, indent=2))
        
        # 重新加载调度器
        await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)
        
        return {"message": "Cron 表达式已更新", "cron": new_cron}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新 Cron 表达式时出错: {e}")


@router.post("/api/scheduled-jobs/{task_id}/cancel")
async def cancel_scheduled_task(task_id: int):
    """取消任务（关闭启用但保留 Cron 表达式）。"""
    from src.web.main import scheduler, fetcher_processes
    
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            tasks = json.loads(await f.read())
        
        if not (0 <= task_id < len(tasks)):
            raise HTTPException(status_code=404, detail="任务未找到。")
        
        task_name = tasks[task_id].get("task_name", f"任务 {task_id}")
        
        # 关闭启用，但保留 cron
        tasks[task_id]['enabled'] = False
        
        async with aiofiles.open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(tasks, ensure_ascii=False, indent=2))
        
        # 重新加载调度器（会移除该任务的调度）
        await reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status)
        
        return {"message": f"任务 '{task_name}' 已取消", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务时出错: {e}")


