import asyncio
import base64
import json
import os
import re
import sys
import shutil
from datetime import datetime
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import requests
from dotenv import dotenv_values

# 设置标准输出编码为UTF-8，解决Windows控制台编码问题
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

# 从config.py导入不需要动态读取的配置
from src.config import (
    AI_DEBUG_MODE,
    IMAGE_DOWNLOAD_HEADERS,
    IMAGE_SAVE_DIR,
    TASK_IMAGE_DIR_PREFIX,
    MODEL_NAME,
    ENABLE_RESPONSE_FORMAT,
    SEND_URL_FORMAT_IMAGE,
    client,
)
from typing import Optional, Dict, Any
from src.utils import convert_goofish_link, retry_on_failure

# 动态加载通知配置的函数
def get_dynamic_config():
    """动态加载配置，支持实时更新"""
    config = dotenv_values(".env")
    return {
        "NTFY_TOPIC_URL": config.get("NTFY_TOPIC_URL", ""),
        "GOTIFY_URL": config.get("GOTIFY_URL", ""),
        "GOTIFY_TOKEN": config.get("GOTIFY_TOKEN", ""),
        "BARK_URL": config.get("BARK_URL", ""),
        "PCURL_TO_MOBILE": config.get("PCURL_TO_MOBILE", "true").lower() == "true",
        "WX_BOT_URL": config.get("WX_BOT_URL", ""),
        "WX_CORP_ID": config.get("WX_CORP_ID", ""),
        "WX_AGENT_ID": config.get("WX_AGENT_ID", ""),
        "WX_SECRET": config.get("WX_SECRET", ""),
        "WX_TO_USER": config.get("WX_TO_USER", "@all"),
        "TELEGRAM_BOT_TOKEN": config.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": config.get("TELEGRAM_CHAT_ID", ""),
        "WEBHOOK_URL": config.get("WEBHOOK_URL", ""),
        "WEBHOOK_METHOD": config.get("WEBHOOK_METHOD", "POST").upper(),
        "WEBHOOK_HEADERS": config.get("WEBHOOK_HEADERS", ""),
        "WEBHOOK_CONTENT_TYPE": config.get("WEBHOOK_CONTENT_TYPE", "JSON").upper(),
        "WEBHOOK_QUERY_PARAMETERS": config.get("WEBHOOK_QUERY_PARAMETERS", ""),
        "WEBHOOK_BODY": config.get("WEBHOOK_BODY", ""),
    }




async def send_test_notification(channel: str):
    """
    向指定渠道发送测试通知。
    
    Args:
        channel (str): 要发送通知的渠道 (ntfy, gotify, bark, wx_bot, wx_app, telegram, webhook)
        
    Returns:
        bool: 如果通知发送成功返回True，否则返回False
    """
    from src.notifier import notifier
    return await notifier.send_test_notification(channel)




def safe_print(text):
    """安全的打印函数，处理编码错误"""
    try:
        print(text)
    except UnicodeEncodeError:
        # 如果遇到编码错误，尝试用ASCII编码并忽略无法编码的字符
        try:
            print(text.encode('ascii', errors='ignore').decode('ascii'))
        except:
            # 如果还是失败，打印一个简化的消息
            print("[输出包含无法显示的字符]")


@retry_on_failure(retries=2, delay=3)
async def _download_single_image(url, save_path):
    """一个带重试的内部函数，用于异步下载单个图片。"""
    loop = asyncio.get_running_loop()
    # 使用 run_in_executor 运行同步的 requests 代码，避免阻塞事件循环
    response = await loop.run_in_executor(
        None,
        lambda: requests.get(url, headers=IMAGE_DOWNLOAD_HEADERS, timeout=20, stream=True)
    )
    response.raise_for_status()
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return save_path


async def download_all_images(product_id, image_urls, task_name="default"):
    """异步下载一个商品的所有图片。如果图片已存在则跳过。支持任务隔离。"""
    if not image_urls:
        return []

    # 为每个任务创建独立的图片目录
    task_image_dir = os.path.join(IMAGE_SAVE_DIR, f"{TASK_IMAGE_DIR_PREFIX}{task_name}")
    os.makedirs(task_image_dir, exist_ok=True)

    urls = [url.strip() for url in image_urls if url.strip().startswith('http')]
    if not urls:
        return []

    saved_paths = []
    total_images = len(urls)
    for i, url in enumerate(urls):
        try:
            clean_url = url.split('.heic')[0] if '.heic' in url else url
            file_name_base = os.path.basename(clean_url).split('?')[0]
            file_name = f"product_{product_id}_{i + 1}_{file_name_base}"
            file_name = re.sub(r'[\\/*?:"<>|]', "", file_name)
            if not os.path.splitext(file_name)[1]:
                file_name += ".jpg"

            save_path = os.path.join(task_image_dir, file_name)

            if os.path.exists(save_path):
                safe_print(f"   [图片] 图片 {i + 1}/{total_images} 已存在，跳过下载: {os.path.basename(save_path)}")
                saved_paths.append(save_path)
                continue

            safe_print(f"   [图片] 正在下载图片 {i + 1}/{total_images}: {url}")
            if await _download_single_image(url, save_path):
                safe_print(f"   [图片] 图片 {i + 1}/{total_images} 已成功下载到: {os.path.basename(save_path)}")
                saved_paths.append(save_path)
        except Exception as e:
            safe_print(f"   [图片] 处理图片 {url} 时发生错误，已跳过此图: {e}")

    return saved_paths


def cleanup_task_images(task_name):
    """清理指定任务的图片目录"""
    task_image_dir = os.path.join(IMAGE_SAVE_DIR, f"{TASK_IMAGE_DIR_PREFIX}{task_name}")
    if os.path.exists(task_image_dir):
        try:
            shutil.rmtree(task_image_dir)
            safe_print(f"   [清理] 已删除任务 '{task_name}' 的临时图片目录: {task_image_dir}")
        except Exception as e:
            safe_print(f"   [清理] 删除任务 '{task_name}' 的临时图片目录时出错: {e}")
    else:
        safe_print(f"   [清理] 任务 '{task_name}' 的临时图片目录不存在: {task_image_dir}")


def encode_image_to_base64(image_path):
    """将本地图片文件编码为 Base64 字符串。"""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        safe_print(f"编码图片时出错: {e}")
        return None


def validate_ai_response_format(parsed_response):
    """验证AI响应的格式是否符合预期结构"""
    required_fields = [
        "prompt_version",
        "is_recommended",
        "reason",
        "risk_tags",
        "criteria_analysis"
    ]

    # 检查顶层字段
    for field in required_fields:
        if field not in parsed_response:
            safe_print(f"   [AI分析] 警告：响应缺少必需字段 '{field}'")
            return False

    # 检查criteria_analysis是否为字典且不为空
    criteria_analysis = parsed_response.get("criteria_analysis", {})
    if not isinstance(criteria_analysis, dict) or not criteria_analysis:
        safe_print("   [AI分析] 警告：criteria_analysis必须是非空字典")
        return False

    # 检查seller_type字段（所有商品都需要）
    if "seller_type" not in criteria_analysis:
        safe_print("   [AI分析] 警告：criteria_analysis缺少必需字段 'seller_type'")
        return False

    # 检查数据类型
    if not isinstance(parsed_response.get("is_recommended"), bool):
        safe_print("   [AI分析] 警告：is_recommended字段不是布尔类型")
        return False

    if not isinstance(parsed_response.get("risk_tags"), list):
        safe_print("   [AI分析] 警告：risk_tags字段不是列表类型")
        return False

    return True


from src.notifier import notifier

async def send_all_notifications(product_data, reason):
    """
    向所有配置的渠道发送通知。
    
    Returns:
        dict: 向每个渠道发送通知的结果
    """
    return await notifier.send_product_notification(product_data, reason)




@retry_on_failure(retries=3, delay=5)
async def get_ai_analysis(product_data, image_paths=None, prompt_text=""):
    """将完整的商品JSON数据和所有图片发送给 AI 进行分析（异步）。"""
    if not client:
        safe_print("   [AI分析] 错误：AI客户端未初始化，跳过分析。")
        return None

    item_info = product_data.get('商品信息', {})
    product_id = item_info.get('商品ID', 'N/A')

    # 计算实际要使用的图片数量
    if SEND_URL_FORMAT_IMAGE():
        product_info = product_data.get('商品信息', {})
        image_urls = product_info.get('商品图片列表', [])
        actual_image_count = len([url for url in image_urls if url and url.startswith('http')])
    else:
        actual_image_count = len(image_paths or [])
    
    safe_print(f"\n   [AI分析] 开始分析商品 #{product_id} (含 {actual_image_count} 张图片)...")
    safe_print(f"   [AI分析] 标题: {item_info.get('商品标题', '无')}")

    if not prompt_text:
        safe_print("   [AI分析] 错误：未提供AI分析所需的prompt文本。")
        return None

    product_details_json = json.dumps(product_data, ensure_ascii=False, indent=2)
    system_prompt = prompt_text

    if AI_DEBUG_MODE():
        safe_print("\n--- [AI DEBUG] ---")
        safe_print("--- PRODUCT DATA (JSON) ---")
        safe_print(product_details_json)
        safe_print("--- PROMPT TEXT (完整内容) ---")
        safe_print(prompt_text)
        safe_print("-------------------\n")

    combined_text_prompt = f"""请基于你的专业知识和我的要求，分析以下完整的商品JSON数据：

```json
    {product_details_json}
```

{system_prompt}
"""
    user_content_list = []

    # 先添加图片内容
    if image_paths:
        # 如果设置为发送URL格式图片，直接使用图片URL，跳过图片下载步骤
        if SEND_URL_FORMAT_IMAGE():
            # 从商品信息中获取原始图片URLs
            product_info = product_data.get('商品信息', {})
            image_urls = product_info.get('商品图片列表', [])
            # 添加有效的图片URL到消息中
            for url in image_urls:
                if url and url.startswith('http'):
                    user_content_list.append(
                        {"type": "image_url", "image_url": {"url": url}})
        else:
            # 否则使用base64编码方式
            for path in image_paths:
                base64_image = encode_image_to_base64(path)
                if base64_image:
                    user_content_list.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

    # 再添加文本内容
    user_content_list.append({"type": "text", "text": combined_text_prompt})

    messages = [{"role": "user", "content": user_content_list}]

    # 保存最终传输内容到日志文件
    try:
        # 创建logs文件夹
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)

        # 生成日志文件名（当前时间）
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{current_time}.log"
        log_filepath = os.path.join(logs_dir, log_filename)

        # 准备日志内容 - 直接保存原始传输内容
        log_content = json.dumps(messages, ensure_ascii=False)

        # 写入日志文件
        with open(log_filepath, 'w', encoding='utf-8') as f:
            f.write(log_content)

        safe_print(f"   [日志] AI分析请求已保存到: {log_filepath}")

    except Exception as e:
        safe_print(f"   [日志] 保存AI分析日志时出错: {e}")

    # 增强的AI调用，包含更严格的格式控制和重试机制
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 根据重试次数调整参数
            current_temperature = 0.1 if attempt == 0 else 0.05  # 重试时使用更低的温度

            from src.config import get_ai_request_params
            
            # 构建请求参数，根据ENABLE_RESPONSE_FORMAT决定是否使用response_format
            request_params = {
                "model": MODEL_NAME(),
                "messages": messages,
                "temperature": current_temperature,
                "max_tokens": 4000
            }
            
            # 只有启用response_format时才添加该参数
            if ENABLE_RESPONSE_FORMAT():
                request_params["response_format"] = {"type": "json_object"}
            
            response = await client.chat.completions.create(
                **get_ai_request_params(**request_params)
            )

            # 兼容不同API响应格式，检查response是否为字符串
            if hasattr(response, 'choices'):
                ai_response_content = response.choices[0].message.content
            else:
                # 如果response是字符串，则直接使用
                ai_response_content = response

            if AI_DEBUG_MODE():
                safe_print(f"\n--- [AI DEBUG] 第{attempt + 1}次尝试 ---")
                safe_print("--- RAW AI RESPONSE ---")
                safe_print(ai_response_content)
                safe_print("---------------------\n")

            # 尝试直接解析JSON
            try:
                parsed_response = json.loads(ai_response_content)

                # 验证响应格式
                if validate_ai_response_format(parsed_response):
                    safe_print(f"   [AI分析] 第{attempt + 1}次尝试成功，响应格式验证通过")
                    return parsed_response
                else:
                    safe_print(f"   [AI分析] 第{attempt + 1}次尝试格式验证失败")
                    if attempt < max_retries - 1:
                        safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                        continue
                    else:
                        safe_print("   [AI分析] 所有重试完成，使用最后一次结果")
                        return parsed_response

            except json.JSONDecodeError:
                safe_print(f"   [AI分析] 第{attempt + 1}次尝试JSON解析失败，尝试清理响应内容...")

                # 清理可能的Markdown代码块标记
                cleaned_content = ai_response_content.strip()
                if cleaned_content.startswith('```json'):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.startswith('```'):
                    cleaned_content = cleaned_content[3:]
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()

                # 寻找JSON对象边界
                json_start_index = cleaned_content.find('{')
                json_end_index = cleaned_content.rfind('}')

                if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
                    json_str = cleaned_content[json_start_index:json_end_index + 1]
                    try:
                        parsed_response = json.loads(json_str)
                        if validate_ai_response_format(parsed_response):
                            safe_print(f"   [AI分析] 第{attempt + 1}次尝试清理后成功")
                            return parsed_response
                        else:
                            if attempt < max_retries - 1:
                                safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                                continue
                            else:
                                safe_print("   [AI分析] 所有重试完成，使用清理后的结果")
                                return parsed_response
                    except json.JSONDecodeError as e:
                        safe_print(f"   [AI分析] 第{attempt + 1}次尝试清理后JSON解析仍然失败: {e}")
                        if attempt < max_retries - 1:
                            safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                            continue
                        else:
                            raise e
                else:
                    safe_print(f"   [AI分析] 第{attempt + 1}次尝试无法在响应中找到有效的JSON对象")
                    if attempt < max_retries - 1:
                        safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                        continue
                    else:
                        raise json.JSONDecodeError("No valid JSON object found", ai_response_content, 0)

        except Exception as e:
            safe_print(f"   [AI分析] 第{attempt + 1}次尝试AI调用失败: {e}")
            if attempt < max_retries - 1:
                safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                continue
            else:
                raise e
