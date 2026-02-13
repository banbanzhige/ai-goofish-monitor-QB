"""
特征提取器 - 8维特征向量提取

从商品卡数据中提取8个维度的特征，用于贝叶斯模型训练：
1. 价格区间特征 (0-1)
2. 描述质量特征 (0-1)
3. 卖家信誉特征 (0-1)
4. 图片数量特征 (0-1)
5. 商品新旧程度 (0-1)
6. 发布时间新鲜度 (0-1)
7. 标题匹配度 (0-1)
8. 风险指标 (0-1)
"""
import re
import math
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class FeatureExtractor:
    """8维特征向量提取器"""
    
    # 特征维度定义
    FEATURE_NAMES = [
        'price_score',          # 价格合理性
        'description_quality',  # 描述质量
        'seller_reputation',    # 卖家信誉
        'image_richness',       # 图片丰富度
        'condition_score',      # 商品成色
        'freshness_score',      # 发布新鲜度
        'title_relevance',      # 标题相关性
        'risk_indicator'        # 风险指标
    ]
    
    # 价格区间配置
    PRICE_RANGES = {
        'very_low': (0, 50),
        'low': (50, 200),
        'medium': (200, 1000),
        'high': (1000, 5000),
        'very_high': (5000, float('inf'))
    }
    
    # 描述质量关键词
    QUALITY_KEYWORDS = {
        'positive': ['全新', '未拆封', '正品', '保真', '完美', '无瑕疵', '99新', '95新'],
        'negative': ['瑕疵', '划痕', '故障', '坏了', '不退', '无售后', '垃圾', '慎拍']
    }
    
    # 风险关键词
    RISK_KEYWORDS = ['仅退款', '不退不换', '不保', '二手翻新', '高仿', '非原装', '杂牌']
    
    def __init__(self, keyword: str = None):
        """
        初始化特征提取器
        
        Args:
            keyword: 搜索关键词，用于计算标题相关性
        """
        self.keyword = keyword or ""
    
    def extract(self, product_data: Dict[str, Any]) -> List[float]:
        """
        从商品数据中提取8维特征向量
        
        Args:
            product_data: 商品数据字典
        
        Returns:
            8维特征向量 [0-1]
        """
        return [
            self._extract_price_score(product_data),
            self._extract_description_quality(product_data),
            self._extract_seller_reputation(product_data),
            self._extract_image_richness(product_data),
            self._extract_condition_score(product_data),
            self._extract_freshness_score(product_data),
            self._extract_title_relevance(product_data),
            self._extract_risk_indicator(product_data)
        ]
    
    def _extract_price_score(self, data: Dict) -> float:
        """
        提取价格合理性特征
        
        策略：价格在中等区间得分最高，过低或过高得分降低
        """
        try:
            price = float(data.get('price', 0))
            original_price = float(data.get('original_price', price * 2))
            
            if price <= 0:
                return 0.0
            
            # 基于折扣率计算
            if original_price > 0:
                discount_ratio = price / original_price
                # 30%-70% 折扣区间为最佳
                if 0.3 <= discount_ratio <= 0.7:
                    price_score = 0.8 + (0.5 - abs(discount_ratio - 0.5)) * 0.4
                elif discount_ratio < 0.3:
                    # 价格过低，可能有问题
                    price_score = 0.3 + discount_ratio
                else:
                    # 折扣较少
                    price_score = 0.5 + (1 - discount_ratio) * 0.5
            else:
                # 无原价参考，根据绝对价格判断
                if 50 <= price <= 2000:
                    price_score = 0.7
                elif price < 50:
                    price_score = 0.4  # 价格太低可能有问题
                else:
                    price_score = 0.5
            
            return min(1.0, max(0.0, price_score))
        except (ValueError, TypeError):
            return 0.5  # 默认中等
    
    def _extract_description_quality(self, data: Dict) -> float:
        """
        提取描述质量特征
        
        基于描述长度、正面关键词、负面关键词计算
        """
        description = str(data.get('description', '') or data.get('title', ''))
        
        if not description:
            return 0.3
        
        score = 0.5
        
        # 描述长度加分
        length = len(description)
        if length >= 100:
            score += 0.2
        elif length >= 50:
            score += 0.1
        
        # 正面关键词加分
        positive_count = sum(1 for kw in self.QUALITY_KEYWORDS['positive'] if kw in description)
        score += min(0.2, positive_count * 0.05)
        
        # 负面关键词扣分
        negative_count = sum(1 for kw in self.QUALITY_KEYWORDS['negative'] if kw in description)
        score -= negative_count * 0.1
        
        return min(1.0, max(0.0, score))
    
    def _extract_seller_reputation(self, data: Dict) -> float:
        """
        提取卖家信誉特征
        
        基于卖家等级、交易数量、好评率计算
        """
        seller_info = data.get('seller', {}) or data.get('seller_info', {})
        
        if not seller_info:
            return 0.5
        
        score = 0.5
        
        # 信用等级
        credit = seller_info.get('credit', 0) or seller_info.get('level', 0)
        if credit:
            try:
                credit_val = int(credit)
                score += min(0.2, credit_val * 0.02)
            except (ValueError, TypeError):
                pass
        
        # 交易数量
        trade_count = seller_info.get('trade_count', 0) or seller_info.get('sold_count', 0)
        if trade_count:
            try:
                trade_val = int(trade_count)
                if trade_val >= 100:
                    score += 0.2
                elif trade_val >= 30:
                    score += 0.1
                elif trade_val >= 10:
                    score += 0.05
            except (ValueError, TypeError):
                pass
        
        # 好评率
        good_rate = seller_info.get('good_rate', 0) or seller_info.get('praise_rate', 0)
        if good_rate:
            try:
                rate = float(good_rate)
                if rate > 1:  # 百分比格式
                    rate = rate / 100
                score += rate * 0.2
            except (ValueError, TypeError):
                pass
        
        return min(1.0, max(0.0, score))
    
    def _extract_image_richness(self, data: Dict) -> float:
        """
        提取图片丰富度特征
        
        基于图片数量计算
        """
        images = data.get('images', []) or data.get('pics', [])
        
        if isinstance(images, str):
            images = [images]
        
        count = len(images) if images else 0
        
        # 图片数量评分
        if count >= 9:
            return 1.0
        elif count >= 6:
            return 0.8
        elif count >= 3:
            return 0.6
        elif count >= 1:
            return 0.4
        else:
            return 0.2
    
    def _extract_condition_score(self, data: Dict) -> float:
        """
        提取商品成色特征
        
        基于成色描述关键词计算
        """
        title = str(data.get('title', ''))
        description = str(data.get('description', ''))
        text = f"{title} {description}"
        
        # 成色关键词匹配
        condition_map = {
            '全新': 1.0,
            '未拆封': 1.0,
            '99新': 0.95,
            '95新': 0.85,
            '9成新': 0.8,
            '9新': 0.8,
            '8成新': 0.7,
            '8新': 0.7,
            '7成新': 0.6,
            '7新': 0.6,
            '5成新': 0.4,
            '二手': 0.5,
            '有瑕疵': 0.3,
            '故障': 0.1
        }
        
        for keyword, score in condition_map.items():
            if keyword in text:
                return score
        
        return 0.6  # 默认中等成色
    
    def _extract_freshness_score(self, data: Dict) -> float:
        """
        提取发布时间新鲜度特征
        
        越新发布的商品得分越高
        """
        publish_time = data.get('publish_time', '') or data.get('created_at', '')
        
        if not publish_time:
            return 0.5
        
        try:
            # 尝试解析时间
            if isinstance(publish_time, datetime):
                pub_dt = publish_time
            elif isinstance(publish_time, str):
                # 处理相对时间
                if '分钟前' in publish_time or '分鐘前' in publish_time:
                    return 1.0
                elif '小时前' in publish_time or '小時前' in publish_time:
                    return 0.95
                elif '天前' in publish_time:
                    match = re.search(r'(\d+)', publish_time)
                    if match:
                        days = int(match.group(1))
                        return max(0.3, 1.0 - days * 0.1)
                    return 0.7
                elif '月前' in publish_time:
                    return 0.3
                else:
                    # 尝试解析日期格式
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d']:
                        try:
                            pub_dt = datetime.strptime(publish_time, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        return 0.5
            else:
                return 0.5
            
            # 计算天数差
            days_ago = (datetime.now() - pub_dt).days
            if days_ago <= 1:
                return 1.0
            elif days_ago <= 3:
                return 0.9
            elif days_ago <= 7:
                return 0.8
            elif days_ago <= 14:
                return 0.6
            elif days_ago <= 30:
                return 0.4
            else:
                return 0.2
        except Exception:
            return 0.5
    
    def _extract_title_relevance(self, data: Dict) -> float:
        """
        提取标题与搜索关键词的相关性
        """
        if not self.keyword:
            return 0.5
        
        title = str(data.get('title', ''))
        
        if not title:
            return 0.0
        
        # 简化关键词匹配
        keywords = [kw.strip() for kw in self.keyword.split() if kw.strip()]
        
        if not keywords:
            return 0.5
        
        # 计算匹配率
        matched = sum(1 for kw in keywords if kw.lower() in title.lower())
        match_ratio = matched / len(keywords)
        
        return match_ratio
    
    def _extract_risk_indicator(self, data: Dict) -> float:
        """
        提取风险指标特征
        
        风险越高，返回值越接近 1
        """
        title = str(data.get('title', ''))
        description = str(data.get('description', ''))
        text = f"{title} {description}"
        
        risk_score = 0.0
        
        # 风险关键词
        for keyword in self.RISK_KEYWORDS:
            if keyword in text:
                risk_score += 0.15
        
        # 价格异常低
        try:
            price = float(data.get('price', 0))
            original = float(data.get('original_price', 0))
            if original > 0 and price < original * 0.2:
                risk_score += 0.2  # 低于2折，风险较高
        except (ValueError, TypeError):
            pass
        
        # 无图片
        images = data.get('images', []) or data.get('pics', [])
        if not images:
            risk_score += 0.1
        
        return min(1.0, risk_score)
    
    @classmethod
    def get_feature_names(cls) -> List[str]:
        """获取特征名称列表"""
        return cls.FEATURE_NAMES.copy()


def extract_features(product_data: Dict[str, Any], keyword: str = None) -> List[float]:
    """
    便捷函数：从商品数据中提取8维特征向量
    
    Args:
        product_data: 商品数据字典
        keyword: 搜索关键词
    
    Returns:
        8维特征向量
    """
    extractor = FeatureExtractor(keyword=keyword)
    return extractor.extract(product_data)
