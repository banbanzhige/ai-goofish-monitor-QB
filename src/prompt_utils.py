import asyncio
import json
import os
import sys
from pathlib import Path

import aiofiles

from src import config
from src.logging_config import get_logger

# 权重框架指导文件路径（策略资产，不作为硬编码权重依赖）
WEIGHT_GUIDE_PATH = Path("prompts/guide/weight_framework_guide.md")

# 统一日志输出
logger = get_logger(__name__, service="system")


def get_weight_framework_guide() -> str:
    """读取权重框架指导文本，缺失时提供最小兜底版本。"""
    if WEIGHT_GUIDE_PATH.exists():
        try:
            return WEIGHT_GUIDE_PATH.read_text(encoding="utf-8")
        except OSError:
            pass
    # 兜底指导：强调必须输出权重表与应用规则
    return (
        "请为评估维度提供权重分配表（总和100%）以及权重应用规则，"
        "并确保高权重维度会影响推荐等级上限与置信度。"
    )


# 用于指导AI的元提示词
META_PROMPT_TEMPLATE = """
你是一位世界级的AI提示词工程大师。你的任务是根据用户提供的【购买需求】，模仿一个【参考范例】，为闲鱼公开内容查看智能处理程序的AI分析模块（代号 EagleEye）生成一份全新的【分析标准】文本。

你的输出必须严格遵循【参考范例】的结构、语气和核心原则，但内容要完全针对用户的【购买需求】进行定制。最终生成的文本将作为AI分析模块的思考指南。

---
这是【参考范例】（`macbook_criteria.txt`）：
```text
{reference_text}
```
---

这是用户的【购买需求】：
```text
{user_description}
```
---

这是本次需要遵循的【权重框架指导】：
```text
{weight_instruction}
```
---

请现在开始生成全新的【分析标准】文本。请注意：
1.  **只输出新生成的文本内容**，不要包含任何额外的解释、标题或代码块标记。
2.  保留范例中的 `[V6.3 核心升级]`、`[V6.4 逻辑修正]` 等版本标记，这有助于保持格式一致性。
3.  将范例中所有与 "MacBook" 相关的内容，替换为与用户需求商品相关的内容。
4.  思考并生成针对新商品类型的“一票否决硬性原则”和“危险信号清单”。
5.  必须包含“评估维度权重分配表（总和100%）”以及“权重应用规则”两个片段。
"""


async def generate_criteria(user_description: str, reference_file_path: str) -> str:
    """
    使用AI生成新的标准文件内容。
    """
    if not config.client:
        raise RuntimeError("AI客户端未初始化，无法生成分析标准。请检查.env配置。")

    logger.info(
        f"正在读取参考文件: {reference_file_path}",
        extra={"event": "criteria_reference_read", "reference_file": reference_file_path}
    )
    try:
        with open(reference_file_path, 'r', encoding='utf-8') as f:
            reference_text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"参考文件未找到: {reference_file_path}")
    except IOError as e:
        raise IOError(f"读取参考文件失败: {e}")

    logger.info("正在构建发送给AI的指令...", extra={"event": "criteria_prompt_build"})
    weight_instruction = get_weight_framework_guide()
    prompt = META_PROMPT_TEMPLATE.format(
        reference_text=reference_text,
        user_description=user_description,
        weight_instruction=weight_instruction,
    )

    logger.info("正在调用AI生成新的分析标准，请稍候...", extra={"event": "criteria_request"})
    try:
        response = await config.client.chat.completions.create(
            **config.get_ai_request_params(
                model=config.MODEL_NAME(),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5 # Lower temperature for more predictable structure
            )
        )
        generated_text = response.choices[0].message.content
        logger.info("AI已成功生成内容。", extra={"event": "criteria_response"})
        
        # 处理content可能为None的情况
        if generated_text is None:
            raise RuntimeError("AI返回的内容为空，请检查模型配置或重试。")
        
        return generated_text.strip()
    except Exception as e:
        logger.error(f"调用AI接口时出错: {e}", extra={"event": "criteria_request_error"})
        raise e


async def update_config_with_new_task(new_task: dict, config_file: str = "config.json"):
    """
    将一个新任务添加到指定的JSON配置文件中。
    """
    logger.info(
        f"正在更新配置文件: {config_file}",
        extra={"event": "config_update_start", "config_file": config_file}
    )
    try:
        # 读取现有配置
        config_data = []
        if os.path.exists(config_file):
            async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                # 处理空文件的情况
                if content.strip():
                    config_data = json.loads(content)

        # 追加新任务
        config_data.append(new_task)

        # 写回配置文件
        async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config_data, ensure_ascii=False, indent=2))

        logger.info(
            f"新任务 '{new_task.get('task_name')}' 已添加到 {config_file} 并已启用。",
            extra={"event": "config_update_success", "task_name": new_task.get("task_name"), "config_file": config_file}
        )
        return True
    except json.JSONDecodeError:
        logger.error(
            f"配置文件 {config_file} 格式错误，无法解析。",
            extra={"event": "config_update_invalid", "config_file": config_file}
        )
        return False
    except IOError as e:
        logger.error(
            f"读写配置文件失败: {e}",
            extra={"event": "config_update_io_error", "config_file": config_file}
        )
        return False

