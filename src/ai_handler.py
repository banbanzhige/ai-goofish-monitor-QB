import asyncio
import copy
import base64
import json
import os
import re
import sys
import shutil
from datetime import datetime

import requests

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
    AI_VISION_ENABLED,
    ENABLE_RESPONSE_FORMAT,
    client,
)
from src.utils import retry_on_failure

# 商品图片数量上限：站点固定最多9张，运行期用常量兜底
MAX_PRODUCT_IMAGE_COUNT = 9

# 动态加载通知配置的函数
def get_dynamic_config():
    """动态加载配置，支持实时更新"""
    from src.config import (
        NTFY_TOPIC_URL,
        GOTIFY_URL,
        GOTIFY_TOKEN,
        BARK_URL,
        PCURL_TO_MOBILE,
        WX_BOT_URL,
        WX_CORP_ID,
        WX_AGENT_ID,
        WX_SECRET,
        WX_TO_USER,
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        WEBHOOK_URL,
        WEBHOOK_METHOD,
        WEBHOOK_HEADERS,
        WEBHOOK_CONTENT_TYPE,
        WEBHOOK_QUERY_PARAMETERS,
        WEBHOOK_BODY,
    )

    return {
        "NTFY_TOPIC_URL": NTFY_TOPIC_URL(),
        "GOTIFY_URL": GOTIFY_URL(),
        "GOTIFY_TOKEN": GOTIFY_TOKEN(),
        "BARK_URL": BARK_URL(),
        "PCURL_TO_MOBILE": PCURL_TO_MOBILE(),
        "WX_BOT_URL": WX_BOT_URL(),
        "WX_CORP_ID": WX_CORP_ID(),
        "WX_AGENT_ID": WX_AGENT_ID(),
        "WX_SECRET": WX_SECRET(),
        "WX_TO_USER": WX_TO_USER(),
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN(),
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID(),
        "WEBHOOK_URL": WEBHOOK_URL(),
        "WEBHOOK_METHOD": WEBHOOK_METHOD(),
        "WEBHOOK_HEADERS": WEBHOOK_HEADERS(),
        "WEBHOOK_CONTENT_TYPE": WEBHOOK_CONTENT_TYPE(),
        "WEBHOOK_QUERY_PARAMETERS": WEBHOOK_QUERY_PARAMETERS(),
        "WEBHOOK_BODY": WEBHOOK_BODY(),
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


async def send_test_task_completion_notification(channel: str):
    """
    向指定渠道发送任务完成通知的测试。
    
    Args:
        channel (str): 要发送通知的渠道 (ntfy, gotify, bark, wx_bot, wx_app, telegram, webhook)
        
    Returns:
        bool: 如果通知发送成功返回True，否则返回False
    """
    from src.notifier import notifier
    return await notifier.send_test_task_completion_notification(channel)


async def send_test_product_notification(channel: str):
    """
    向指定渠道发送商品卡测试通知。
    
    Args:
        channel (str): 要发送通知的渠道 (ntfy, gotify, bark, wx_bot, wx_app, telegram, webhook)
        
    Returns:
        bool: 如果通知发送成功返回True，否则返回False
    """
    from src.notifier import notifier
    return await notifier.send_test_product_notification(channel)




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


# 推荐等级与推荐判定集合（运行期与下游消费保持一致口径）
RECOMMENDATION_LEVELS = {
    "STRONG_BUY",
    "CAUTIOUS_BUY",
    "CONDITIONAL_BUY",
    "NOT_RECOMMENDED",
}
RECOMMENDED_LEVELS = {
    "STRONG_BUY",
    "CAUTIOUS_BUY",
    "CONDITIONAL_BUY",
}


def _is_recommended_level(level):
    """根据推荐等级判断是否属于推荐集合。"""
    return isinstance(level, str) and level in RECOMMENDED_LEVELS


def _backfill_and_normalize_ai_response(parsed_response):
    """对新结构字段做最小回填与归一化，避免下游出现空字段。"""
    if not isinstance(parsed_response, dict):
        return parsed_response

    level = parsed_response.get("recommendation_level")
    is_recommended = parsed_response.get("is_recommended")

    # 若缺少推荐等级但有布尔推荐结论，做最小映射回填
    if level not in RECOMMENDATION_LEVELS and isinstance(is_recommended, bool):
        parsed_response["recommendation_level"] = "STRONG_BUY" if is_recommended else "NOT_RECOMMENDED"
        safe_print("   [AI分析] 警告：缺少recommendation_level，已基于is_recommended回填")
        level = parsed_response["recommendation_level"]

    # 若有推荐等级但布尔值缺失或不一致，以推荐等级为准
    if level in RECOMMENDATION_LEVELS:
        expected_bool = _is_recommended_level(level)
        if not isinstance(is_recommended, bool) or is_recommended != expected_bool:
            parsed_response["is_recommended"] = expected_bool
            safe_print("   [AI分析] 警告：is_recommended与recommendation_level不一致，已按等级修正")

    # action_required/risk_tags 统一为列表，避免前端/通知类型错误
    if not isinstance(parsed_response.get("action_required"), list):
        parsed_response["action_required"] = []
    if not isinstance(parsed_response.get("risk_tags"), list):
        parsed_response["risk_tags"] = []

    # 置信度统一归一化到 0-1 区间（兼容 0-100 的旧输出）
    confidence_score = parsed_response.get("confidence_score")
    if isinstance(confidence_score, (int, float)):
        normalized_score = float(confidence_score)
        if normalized_score > 1.0 and normalized_score <= 100.0:
            normalized_score = normalized_score / 100.0
            safe_print("   [AI分析] 警告：confidence_score疑似0-100区间，已归一化到0-1")
        if normalized_score < 0.0 or normalized_score > 1.0:
            normalized_score = min(1.0, max(0.0, normalized_score))
            safe_print("   [AI分析] 警告：confidence_score超出范围，已截断到0-1")
        parsed_response["confidence_score"] = round(normalized_score, 4)
    else:
        # 若缺失置信度，提供最小兜底值，避免下游空值判断异常
        fallback_score = 0.9 if parsed_response.get("is_recommended") else 0.0
        parsed_response["confidence_score"] = fallback_score
        safe_print("   [AI分析] 警告：缺少confidence_score，已使用兜底值")

    return parsed_response


def validate_ai_response_format(parsed_response):
    """验证AI响应是否符合新结构要求（含最小回填与类型校验）。"""
    if not isinstance(parsed_response, dict):
        safe_print("   [AI分析] 警告：AI响应不是字典结构")
        return False

    # 先做一次最小回填与归一化，降低下游出现空字段的概率
    _backfill_and_normalize_ai_response(parsed_response)

    required_fields = [
        "prompt_version",
        "recommendation_level",
        "confidence_score",
        "is_recommended",
        "reason",
        "action_required",
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
    recommendation_level = parsed_response.get("recommendation_level")
    if recommendation_level not in RECOMMENDATION_LEVELS:
        safe_print("   [AI分析] 警告：recommendation_level不在允许集合内")
        return False

    confidence_score = parsed_response.get("confidence_score")
    if not isinstance(confidence_score, (int, float)) or not (0.0 <= float(confidence_score) <= 1.0):
        safe_print("   [AI分析] 警告：confidence_score必须为0-1之间的数值")
        return False

    if not isinstance(parsed_response.get("is_recommended"), bool):
        safe_print("   [AI分析] 警告：is_recommended字段不是布尔类型")
        return False

    if not isinstance(parsed_response.get("action_required"), list):
        safe_print("   [AI分析] 警告：action_required字段不是列表类型")
        return False

    if not isinstance(parsed_response.get("risk_tags"), list):
        safe_print("   [AI分析] 警告：risk_tags字段不是列表类型")
        return False

    return True


# 自定义异常类，用于表示AI调用失败需要停止任务
class AICallFailureException(Exception):
    """当AI调用多次失败需要停止任务时抛出的异常"""
    def __init__(self, message="AI调用多次失败，任务需要停止"):
        self.message = message
        super().__init__(self.message)

from src.notifier import notifier

async def send_all_notifications(product_data, reason):
    """
    向所有配置的渠道发送通知。
    
    Returns:
        dict: 向每个渠道发送通知的结果
    """
    return await notifier.send_product_notification(product_data, reason)

# 全局AI调用失败计数器
ai_call_failure_count = 0
# AI调用失败阈值，达到此次数时停止任务
AI_CALL_FAILURE_THRESHOLD = 3



@retry_on_failure(retries=3, delay=5)
async def get_ai_analysis(product_data, image_paths=None, prompt_text=""):
    """将完整的商品JSON数据和所有图片发送给 AI 进行分析（异步）。"""
    global ai_call_failure_count
    
    if not client:
        safe_print("   [AI分析] 错误：AI客户端未初始化，跳过分析。")
        return None

    item_info = product_data.get('商品信息', {})
    product_id = item_info.get('商品ID', 'N/A')

    # 统一从商品图片列表字段提取URL，避免重复注入image_url导致冗余
    product_info = product_data.get('商品信息', {})
    raw_image_urls = product_info.get('商品图片列表', [])
    valid_image_urls = [
        url for url in raw_image_urls
        if isinstance(url, str) and url.startswith('http')
    ]
    actual_image_count = len(valid_image_urls)
    ai_vision_enabled = AI_VISION_ENABLED()
    has_image_input = actual_image_count > 0 and ai_vision_enabled

    safe_print(f"\n   [AI分析] 开始分析商品 #{product_id} (含 {actual_image_count} 张图片)...")
    safe_print(f"   [AI分析] 标题: {item_info.get('商品标题', '无')}")

    if not prompt_text:
        safe_print("   [AI分析] 错误：未提供AI分析所需的prompt文本。")
        return None

    system_prompt = prompt_text

    # 为提示词构造一个可控的payload副本，必要时按上限裁剪图片URL列表
    product_payload = copy.deepcopy(product_data)
    payload_info = product_payload.get('商品信息', {})
    selected_urls = []

    if valid_image_urls:
        selected_urls = valid_image_urls[:MAX_PRODUCT_IMAGE_COUNT]
        payload_info['商品图片列表'] = selected_urls
        safe_print(
            f"   [AI分析] 商品图片列表已按站点上限裁剪为 {len(selected_urls)} / {MAX_PRODUCT_IMAGE_COUNT}"
        )
    else:
        safe_print("   [AI分析] 商品图片列表为空或无有效URL")
    product_payload['商品信息'] = payload_info

    product_details_json = json.dumps(product_payload, ensure_ascii=False, indent=2)

    if AI_DEBUG_MODE():
        safe_print("\n--- [AI DEBUG] ---")
        safe_print("--- PRODUCT DATA (JSON) ---")
        safe_print(product_details_json)
        safe_print("--- PROMPT TEXT (完整内容) ---")
        safe_print(prompt_text)
        safe_print("-------------------\n")

    multimodal_instruction = ""
    if has_image_input:
        multimodal_instruction = (
            "\n补充说明：商品JSON中的“商品图片列表”字段提供图片URL列表。"
            "如可访问这些图片，请将其用于成色、瑕疵、真实性与关键细节完整性的视觉评估，"
            "并在证据或结论中体现图片带来的判断依据；如无法访问图片，也要明确标注证据不足。"
        )
    elif actual_image_count > 0:
        multimodal_instruction = (
            "\n补充说明：已发现商品图片URL，但当前未开启AI多模态输入，请仅依据文本信息判断，"
            "并明确标注“视觉证据不足”。"
        )

    combined_text_prompt = f"""请基于你的专业知识和我的要求，分析以下完整的商品JSON数据：

```json
    {product_details_json}
```

{system_prompt}
{multimodal_instruction}
    """
    user_content_list = []

    # 多模态输入由开关控制，开启后追加image_url

    # 再添加文本内容
    user_content_list.append({"type": "text", "text": combined_text_prompt})

    if ai_vision_enabled and selected_urls:
        for url in selected_urls:
            user_content_list.append({"type": "image_url", "image_url": {"url": url}})
        safe_print(f"   [AI分析] 多模态已启用，已附加 {len(selected_urls)} 张图片")
    elif ai_vision_enabled and actual_image_count == 0:
        safe_print("   [AI分析] 多模态已启用，但商品图片列表为空")
    elif not ai_vision_enabled:
        safe_print("   [AI分析] 多模态未启用，仅发送文本给模型")

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
                    
                    # 新增: 计算多维度推荐度
                    try:
                        from src.recommendation_scorer import RecommendationScorer
                        scorer = RecommendationScorer()
                        recommendation_result = scorer.calculate(product_data, parsed_response)
                        parsed_response['recommendation_score_v2'] = recommendation_result
                        safe_print(f"   [推荐度] 综合推荐度: {recommendation_result['recommendation_score']}分")
                        safe_print(f"   [推荐度] 贝叶斯: {recommendation_result['bayesian']['score']*100:.1f}分 | "
                                 f"视觉AI: {recommendation_result['visual_ai']['score']*100:.1f}分 | "
                                 f"AI置信: {recommendation_result['fusion']['ai_score']:.1f}分")
                    except Exception as scorer_error:
                        safe_print(f"   [推荐度] 计算推荐度时出错(不影响主流程): {scorer_error}")
                        # 推荐度计算失败不影响主流程，继续返回原始AI分析
                    
                    return parsed_response
                else:
                    safe_print(f"   [AI分析] 第{attempt + 1}次尝试格式验证失败")
                    if attempt < max_retries - 1:
                        safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                        continue
                    else:
                        safe_print("   [AI分析] 所有重试完成，使用最后一次结果")
                        
                        # 新增: 计算多维度推荐度
                        try:
                            from src.recommendation_scorer import RecommendationScorer
                            scorer = RecommendationScorer()
                            recommendation_result = scorer.calculate(product_data, parsed_response)
                            parsed_response['recommendation_score_v2'] = recommendation_result
                            safe_print(f"   [推荐度] 综合推荐度: {recommendation_result['recommendation_score']}分")
                        except Exception as scorer_error:
                            safe_print(f"   [推荐度] 计算推荐度时出错: {scorer_error}")
                        
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
                            
                            # 新增: 计算多维度推荐度
                            try:
                                from src.recommendation_scorer import RecommendationScorer
                                scorer = RecommendationScorer()
                                recommendation_result = scorer.calculate(product_data, parsed_response)
                                parsed_response['recommendation_score_v2'] = recommendation_result
                                safe_print(f"   [推荐度] 综合推荐度: {recommendation_result['recommendation_score']}分")
                            except Exception as scorer_error:
                                safe_print(f"   [推荐度] 计算推荐度时出错: {scorer_error}")
                            
                            return parsed_response
                        else:
                            if attempt < max_retries - 1:
                                safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                                continue
                            else:
                                safe_print("   [AI分析] 所有重试完成，使用清理后的结果")
                                
                                # 新增: 计算多维度推荐度
                                try:
                                    from src.recommendation_scorer import RecommendationScorer
                                    scorer = RecommendationScorer()
                                    recommendation_result = scorer.calculate(product_data, parsed_response)
                                    parsed_response['recommendation_score_v2'] = recommendation_result
                                    safe_print(f"   [推荐度] 综合推荐度: {recommendation_result['recommendation_score']}分")
                                except Exception as scorer_error:
                                    safe_print(f"   [推荐度] 计算推荐度时出错: {scorer_error}")
                                
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
            ai_call_failure_count += 1
            safe_print(f"   [AI分析] AI调用失败计数: {ai_call_failure_count}/{AI_CALL_FAILURE_THRESHOLD}")
            
            if ai_call_failure_count >= AI_CALL_FAILURE_THRESHOLD:
                safe_print(f"   [AI分析] AI调用失败次数已达到阈值 ({AI_CALL_FAILURE_THRESHOLD})，任务将停止")
                raise AICallFailureException(f"AI调用连续失败 {AI_CALL_FAILURE_THRESHOLD} 次，任务需要停止。失败原因: {str(e)}")
            
            if attempt < max_retries - 1:
                safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                continue
            else:
                raise e
