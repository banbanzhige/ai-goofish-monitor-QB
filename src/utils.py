import asyncio
import json
import math
import os
import random
import re
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from openai import APIStatusError
from requests.exceptions import HTTPError


def retry_on_failure(retries=3, delay=5):
    """
    一个通用的异步重试装饰器，增加了对HTTP错误的详细日志记录。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except (APIStatusError, HTTPError) as e:
                    print(f"函数 {func.__name__} 第 {i + 1}/{retries} 次尝试失败，发生HTTP错误。")
                    if hasattr(e, 'status_code'):
                        print(f"  - 状态码 (Status Code): {e.status_code}")
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        response_text = e.response.text
                        print(
                            f"  - 返回值 (Response): {response_text[:300]}{'...' if len(response_text) > 300 else ''}")
                except json.JSONDecodeError as e:
                    print(f"函数 {func.__name__} 第 {i + 1}/{retries} 次尝试失败: JSON解析错误 - {e}")
                except Exception as e:
                    print(f"函数 {func.__name__} 第 {i + 1}/{retries} 次尝试失败: {type(e).__name__} - {e}")

                if i < retries - 1:
                    print(f"将在 {delay} 秒后重试...")
                    await asyncio.sleep(delay)

            print(f"函数 {func.__name__} 在 {retries} 次尝试后彻底失败。")
            return None
        return wrapper
    return decorator


async def safe_get(data, *keys, default="暂无"):
    """安全获取嵌套字典值"""
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, IndexError):
            return default
    return data


async def random_sleep(min_seconds: float, max_seconds: float):
    """异步等待一个在指定范围内的随机时间。"""
    delay = random.uniform(min_seconds, max_seconds)
    print(f"   [延迟] 等待 {delay:.2f} 秒... (范围: {min_seconds}-{max_seconds}s)")
    await asyncio.sleep(delay)


def log_time(message: str, prefix: str = "", task_name: str = "") -> None:
    """在日志前加上 YY-MM-DD HH:MM:SS 时间戳和任务名称的简单打印。"""
    try:
        ts = datetime.now().strftime(' %Y-%m-%d %H:%M:%S')
    except Exception:
        ts = "--:--:--"
    task_prefix = f"[{task_name}] " if task_name else ""
    print(f"[{ts}] {prefix}{task_prefix}{message}")


def convert_goofish_link(url: str) -> str:
    """
    将Goofish商品链接转换为只包含商品ID的手机端格式，匹配用户提供的示例格式。
    """
    # 尝试在URL中找到 itemId=... 或 id=... 参数
    item_id = None
    
    # 检查是否有 itemId 参数
    match_itemid = re.search(r'(?:\?|&)itemId=(\d+)', url)
    if match_itemid:
        item_id = match_itemid.group(1)
    
    # 如果没找到itemId参数，再检查id参数
    if not item_id:
        match_id = re.search(r'(?:\?|&)id=(\d+)', url)
        if match_id:
            item_id = match_id.group(1)
    
    if item_id:
        # 返回与用户示例匹配的手机端格式
        return f"https://h5.m.goofish.com/item?id={item_id}"
    
    # 如果没有找到商品ID，返回原始URL
    return url


def get_pc_goofish_link(item_id: str) -> str:
    """
    获取Goofish商品的PC端链接
    """
    return f"https://www.goofish.com/item?id={item_id}"


def get_link_unique_key(link: str) -> str:
    """截取链接中第一个"&"之前的内容作为唯一标识依据。"""
    return link.split('&', 1)[0]


async def save_to_jsonl(data_record: dict, keyword: str):
    """将一个包含商品和卖家信息的完整记录追加保存到 .jsonl 文件。"""
    output_dir = "jsonl"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{keyword.replace(' ', '_')}_full_data.jsonl")
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(data_record, ensure_ascii=False) + "\n")
        return True
    except IOError as e:
        print(f"写入文件 {filename} 出错: {e}")
        return False


def format_registration_days(total_days: int) -> str:
    """
    将总天数格式化为“X年Y个月”的字符串。
    """
    if not isinstance(total_days, int) or total_days <= 0:
        return '未知'

    DAYS_IN_YEAR = 365.25
    DAYS_IN_MONTH = DAYS_IN_YEAR / 12

    years = math.floor(total_days / DAYS_IN_YEAR)
    remaining_days = total_days - (years * DAYS_IN_YEAR)
    months = round(remaining_days / DAYS_IN_MONTH)

    if months == 12:
        years += 1
        months = 0

    if years > 0 and months > 0:
        return f"来闲鱼{years}年{months}个月"
    elif years > 0 and months == 0:
        return f"来闲鱼{years}年整"
    elif years == 0 and months > 0:
        return f"来闲鱼{months}个月"
    else:
        return "来闲鱼不足一个月"
