import asyncio
import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from src.utils import convert_goofish_link
from src.notifier.config import config


class BaseNotifier(ABC):
    """通知渠道基类"""

    def __init__(self, channel_name: str):
        self.channel_name = channel_name

    @abstractmethod
    async def send_test_notification(self) -> bool:
        """发送测试通知"""
        pass

    @abstractmethod
    async def send_product_notification(self, product: Dict[str, Any], reason: str) -> bool:
        """发送商品通知"""
        pass

    @abstractmethod
    async def send_task_start_notification(self, task_name: str, reason: str) -> bool:
        """发送任务开始通知"""
        pass

    @abstractmethod
    async def send_task_completion_notification(
        self,
        task_name: str,
        reason: str,
        processed_count: int = 0,
        recommended_count: int = 0,
    ) -> bool:
        """发送任务完成通知"""
        pass

    def _replace_placeholders(self, template_str: str, notification_title: str, message: str) -> str:
        """替换模板中的占位符"""
        if not template_str:
            return ""
        safe_title = json.dumps(notification_title, ensure_ascii=False)[1:-1]
        safe_content = json.dumps(message, ensure_ascii=False)[1:-1]
        # 同时支持两种占位符格式：${key} 和 {{key}}
        return template_str.replace("${title}", safe_title).replace("${content}", safe_content) \
            .replace("{{title}}", safe_title).replace("{{content}}", safe_content)

    def _get_product_info(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """提取商品信息，统一处理不同的数据格式"""
        # 处理两种数据格式：带“商品信息”键和直接的商品数据
        actual_product = product.get("商品信息", product)
        ai_analysis = {}

        # 查找 AI 分析信息的位置
        if "ai_analysis" in actual_product:
            ai_analysis = actual_product["ai_analysis"]
        elif "ai_analysis" in product:
            ai_analysis = product["ai_analysis"]

        # 转换链接
        pc_link = actual_product.get("商品链接", "")
        mobile_link = convert_goofish_link(pc_link)

        # 处理图片
        main_image = actual_product.get("商品主图链接", "")
        if not main_image and actual_product.get("商品图片列表"):
            image_list = actual_product["商品图片列表"]
            main_image = image_list[0] if image_list else ""

        return {
            "actual_product": actual_product,
            "ai_analysis": ai_analysis,
            "pc_link": pc_link,
            "mobile_link": mobile_link,
            "main_image": main_image,
        }

    def _format_notification_content(self, product_info: Dict[str, Any], reason: str) -> tuple:
        """格式化通知内容"""
        actual_product = product_info["actual_product"]
        pc_link = product_info["pc_link"]
        mobile_link = product_info["mobile_link"]

        title = actual_product.get("商品标题", "N/A")
        price = actual_product.get("当前售价", "N/A")
        publish_time = actual_product.get("发布时间", "N/A")

        # 格式化推荐理由
        ai_analysis = product_info["ai_analysis"]
        ai_reason = ai_analysis.get("reason", "") if ai_analysis else ""

        # 新版推荐度系统 - 优先使用 recommendation_score_v2
        rec_v2 = ai_analysis.get("recommendation_score_v2") if ai_analysis else None

        if rec_v2 and isinstance(rec_v2, dict) and isinstance(rec_v2.get("recommendation_score"), (int, float)):
            final_score = rec_v2.get("recommendation_score", 0)
            fusion = rec_v2.get("fusion", {})
            bayes = fusion.get("bayesian_score", 0)
            visual = fusion.get("visual_score", 0)
            ai_conf = fusion.get("ai_score", 0)

            # 评分徽章
            if final_score >= 80:
                badge = "⭐⭐⭐"
            elif final_score >= 60:
                badge = "⭐⭐"
            else:
                badge = "⭐"

            # 推荐等级
            level_map = {
                "STRONG_BUY": "强烈推荐",
                "CAUTIOUS_BUY": "谨慎推荐",
                "CONDITIONAL_BUY": "有条件推荐",
                "NOT_RECOMMENDED": "不推荐",
            }
            level = ai_analysis.get("recommendation_level") if ai_analysis else None
            level_text = level_map.get(level, level) if isinstance(level, str) else ""

            extra_lines = ""
            if level_text:
                extra_lines += f"\n推荐等级: {level_text}"
            extra_lines += f"\n综合推荐度: {final_score:.1f}分{badge}"
            extra_lines += f"\n  └ 贝叶斯{bayes:.0f} | 视觉{visual:.0f} | AI{ai_conf:.0f}"
        else:
            # 降级到旧版置信度显示
            level_map = {
                "STRONG_BUY": "强烈推荐",
                "CAUTIOUS_BUY": "谨慎推荐",
                "CONDITIONAL_BUY": "有条件推荐",
                "NOT_RECOMMENDED": "不推荐",
            }
            level = ai_analysis.get("recommendation_level") if ai_analysis else None
            level_text = level_map.get(level, level) if isinstance(level, str) else ""
            score = ai_analysis.get("confidence_score") if ai_analysis else None
            score_text = f"{float(score):.2f}" if isinstance(score, (int, float)) else ""
            extra_lines = ""
            if level_text:
                extra_lines += f"\n推荐等级: {level_text}"
            if score_text:
                extra_lines += f"\n置信度: {score_text}"

        # 构建消息内容
        if config["PCURL_TO_MOBILE"]:
            # 只发送手机端链接
            if reason and reason != "AI推荐的优质商品" and ai_reason:
                message = (
                    f"价格: {price}\n发布时间: {publish_time}{extra_lines}\n\n"
                    f"推荐理由:\n{ai_reason}\n\n手机端链接: {mobile_link}"
                )
            elif reason == "用户手动发送通知" and ai_reason:
                message = (
                    f"价格: {price}\n发布时间: {publish_time}{extra_lines}\n\n"
                    f"推荐理由:\n{ai_reason}\n\n手机端链接: {mobile_link}"
                )
            elif reason:
                message = (
                    f"价格: {price}\n发布时间: {publish_time}{extra_lines}\n\n"
                    f"推荐理由:\n{reason}\n\n手机端链接: {mobile_link}"
                )
            else:
                message = (
                    f"价格: {price}\n发布时间: {publish_time}{extra_lines}\n\n"
                    f"手机端链接: {mobile_link}"
                )
        else:
            # 同时发送手机端和电脑端链接
            if reason and reason != "AI推荐的优质商品" and ai_reason:
                message = (
                    f"价格: {price}\n发布时间: {publish_time}{extra_lines}\n\n"
                    f"推荐理由:\n{ai_reason}\n\n"
                    f"手机端链接: {mobile_link}\n电脑端链接: {pc_link}"
                )
            elif reason == "用户手动发送通知" and ai_reason:
                message = (
                    f"价格: {price}\n发布时间: {publish_time}{extra_lines}\n\n"
                    f"推荐理由:\n{ai_reason}\n\n"
                    f"手机端链接: {mobile_link}\n电脑端链接: {pc_link}"
                )
            elif reason:
                message = (
                    f"价格: {price}\n发布时间: {publish_time}{extra_lines}\n\n"
                    f"推荐理由:\n{reason}\n\n"
                    f"手机端链接: {mobile_link}\n电脑端链接: {pc_link}"
                )
            else:
                message = (
                    f"价格: {price}\n发布时间: {publish_time}{extra_lines}\n\n"
                    f"手机端链接: {mobile_link}\n电脑端链接: {pc_link}"
                )

        notification_title = f"🐟 新推荐: {title[:30]}..."
        return notification_title, message
