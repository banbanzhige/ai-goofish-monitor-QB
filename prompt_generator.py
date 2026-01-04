import os
import sys
import argparse
import asyncio

from src.prompt_utils import generate_criteria, update_config_with_new_task


async def main():
    parser = argparse.ArgumentParser(
        description="使用AI根据用户需求和参考范例，生成闲鱼公开内容查看智能处理程序的分析标准文件，并自动更新config.json。",
        epilog="""
使用示例:
  python prompt_generator.py \\
    --description "我想买一台95新以上的索尼A7M4相机，预算在10000到13000元之间..." \\
    --output criteria/sony_a7m4_criteria.txt \\
    --task-name "Sony A7M4" \\
    --keyword "a7m4" \\
    --min-price "10000" \\
    --max-price "13000"
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--description", type=str, required=True, help="你详细的购买需求描述。")
    parser.add_argument("--output", type=str, required=True, help="新生成的分析标准文件的保存路径。")
    parser.add_argument("--reference", type=str, default="prompts/base_prompt.txt", help="作为模仿范例的参考文件路径。")
    # New arguments for config.json
    parser.add_argument("--task-name", type=str, required=True, help="新任务的名称 (例如: 'Sony A7M4')。")
    parser.add_argument("--keyword", type=str, required=True, help="新任务的搜索关键词 (例如: 'a7m4')。")
    parser.add_argument("--min-price", type=str, help="最低价格。")
    parser.add_argument("--max-price", type=str, help="最高价格。")
    parser.add_argument("--max-pages", type=int, default=3, help="最大搜索页数 (默认: 3)。")
    parser.add_argument('--no-personal-only', dest='personal_only', action='store_false', help="如果设置，则不筛选个人卖家。")
    parser.set_defaults(personal_only=True)
    parser.add_argument("--config-file", type=str, default="config.json", help="任务配置文件的路径 (默认: config.json)。")
    args = parser.parse_args()

    # Ensure the output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        generated_criteria = await generate_criteria(args.description, args.reference if args.reference else "prompts/base_prompt.txt")
    except Exception as e:
        sys.exit(f"错误: 生成分析标准时失败: {e}")


    if generated_criteria:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(generated_criteria)
            print(f"\n成功！新的分析标准已保存到: {args.output}")
        except IOError as e:
            sys.exit(f"错误: 写入输出文件失败: {e}")

        # 创建新任务条目
        new_task = {
            "task_name": args.task_name,
            "enabled": True,
            "keyword": args.keyword,
            "max_pages": args.max_pages,
            "personal_only": args.personal_only,
            "ai_prompt_base_file": "prompts/base_prompt.txt",
            "ai_prompt_criteria_file": args.output
        }
        if args.min_price:
            new_task["min_price"] = args.min_price
        if args.max_price:
            new_task["max_price"] = args.max_price

        # 使用重构的函数更新 config.json
        success = await update_config_with_new_task(new_task, args.config_file)
        if success:
            print("现在，你可以直接运行 `python collector.py` 来启动包括新任务在内的所有公开内容查看。")

if __name__ == "__main__":
    asyncio.run(main())
