import json

from pydantic import BaseModel
from typing import Optional

from src.config import CONFIG_FILE
from src.file_operator import FileOperator


class Task(BaseModel):
    task_name: str
    order: Optional[int] = None
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
    generating_ai_criteria: Optional[bool] = False  # New field for AI criteria generation status
    bound_account: Optional[str] = None
    auto_switch_on_risk: Optional[bool] = False
    free_shipping: Optional[bool] = False
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    inspection_service: Optional[bool] = False
    account_assurance: Optional[bool] = False
    super_shop: Optional[bool] = False
    brand_new: Optional[bool] = False
    strict_selected: Optional[bool] = False
    resale: Optional[bool] = False


class TaskUpdate(BaseModel):
    task_name: Optional[str] = None
    order: Optional[int] = None
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
    generating_ai_criteria: Optional[bool] = None  # New field for AI criteria generation status
    bound_account: Optional[str] = None
    auto_switch_on_risk: Optional[bool] = None
    free_shipping: Optional[bool] = None
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    inspection_service: Optional[bool] = None
    account_assurance: Optional[bool] = None
    super_shop: Optional[bool] = None
    brand_new: Optional[bool] = None
    strict_selected: Optional[bool] = None
    resale: Optional[bool] = None


async def add_task(task: Task) -> bool:
    """
    向配置文件中添加一个新任务。
    """
    config_file_op = FileOperator(CONFIG_FILE)

    config_data_str = await config_file_op.read()
    config_data = json.loads(config_data_str) if config_data_str else []
    
    # 确保任务名称唯一，使用自动递增的副本计数
    original_name = task.task_name
    base_name = original_name
    copy_count = 0
    
    # 如果原始名称已经以"(副本)"或"(副本n)"结尾，提取基础名称和副本计数
    import re
    # 匹配中文格式：原名称 (副本) 或 原名称 (副本n)
    match = re.match(r'^(.+?)(?:\s+\((副本)(\d+)?\))?$', original_name)
    if match:
        base_name = match.group(1)
        if match.group(3):  # 如果已有数字后缀
            copy_count = int(match.group(3))
        elif match.group(2):  # 如果只有"副本"没有数字
            copy_count = 1
    
    # 检查是否有 existing task names
    while True:
        # 格式化任务名称 - 始终使用中文 "(副本n)" 格式
        if copy_count == 0:
            current_name = original_name
        else:
            current_name = f"{base_name} (副本{copy_count})"
        
        # 检查名称是否存在
        exists = any(existing_task['task_name'] == current_name for existing_task in config_data)
        if not exists:
            # 更新任务名称
            task.task_name = current_name
            break
        
        # 递增副本计数并再次尝试
        copy_count += 1
    
    # Convert to dictionary before appending to ensure JSON serializability
    if task.order is None:
        task.order = len(config_data)
    config_data.append(task.model_dump())

    return await config_file_op.write(json.dumps(config_data, ensure_ascii=False, indent=2))


async def update_task(task_id: int, task: Task | dict) -> bool:
    """
    更新配置文件中指定ID的任务。
    """
    config_file_op = FileOperator(CONFIG_FILE)

    config_data_str = await config_file_op.read()

    if not config_data_str:
        return False

    config_data = json.loads(config_data_str)

    if len(config_data) <= task_id:
        return False

    # Check if task is a Task object or dict
    if hasattr(task, 'model_dump'):
        # Task object
        config_data[task_id] = task.model_dump()
    else:
        # Dict
        config_data[task_id] = task

    return await config_file_op.write(json.dumps(config_data, ensure_ascii=False, indent=2))


async def get_task(task_id: int) -> Task | None:
    """
    从配置文件中获取指定ID的任务。
    """
    config_file_op = FileOperator(CONFIG_FILE)
    config_data_str = await config_file_op.read()

    if not config_data_str:
        return None

    config_data = json.loads(config_data_str)
    if len(config_data) <= task_id:
        return None

    task_data = config_data[task_id]
    task_data.setdefault("free_shipping", False)
    task_data.setdefault("new_publish_option", None)
    task_data.setdefault("region", None)
    task_data.setdefault("inspection_service", False)
    task_data.setdefault("account_assurance", False)
    task_data.setdefault("super_shop", False)
    task_data.setdefault("brand_new", False)
    task_data.setdefault("strict_selected", False)
    task_data.setdefault("resale", False)
    task_data.setdefault("bound_account", None)
    task_data.setdefault("auto_switch_on_risk", False)

    # Convert dictionary to Task object before returning
    return Task(**task_data)


async def remove_task(task_id: int) -> bool:
    """
    从配置文件中删除指定ID的任务。
    """
    config_file_op = FileOperator(CONFIG_FILE)
    config_data_str = await config_file_op.read()
    if not config_data_str:
        return True

    config_data = json.loads(config_data_str)

    if len(config_data) <= task_id:
        return True

    config_data.pop(task_id)

    return await config_file_op.write(json.dumps(config_data, ensure_ascii=False, indent=2))
