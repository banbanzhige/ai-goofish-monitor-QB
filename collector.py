import asyncio
import sys
import os
import argparse
import json
from datetime import datetime

from src.config import STATE_FILE
from src.scraper import fetch_xianyu

# 统一日志格式化函数
def log_message(task_name, level, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{task_name}] [{level.upper()}] {message}"

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

    if not os.path.exists(STATE_FILE):
        sys.exit(log_message("系统", "error", f"登录状态文件 '{STATE_FILE}' 不存在。请先运行 login.py 生成。"))

    if not os.path.exists(args.config):
        sys.exit(log_message("系统", "error", f"配置文件 '{args.config}' 不存在。"))

    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            tasks_config = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        sys.exit(log_message("系统", "error", f"读取或解析配置文件 '{args.config}' 失败: {e}"))

    # 读取所有prompt文件内容
    for task in tasks_config:
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
                    print(log_message(task['task_name'], "warning", f"生成的prompt过短 ({len(task['ai_prompt_text'])} 字符)，可能存在问题。"))
                elif "{{CRITERIA_SECTION}}" in task['ai_prompt_text']:
                    print(log_message(task['task_name'], "warning", "prompt中仍包含占位符，替换可能失败。"))
                else:
                    print(log_message(task['task_name'], "info", f"prompt生成成功，长度: {len(task['ai_prompt_text'])} 字符"))

            except FileNotFoundError as e:
                print(log_message(task['task_name'], "warning", f"prompt文件缺失: {e}，该任务的AI分析将被跳过。"))
                task['ai_prompt_text'] = ""
            except Exception as e:
                print(log_message(task['task_name'], "error", f"处理prompt文件时发生异常: {e}，该任务的AI分析将被跳过。"))
                task['ai_prompt_text'] = ""
        elif task.get("enabled", False) and task.get("ai_prompt_file"):
            try:
                with open(task["ai_prompt_file"], 'r', encoding='utf-8') as f:
                    task['ai_prompt_text'] = f.read()
                print(log_message(task['task_name'], "info", f"prompt文件读取成功，长度: {len(task['ai_prompt_text'])} 字符"))
            except FileNotFoundError:
                print(log_message(task['task_name'], "warning", f"prompt文件 '{task['ai_prompt_file']}' 未找到，该任务的AI分析将被跳过。"))
                task['ai_prompt_text'] = ""
            except Exception as e:
                print(log_message(task['task_name'], "error", f"读取prompt文件时发生异常: {e}，该任务的AI分析将被跳过。"))
                task['ai_prompt_text'] = ""

    print(log_message("系统", "info", "--- 开始执行任务 ---"))
    if args.debug_limit > 0:
        print(log_message("系统", "info", f"** 调试模式已激活，每个任务最多处理 {args.debug_limit} 个新商品 **"))
    
    if args.task_name:
        print(log_message("系统", "info", f"** 定时任务模式：只执行任务 '{args.task_name}' **"))

    print(log_message("系统", "info", "--------------------"))

    active_task_configs = []
    if args.task_name:
        # 如果指定了任务名称，只查找该任务
        task_found = next((task for task in tasks_config if task.get('task_name') == args.task_name), None)
        if task_found:
            if task_found.get("enabled", False):
                active_task_configs.append(task_found)
            else:
                print(log_message(args.task_name, "info", "任务已被禁用，跳过执行。"))
        else:
            print(log_message("系统", "error", f"在配置文件中未找到名为 '{args.task_name}' 的任务。"))
            return
    else:
        # 否则，按原计划加载所有启用的任务
        active_task_configs = [task for task in tasks_config if task.get("enabled", False)]

    if not active_task_configs:
        print(log_message("系统", "info", "没有需要执行的任务，程序退出。"))
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
        print(log_message(task_conf['task_name'], "info", "已加入执行队列。"))
        # 发送任务开始通知
        try:
            from src.notifier import notifier
            await notifier.send_task_start_notification(task_conf['task_name'], start_reason)
        except ImportError as e:
            print(log_message(task_conf['task_name'], "error", f"导入通知模块失败: {e}"))
        except Exception as e:
            print(log_message(task_conf['task_name'], "error", f"发送任务开始通知失败: {e}"))
        
        coroutines.append(fetch_xianyu(task_config=task_conf, debug_limit=args.debug_limit))

    # 并发执行所有任务
    results = await asyncio.gather(*coroutines, return_exceptions=True)

    print(log_message("系统", "info", "--- 所有任务执行完毕 ---"))
    for i, result in enumerate(results):
        task_name = active_task_configs[i]['task_name']
        if isinstance(result, Exception):
            print(log_message(task_name, "error", f"任务因异常而终止: {result}"))
            # 发送任务完成通知（异常情况）
            try:
                from src.notifier import notifier
                end_reason = f"自动结束-结束原因：任务执行过程中发生错误 - {str(result)}"
                await notifier.send_task_completion_notification(task_name, end_reason, 0, 0)
            except ImportError as e:
                print(log_message(task_name, "error", f"导入通知模块失败: {e}"))
            except Exception as e:
                print(log_message(task_name, "error", f"发送任务完成通知失败: {e}"))
        else:
            processed_count, recommended_count, end_reason = result
            print(log_message(task_name, "info", f"任务正常结束，本次运行共处理了 {processed_count} 个新商品，其中 {recommended_count} 个被AI推荐。结束原因：{end_reason}"))
            
            # 发送任务完成通知
            try:
                from src.notifier import notifier
                await notifier.send_task_completion_notification(task_name, end_reason, processed_count, recommended_count)
            except ImportError as e:
                print(log_message(task_name, "error", f"导入通知模块失败: {e}"))
            except Exception as e:
                print(log_message(task_name, "error", f"发送任务完成通知失败: {e}"))
            
            # 删除任务统计数据文件
            try:
                from src.scraper import delete_task_stats_file
                delete_task_stats_file(task_name)
            except Exception as e:
                print(log_message(task_name, "error", f"删除任务统计数据文件失败: {e}"))

if __name__ == "__main__":
    asyncio.run(main())
