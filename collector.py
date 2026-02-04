import asyncio
import sys
import os
import argparse
import json

from src.scraper import fetch_xianyu
from src.logging_config import setup_logging, get_logger
from src.config import (
    LOG_LEVEL, LOG_CONSOLE_LEVEL, LOG_DIR, LOG_MAX_BYTES,
    LOG_BACKUP_COUNT, LOG_RETENTION_DAYS, LOG_JSON_FORMAT, LOG_ENABLE_LEGACY
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

# 获取系统logger
logger = get_logger(__name__, service="collector")

async def main():
    parser = argparse.ArgumentParser(
        description="闲鱼商品公开内容查看脚本，支持多任务配置和实时AI分析。",
        epilog="""
使用示例:
  # 运行 config.json 中定义的所有任务
  python collector.py

  # 只运行名为 "Sony A7M4" 的任务 (通常由调度器调用)
  python collector.py --task-name "Sony A7M4"

  # 只运行名为 "Sony A7M4" 的任务 (手动开始)
  python collector.py --task-name "Sony A7M4" --start-reason manual

  # 调试模式: 运行所有任务，但每个任务只处理前3个新发现的商品
  python collector.py --debug-limit 3
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--debug-limit", type=int, default=0, help="调试模式：每个任务仅处理前 N 个新商品（0 表示无限制）")
    parser.add_argument("--config", type=str, default="config.json", help="指定任务配置文件路径（默认为 config.json）")
    parser.add_argument("--task-name", type=str, help="只运行指定名称的单个任务 (用于定时任务调度)")
    parser.add_argument("--start-reason", type=str, default="手动开始", help="任务开始原因（可选值：manual 手动开始，scheduled 定时开始）")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        logger.error(f"配置文件 '{args.config}' 不存在。", extra={"event": "config_not_found"})
        sys.exit(1)

    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            tasks_config = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"读取或解析配置文件 '{args.config}' 失败: {e}", extra={"event": "config_parse_error"})
        sys.exit(1)

    # 读取所有prompt文件内容
    for task in tasks_config:
        task_name = task.get('task_name', 'unknown')
        if task.get("enabled", False) and task.get("ai_prompt_base_file") and task.get("ai_prompt_criteria_file"):
            try:
                with open(task["ai_prompt_base_file"], 'r', encoding='utf-8') as f_base:
                    base_prompt = f_base.read()
                with open(task["ai_prompt_criteria_file"], 'r', encoding='utf-8') as f_criteria:
                    criteria_text = f_criteria.read()
                
                # 动态组合成最终的Prompt
                task['ai_prompt_text'] = base_prompt.replace("{{CRITERIA_SECTION}}", criteria_text)
                
                # 验证生成的prompt是否有效
                if len(task['ai_prompt_text']) < 100:
                    logger.warning(
                        f"生成的prompt过短 ({len(task['ai_prompt_text'])} 字符)，可能存在问题。",
                        extra={"task_name": task_name, "event": "prompt_short"}
                    )
                elif "{{CRITERIA_SECTION}}" in task['ai_prompt_text']:
                    logger.warning(
                        "prompt中仍包含占位符，替换可能失败。",
                        extra={"task_name": task_name, "event": "prompt_placeholder"}
                    )
                else:
                    logger.info(
                        f"prompt生成成功，长度: {len(task['ai_prompt_text'])} 字符",
                        extra={"task_name": task_name, "event": "prompt_loaded"}
                    )

            except FileNotFoundError as e:
                logger.warning(
                    f"prompt文件缺失: {e}，该任务的AI分析将被跳过。",
                    extra={"task_name": task_name, "event": "prompt_file_missing"}
                )
                task['ai_prompt_text'] = ""
            except Exception as e:
                logger.error(
                    f"处理prompt文件时发生异常: {e}，该任务的AI分析将被跳过。",
                    extra={"task_name": task_name, "event": "prompt_error"}
                )
                task['ai_prompt_text'] = ""
        elif task.get("enabled", False) and task.get("ai_prompt_file"):
            try:
                with open(task["ai_prompt_file"], 'r', encoding='utf-8') as f:
                    task['ai_prompt_text'] = f.read()
                logger.info(
                    f"prompt文件读取成功，长度: {len(task['ai_prompt_text'])} 字符",
                    extra={"task_name": task_name, "event": "prompt_loaded"}
                )
            except FileNotFoundError:
                logger.warning(
                    f"prompt文件 '{task['ai_prompt_file']}' 未找到，该任务的AI分析将被跳过。",
                    extra={"task_name": task_name, "event": "prompt_file_missing"}
                )
                task['ai_prompt_text'] = ""
            except Exception as e:
                logger.error(
                    f"读取prompt文件时发生异常: {e}，该任务的AI分析将被跳过。",
                    extra={"task_name": task_name, "event": "prompt_error"}
                )
                task['ai_prompt_text'] = ""

    logger.info("--- 开始执行任务 ---", extra={"event": "tasks_start"})
    if args.debug_limit > 0:
        logger.info(
            f"** 调试模式已激活，每个任务最多处理 {args.debug_limit} 个新商品 **",
            extra={"event": "debug_mode", "debug_limit": args.debug_limit}
        )
    
    if args.task_name:
        logger.info(
            f"** 定时任务模式：只执行任务 '{args.task_name}' **",
            extra={"event": "scheduled_mode", "task_name": args.task_name}
        )

    logger.info("--------------------", extra={"event": "separator"})

    active_task_configs = []
    if args.task_name:
        # 如果指定了任务名称，只查找该任务
        task_found = next((task for task in tasks_config if task.get('task_name') == args.task_name), None)
        if task_found:
            if task_found.get("enabled", False):
                active_task_configs.append(task_found)
            else:
                logger.info(
                    "任务已被禁用，跳过执行。",
                    extra={"task_name": args.task_name, "event": "task_disabled"}
                )
        else:
            logger.error(
                f"在配置文件中未找到名为 '{args.task_name}' 的任务。",
                extra={"task_name": args.task_name, "event": "task_not_found"}
            )
            return
    else:
        # 否则，按原计划加载所有启用的任务
        active_task_configs = [task for task in tasks_config if task.get("enabled", False)]

    if not active_task_configs:
        logger.info("没有需要执行的任务，程序退出。", extra={"event": "no_tasks"})
        return

    # 确定任务开始原因
    if args.start_reason == "scheduled":
        start_reason = "定时开始"
    elif args.start_reason == "manual":
        start_reason = "手动开始"
    elif args.task_name:
        # 默认情况下，如果有--task-name参数但没有指定--start-reason，视为定时开始
        start_reason = "定时开始"
    else:
        start_reason = "手动开始"
    
    # 为每个启用的任务创建一个异步执行协程
    coroutines = []
    for task_conf in active_task_configs:
        task_name = task_conf['task_name']
        logger.info(
            "已加入执行队列。",
            extra={"task_name": task_name, "event": "task_queued"}
        )
        # 发送任务开始通知
        try:
            from src.notifier import notifier
            await notifier.send_task_start_notification(task_name, start_reason)
        except ImportError as e:
            logger.error(f"导入通知模块失败: {e}", extra={"task_name": task_name, "event": "import_error"})
        except Exception as e:
            logger.error(f"发送任务开始通知失败: {e}", extra={"task_name": task_name, "event": "notification_error"})
        
        coroutines.append(fetch_xianyu(
            task_config=task_conf, 
            debug_limit=args.debug_limit,
            bound_account=task_conf.get('bound_account')
        ))

    # 并发执行所有任务
    results = await asyncio.gather(*coroutines, return_exceptions=True)

    logger.info("--- 所有任务执行完毕 ---", extra={"event": "tasks_complete"})
    for i, result in enumerate(results):
        task_name = active_task_configs[i]['task_name']
        if isinstance(result, Exception):
            logger.error(
                f"任务因异常而终止: {result}",
                extra={"task_name": task_name, "event": "task_exception"}
            )
            # 发送任务完成通知（异常情况）
            try:
                from src.notifier import notifier
                end_reason = f"自动结束-结束原因：任务执行过程中发生错误 - {str(result)}"
                await notifier.send_task_completion_notification(task_name, end_reason, 0, 0)
            except ImportError as e:
                logger.error(f"导入通知模块失败: {e}", extra={"task_name": task_name, "event": "import_error"})
            except Exception as e:
                logger.error(f"发送任务完成通知失败: {e}", extra={"task_name": task_name, "event": "notification_error"})
        else:
            processed_count, recommended_count, end_reason = result
            logger.info(
                f"任务正常结束，本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。结束原因：{end_reason}",
                extra={
                    "task_name": task_name,
                    "event": "task_complete",
                    "processed_count": processed_count,
                    "recommended_count": recommended_count,
                    "end_reason": end_reason
                }
            )
            
            # 发送任务完成通知
            try:
                from src.notifier import notifier
                await notifier.send_task_completion_notification(task_name, end_reason, processed_count, recommended_count)
            except ImportError as e:
                logger.error(f"导入通知模块失败: {e}", extra={"task_name": task_name, "event": "import_error"})
            except Exception as e:
                logger.error(f"发送任务完成通知失败: {e}", extra={"task_name": task_name, "event": "notification_error"})
            
            # 删除任务统计数据文件
            try:
                from src.scraper import delete_task_stats_file
                delete_task_stats_file(task_name)
            except Exception as e:
                logger.error(
                    f"删除任务统计数据文件失败: {e}",
                    extra={"task_name": task_name, "event": "stats_cleanup_error"}
                )

if __name__ == "__main__":
    asyncio.run(main())
