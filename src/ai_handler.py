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

# 企业微信通知相关函数
def get_wecom_access_token() -> Optional[str]:
    """
    获取企业微信API访问令牌
    
    Returns:
        Optional[str]: 成功时返回访问令牌，失败返回None
    """
    config = get_dynamic_config()
    CORP_ID = config["WX_CORP_ID"]
    CORP_SECRET = config["WX_SECRET"]
    
    if not all([CORP_ID, CORP_SECRET]):
        print("错误：未在 .env 文件中完整设置 WX_CORP_ID 和 WX_SECRET")
        return None
        
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={CORP_SECRET}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        result = response.json()
        
        if result.get("errcode") != 0:
            print(f"获取企业微信访问令牌失败: {result.get('errmsg', '未知错误')}")
            return None
            
        return result["access_token"]
        
    except requests.exceptions.RequestException as e:
        print(f"请求企业微信API时发生错误: {e}")
        return None


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

def send_wechat_news_notification(product: Dict[str, Any]) -> bool:
    """
    从推荐商品数据发送带图片和跳转链接的图文消息到企业微信应用
    
    Args:
        product (Dict[str, Any]): 推荐商品的完整数据对象
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    config = get_dynamic_config()
    CORP_ID = config["WX_CORP_ID"]
    CORP_SECRET = config["WX_SECRET"]
    AGENT_ID = config["WX_AGENT_ID"]
    TO_USER = config["WX_TO_USER"]
    
    access_token = get_wecom_access_token()
    
    if not access_token:
        return False
        
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
    
    # 转换为手机链接
    from src.utils import convert_goofish_link
    
    # 从商品数据中提取关键信息
    # 结构有所不同：从API调用时，product_data有"商品信息"键
    # 从其他地方调用时，它可能是直接的商品数据
    actual_product = product.get('商品信息', product)
    
    title = f"{actual_product.get('商品标题', '未知商品')}"
    
    # 提取AI推荐理由 - 检查JSONL结构中的两个位置
    ai_reason = ""
    ai_analysis = {}
    
    # 首先，检查actual_product是否有ai_analysis（直接商品数据格式）
    if 'ai_analysis' in actual_product:
        ai_analysis = actual_product['ai_analysis']
    # 然后，检查product是否有ai_analysis（JSONL结构中，ai_analysis是"商品信息"的兄弟项）
    elif 'ai_analysis' in product:
        ai_analysis = product['ai_analysis']
    
    # 从ai_analysis中提取理由
    if ai_analysis:
        ai_reason = ai_analysis.get('reason', '')
    
    # 如果仍然没有找到理由，使用默认值
    if not ai_reason:
        ai_reason = "AI推荐商品，查看详情了解更多"
    
    print(f"DEBUG: 找到AI推荐理由: {ai_reason[:100]}...")
    
    # 检查是否有更详细的分析可用
    ai_analysis = product.get('ai_analysis', {})
    
    # 如果有风险标签，包含它们
    risk_tags = ai_analysis.get('risk_tags', [])
    risk_tags_str = ""
    if risk_tags:
        risk_tags_str = f"\n风险标签: {', '.join(risk_tags)}"
    
    # 获得标准分析（如果有的话）
    criteria_analysis = ai_analysis.get('criteria_analysis', {})
    
    # 以更好的格式包含AI推荐理由
    if ai_reason:
        content = f"""
价格：{actual_product.get('当前售价', '未知')}
发布时间：{actual_product.get('发布时间', '未知')}

推荐理由：
{ai_reason}
"""
    else:
        content = f"""
价格：{actual_product.get('当前售价', '未知')}
发布时间：{actual_product.get('发布时间', '未知')}

AI推荐商品，查看详情了解更多...
"""

    # 使用actual_product转换为手机链接
    pc_link = actual_product.get('商品链接', '')
    link_url = convert_goofish_link(pc_link)
    
    print(f"DEBUG: 原始链接: {pc_link}")
    print(f"DEBUG: 转换后的手机链接: {link_url}")
    
    # 优先使用商品图片列表第二张图片，次选第一张，不使用商品主图
    image_url = ''
    if actual_product.get('商品图片列表'):
        image_list = actual_product['商品图片列表']
        # 如果有第二张图片，优先使用
        image_url = image_list[1] if len(image_list) > 1 else image_list[0]
    
    # 构建图文消息内容
    message_data = {
        "touser": TO_USER,
        "msgtype": "news",
        "agentid": AGENT_ID,
        "news": {
            "articles": [{
                "title": title,
                "description": content,
                "url": link_url,
                "picurl": image_url
            }]
        },
        "duplicate_check_interval": 60
    }
    
    try:
        response = requests.post(url, data=json.dumps(message_data, ensure_ascii=False).encode('utf-8'))
        response.raise_for_status()
        result = response.json()
        
        if result.get("errcode") != 0:
            print(f"发送微信图文通知失败: {result.get('errmsg', '未知错误')}")
            return False
            
        print(f"微信图文通知已发送: {title}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"发送微信图文通知时发生错误: {e}")
        return False


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
async def send_ntfy_notification(product_data, reason):
    """当发现推荐商品时，异步发送一个高优先级的 ntfy.sh 通知。"""
    # 动态加载配置
    config = get_dynamic_config()
    
    # 更新条件检查
    if not config["NTFY_TOPIC_URL"] and not config["WX_BOT_URL"] and not (config["WX_CORP_ID"] and config["WX_AGENT_ID"] and config["WX_SECRET"]) and not (config["GOTIFY_URL"] and config["GOTIFY_TOKEN"]) and not config["BARK_URL"] and not (config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]) and not config["WEBHOOK_URL"]:
        safe_print("警告：未在 .env 文件中配置任何通知服务 (NTFY_TOPIC_URL, WX_BOT_URL, GOTIFY_URL/TOKEN, BARK_URL, TELEGRAM_BOT_TOKEN/CHAT_ID, WEBHOOK_URL)，跳过通知。")
        return

    title = product_data.get('商品标题', 'N/A')
    price = product_data.get('当前售价', 'N/A')
    link = product_data.get('商品链接', '#')
    if config["PCURL_TO_MOBILE"]:
        mobile_link = convert_goofish_link(link)
        message = f"价格: {price}\n原因: {reason}\n手机端链接: {mobile_link}\n电脑端链接: {link}"
    else:
        message = f"价格: {price}\n原因: {reason}\n链接: {link}"

    notification_title = f"🚨 新推荐! {title[:30]}..."

    # --- 发送 ntfy 通知 ---
    if config["NTFY_TOPIC_URL"]:
        try:
            safe_print(f"   -> 正在发送 ntfy 通知到: {config['NTFY_TOPIC_URL']}")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: requests.post(
                    config["NTFY_TOPIC_URL"],
                    data=message.encode('utf-8'),
                    headers={
                        "Title": notification_title.encode('utf-8'),
                        "Priority": "urgent",
                        "Tags": "bell,vibration"
                    },
                    timeout=10
                )
            )
            safe_print("   -> ntfy 通知发送成功。")
        except Exception as e:
            safe_print(f"   -> 发送 ntfy 通知失败: {e}")

    # --- 发送 Gotify 通知 ---
    if config["GOTIFY_URL"] and config["GOTIFY_TOKEN"]:
        try:
            safe_print(f"   -> 正在发送 Gotify 通知到: {config['GOTIFY_URL']}")
            # Gotify uses multipart/form-data
            payload = {
                'title': (None, notification_title),
                'message': (None, message),
                'priority': (None, '5')
            }

            gotify_url_with_token = f"{config['GOTIFY_URL']}/message?token={config['GOTIFY_TOKEN']}"

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    gotify_url_with_token,
                    files=payload,
                    timeout=10
                )
            )
            response.raise_for_status()
            safe_print("   -> Gotify 通知发送成功。")
        except requests.exceptions.RequestException as e:
            safe_print(f"   -> 发送 Gotify 通知失败: {e}")
        except Exception as e:
            safe_print(f"   -> 发送 Gotify 通知时发生未知错误: {e}")

    # --- 发送 Bark 通知 ---
    if config["BARK_URL"]:
        try:
            safe_print(f"   -> 正在发送 Bark 通知...")

            bark_payload = {
                "title": notification_title,
                "body": message,
                "level": "timeSensitive",
                "group": "闲鱼监控"
            }

            link_to_use = convert_goofish_link(link) if config["PCURL_TO_MOBILE"] else link
            bark_payload["url"] = link_to_use

            # 如果有主图就用主图
            main_image = product_data.get('商品主图链接')
            if not main_image:
                # 没主图就用图片列表
                image_list = product_data.get('商品图片列表', [])
                if image_list:
                    main_image = image_list[0]

            if main_image:
                bark_payload['icon'] = main_image

            headers = { "Content-Type": "application/json; charset=utf-8" }
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    config["BARK_URL"],
                    json=bark_payload,
                    headers=headers,
                    timeout=10
                )
            )
            response.raise_for_status()
            safe_print("   -> Bark 通知发送成功。")
        except requests.exceptions.RequestException as e:
            safe_print(f"   -> 发送 Bark 通知失败: {e}")
        except Exception as e:
            safe_print(f"   -> 发送 Bark 通知时发生未知错误: {e}")

    # --- 发送企业微信机器人通知 ---
    if config["WX_BOT_URL"]:
        # 使用text类型消息而不是markdown类型，确保手机端兼容
        full_message = f"{notification_title}\n\n{message}"
        
        payload = {
            "msgtype": "text",
            "text": {
                "content": full_message
            }
        }

        try:
            safe_print(f"   -> 正在发送企业微信机器人通知到: {config['WX_BOT_URL']}")
            headers = { "Content-Type": "application/json" }
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    config['WX_BOT_URL'],
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            )
            response.raise_for_status()
            result = response.json()
            safe_print(f"   -> 企业微信机器人通知发送成功。响应: {result}")
        except requests.exceptions.RequestException as e:
            safe_print(f"   -> 发送企业微信机器人通知失败: {e}")
        except Exception as e:
            safe_print(f"   -> 发送企业微信机器人通知时发生未知错误: {e}")
    
    # --- 发送企业微信应用通知 ---
    if config["WX_CORP_ID"] and config["WX_AGENT_ID"] and config["WX_SECRET"]:
        # 使用旧的函数发送图文消息
        try:

            
            # Pass the full product data since send_wechat_news_notification expects it
            safe_print(f"   -> 正在发送企业微信应用通知...")
            loop = asyncio.get_running_loop()
            success = await loop.run_in_executor(
                None,
                lambda: send_wechat_news_notification(product_data)
            )
            
            if success:
                safe_print(f"   -> 企业微信应用通知发送成功")
        except Exception as e:
            safe_print(f"   -> 发送企业微信应用通知失败: {e}")
            import traceback
            traceback.print_exc()

    # --- 发送 Telegram 机器人通知 ---
    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        try:
            safe_print(f"   -> 正在发送 Telegram 通知...")
            
            # 构建 Telegram API URL
            telegram_api_url = f"https://api.telegram.org/bot{config['TELEGRAM_BOT_TOKEN']}/sendMessage"
            
            # 格式化消息内容
            telegram_message = f"🚨 <b>新推荐!</b>\n\n"
            telegram_message += f"<b>{title[:50]}...</b>\n\n"
            telegram_message += f"💰 价格: {price}\n"
            telegram_message += f"📝 原因: {reason}\n"
            
            # 添加链接
            if config["PCURL_TO_MOBILE"]:
                mobile_link = convert_goofish_link(link)
                telegram_message += f"📱 <a href='{mobile_link}'>手机端链接</a>\n"
            telegram_message += f"💻 <a href='{link}'>电脑端链接</a>"
            
            # 构建请求负载
            telegram_payload = {
                "chat_id": config["TELEGRAM_CHAT_ID"],
                "text": telegram_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            
            headers = {"Content-Type": "application/json"}
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    telegram_api_url,
                    json=telegram_payload,
                    headers=headers,
                    timeout=10
                )
            )
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                safe_print("   -> Telegram 通知发送成功。")
            else:
                safe_print(f"   -> Telegram 通知发送失败: {result.get('description', '未知错误')}")
        except requests.exceptions.RequestException as e:
            safe_print(f"   -> 发送 Telegram 通知失败: {e}")
        except Exception as e:
            safe_print(f"   -> 发送 Telegram 通知时发生未知错误: {e}")

    # --- 发送通用 Webhook 通知 ---
    if config["WEBHOOK_URL"]:
        try:
            safe_print(f"   -> 正在发送通用 Webhook 通知到: {config['WEBHOOK_URL']}")

            # 替换占位符
            def replace_placeholders(template_str):
                if not template_str:
                    return ""
                # 对内容进行JSON转义，避免换行符和特殊字符破坏JSON格式
                safe_title = json.dumps(notification_title, ensure_ascii=False)[1:-1]  # 去掉外层引号
                safe_content = json.dumps(message, ensure_ascii=False)[1:-1]  # 去掉外层引号
                # 同时支持旧的${title}${content}和新的{{title}}{{content}}格式
                return template_str.replace("${title}", safe_title).replace("${content}", safe_content).replace("{{title}}", safe_title).replace("{{content}}", safe_content)

            # 准备请求头
            headers = {}
            if config["WEBHOOK_HEADERS"]:
                try:
                    headers = json.loads(config["WEBHOOK_HEADERS"])
                except json.JSONDecodeError:
                    safe_print(f"   -> [警告] Webhook 请求头格式错误，请检查 .env 中的 WEBHOOK_HEADERS。")

            loop = asyncio.get_running_loop()

            if config["WEBHOOK_METHOD"] == "GET":
                # 准备查询参数
                final_url = config["WEBHOOK_URL"]
                if config["WEBHOOK_QUERY_PARAMETERS"]:
                    try:
                        params_str = replace_placeholders(config["WEBHOOK_QUERY_PARAMETERS"])
                        params = json.loads(params_str)

                        # 解析原始URL并追加新参数
                        url_parts = list(urlparse(final_url))
                        query = dict(parse_qsl(url_parts[4]))
                        query.update(params)
                        url_parts[4] = urlencode(query)
                        final_url = urlunparse(url_parts)
                    except json.JSONDecodeError:
                        safe_print(f"   -> [警告] Webhook 查询参数格式错误，请检查 .env 中的 WEBHOOK_QUERY_PARAMETERS。")

                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(final_url, headers=headers, timeout=15)
                )

            elif config["WEBHOOK_METHOD"] == "POST":
                # 准备请求体
                data = None
                json_payload = None

                if config["WEBHOOK_BODY"]:
                    body_str = replace_placeholders(config["WEBHOOK_BODY"])
                    try:
                        if config["WEBHOOK_CONTENT_TYPE"] == "JSON":
                            json_payload = json.loads(body_str)
                            if 'Content-Type' not in headers and 'content-type' not in headers:
                                headers['Content-Type'] = 'application/json; charset=utf-8'
                        elif config["WEBHOOK_CONTENT_TYPE"] == "FORM":
                            data = json.loads(body_str)  # requests会处理url-encoding
                            if 'Content-Type' not in headers and 'content-type' not in headers:
                                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                        else:
                            safe_print(f"   -> [警告] 不支持的 WEBHOOK_CONTENT_TYPE: {config['WEBHOOK_CONTENT_TYPE']}。")
                    except json.JSONDecodeError:
                        safe_print(f"   -> [警告] Webhook 请求体格式错误，请检查 .env 中的 WEBHOOK_BODY。")

                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(config["WEBHOOK_URL"], headers=headers, json=json_payload, data=data, timeout=15)
                )
            else:
                safe_print(f"   -> [警告] 不支持的 WEBHOOK_METHOD: {config['WEBHOOK_METHOD']}。")
                return

            response.raise_for_status()
            safe_print(f"   -> Webhook 通知发送成功。状态码: {response.status_code}")

        except requests.exceptions.RequestException as e:
            safe_print(f"   -> 发送 Webhook 通知失败: {e}")
        except Exception as e:
            safe_print(f"   -> 发送 Webhook 通知时发生未知错误: {e}")


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
