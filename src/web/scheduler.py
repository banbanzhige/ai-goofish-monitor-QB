import os
import asyncio
import sys
import aiofiles
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.logging_config import get_logger

# 获取logger
logger = get_logger(__name__, service="scheduler")

CONFIG_FILE = "config.json"


async def run_single_task(task_id: int, task_name: str, fetcher_processes, update_task_running_status):
    """由调度器调用的函数，用于启动单个公开内容查看任务。"""
    logger.info(
        f"定时任务触发: 正在为任务 '{task_name}' 启动公开内容查看脚本...",
        extra={"event": "scheduled_task_trigger", "task_id": task_id, "task_name": task_name}
    )
    log_file_handle = None
    try:
        os.makedirs("logs", exist_ok=True)
        log_file_path = os.path.join("logs", "fetcher.log")
        log_file_handle = open(log_file_path, 'a', encoding='utf-8')

        preexec_fn = os.setsid if sys.platform != "win32" else None
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "collector.py", "--task-name", task_name, "--start-reason", "scheduled",
            stdout=log_file_handle,
            stderr=log_file_handle,
            preexec_fn=preexec_fn,
            env=child_env
        )

        fetcher_processes[task_id] = process
        await update_task_running_status(task_id, True, process.pid)
        logger.info(
            f"定时任务 '{task_name}' (PID: {process.pid}) 已添加到进程管理中",
            extra={"event": "task_started", "task_id": task_id, "task_name": task_name, "pid": process.pid}
        )

        async def monitor_process():
            try:
                await process.wait()
                if process.returncode == 0:
                    logger.info(
                        f"定时任务 '{task_name}' 执行成功。日志已写入 {log_file_path}",
                        extra={"event": "task_success", "task_id": task_id, "task_name": task_name}
                    )
                else:
                    logger.error(
                        f"定时任务 '{task_name}' 执行失败。返回码: {process.returncode}",
                        extra={"event": "task_failed", "task_id": task_id, "task_name": task_name, "return_code": process.returncode}
                    )
            finally:
                await update_task_running_status(task_id, False)
                if task_id in fetcher_processes:
                    del fetcher_processes[task_id]

        asyncio.create_task(monitor_process())

    except Exception as e:
        logger.error(
            f"启动定时任务 '{task_name}' 时发生错误: {e}",
            extra={"event": "task_start_error", "task_id": task_id, "task_name": task_name}
        )
        await update_task_running_status(task_id, False)
    finally:
        if log_file_handle:
            log_file_handle.close()


async def _set_all_tasks_stopped_in_config():
    """读取配置文件，将所有任务的 is_running 状态和 generating_ai_criteria 状态设置为 false。"""
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            if not content.strip():
                return
            tasks = json.loads(content)

        needs_update = any(task.get('is_running') or task.get('generating_ai_criteria') for task in tasks)

        if needs_update:
            for task in tasks:
                task['is_running'] = False
                task['generating_ai_criteria'] = False

            async with aiofiles.open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(tasks, ensure_ascii=False, indent=2))
            logger.info(
                '所有任务状态已在配置文件中重置为"已停止"，生成状态已重置为"未生成"。',
                extra={"event": "tasks_reset"}
            )

    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"重置任务状态时出错: {e}", extra={"event": "tasks_reset_error"})


def _get_job_next_run_time(job):
    """安全获取 APScheduler job 下次执行时间，兼容不同版本差异。"""
    try:
        if hasattr(job, "next_run_time"):
            return job.next_run_time
    except Exception:
        pass

    try:
        trigger = getattr(job, "trigger", None)
        if trigger and hasattr(trigger, "get_next_fire_time"):
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            return trigger.get_next_fire_time(None, now)
    except Exception:
        return None

    return None


async def reload_scheduler_jobs(scheduler, fetcher_processes, update_task_running_status):
    """重新加载所有定时任务。清空现有任务，并从 config.json 重新创建。"""
    logger.info("正在重新加载定时任务调度器...", extra={"event": "scheduler_reload"})
    sys.stdout.flush()
    scheduler.remove_all_jobs()
    try:
        async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            if not content.strip():
                tasks = []
            else:
                tasks = json.loads(content)

        for i, task in enumerate(tasks):
            task_name = task.get("task_name")
            cron_str = task.get("cron")
            is_enabled = task.get("enabled", False)
            ai_prompt_criteria_file = task.get("ai_prompt_criteria_file", "")

            # 判断任务是否已生成标准（ai_prompt_criteria_file 应该是 criteria/ 目录下的文件，而不是 requirement/ 目录下的）
            has_generated_criteria = ai_prompt_criteria_file and not ai_prompt_criteria_file.startswith("requirement/")

            if task_name and cron_str and is_enabled and has_generated_criteria:
                try:
                    trigger = CronTrigger.from_crontab(cron_str)
                    scheduler.add_job(
                        run_single_task,
                        trigger=trigger,
                        args=[i, task_name, fetcher_processes, update_task_running_status],
                        id=f"task_{i}",
                        name=f"Scheduled: {task_name}",
                        replace_existing=True
                    )
                    logger.info(
                        f"  -> 已为任务 '{task_name}' 添加定时规则: '{cron_str}'",
                        extra={"event": "job_added", "task_name": task_name, "cron": cron_str}
                    )
                except ValueError as e:
                    logger.warning(
                        f"任务 '{task_name}' 的 Cron 表达式 '{cron_str}' 无效，已跳过: {e}",
                        extra={"event": "invalid_cron", "task_name": task_name, "cron": cron_str}
                    )
            elif task_name and cron_str and is_enabled and not has_generated_criteria:
                logger.info(
                    f"  -> 任务 '{task_name}' 尚未生成标准，已跳过定时任务调度",
                    extra={"event": "task_skipped", "task_name": task_name, "reason": "no_criteria"}
                )

    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"重新加载定时任务时发生错误: {e}", extra={"event": "scheduler_reload_error"})

    logger.info("定时任务加载完成。", extra={"event": "scheduler_ready"})
    sys.stdout.flush()
    if scheduler.get_jobs():
        logger.info("当前已调度的任务:", extra={"event": "jobs_list"})
        for job in scheduler.get_jobs():
            next_run_time = _get_job_next_run_time(job)
            logger.info(
                f"Jobstore default: {job}",
                extra={
                    "event": "job_detail",
                    "job_id": job.id,
                    "job_name": job.name,
                    "next_run_time": next_run_time.isoformat() if next_run_time else None
                }
            )


def get_scheduled_jobs(scheduler):
    """获取所有调度中的定时任务信息，按执行时间排序。"""
    from datetime import datetime, timezone
    import json
    
    # 读取 config.json 获取真实 cron 表达式
    config_tasks = []
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config_tasks = json.load(f)
    except Exception:
        pass
    
    jobs = []
    for job in scheduler.get_jobs():
        # job.id 格式为 "task_{index}"
        try:
            task_id = int(job.id.replace("task_", ""))
        except ValueError:
            continue
        
        # 从 job.args 获取 task_name (第二个参数)
        task_name = job.args[1] if len(job.args) > 1 else job.name.replace("Scheduled: ", "")
        
        # 从 config.json 获取真实 cron 表达式
        cron_str = ""
        order_value = None
        if task_id < len(config_tasks):
            cron_str = config_tasks[task_id].get("cron", "")
            order_value = config_tasks[task_id].get("order")
        
        # 获取下次执行时间
        next_run = None
        if hasattr(job, 'next_run_time') and job.next_run_time:
            next_run = job.next_run_time
        elif hasattr(job.trigger, 'get_next_fire_time'):
            # 使用 trigger 计算下次执行时间
            now = datetime.now(timezone.utc)
            next_run = job.trigger.get_next_fire_time(None, now)
        
        next_run_str = next_run.isoformat() if next_run else None
        
        jobs.append({
            "job_id": job.id,
            "task_id": task_id,
            "task_name": task_name,
            "cron": cron_str,
            "next_run_time": next_run_str,
            "order": order_value,
            "_next_run_dt": next_run  # 用于排序
        })
    
    # 优先按自定义顺序排序，其次按下次执行时间
    has_custom_order = any(job.get("order") is not None for job in jobs)
    if has_custom_order:
        jobs.sort(key=lambda x: x.get("order") if x.get("order") is not None else float("inf"))
    else:
        jobs.sort(key=lambda x: x["_next_run_dt"] or datetime.max.replace(tzinfo=timezone.utc))
    
    # 添加执行顺序并移除临时字段
    for i, job in enumerate(jobs):
        job["execution_order"] = i + 1
        del job["_next_run_dt"]
    
    return jobs
