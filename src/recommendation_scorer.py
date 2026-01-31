"""
推荐度计算模块 - 融合贝叶斯统计与视觉AI的综合评分系统

此模块实现了三层评分架构:
1. 贝叶斯用户评分 - 基于卖家历史数据的统计概率
2. 视觉AI产品评分 - 基于商品图片的质量评估  
3. 综合推荐度融合 - 加权融合最终得分

Author: AI闲鱼监控系统
Version: 1.0.0
Date: 2026-01-30
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional, List


class RecommendationScorer:
    """推荐度计算器 - 多维度商品推荐评分系统"""
    
    def __init__(self, config_path: str = "prompts/bayes/bayes_v1.json"):
        """
        初始化评分器，从配置文件加载权重参数
        
        Args:
            config_path: 配置文件路径，默认为 prompts/bayes/bayes_v1.json
        """
        import json
        import os
        
        # 默认权重（作为后备）
        default_fusion_config = {
            "weights": {"bayesian": 0.40, "visual": 0.35, "ai": 0.25},
            "weights_no_visual": {"bayesian": 0.50, "visual": 0.00, "ai": 0.50},
            "bayesian_features": {
                'seller_tenure': 0.15, 'positive_rate': 0.25, 'seller_credit_level': 0.20,
                'sales_ratio': 0.10, 'used_years': 0.15, 'freshness': 0.05,
                'has_guarantee': 0.10
            },
            "visual_features": {
                'image_quality': 0.30, 'condition': 0.30, 
                'authenticity': 0.25, 'completeness': 0.15
            },
            "risk_penalty": {"per_tag_penalty": 5, "max_penalty": 20}
        }
        
        # 尝试从配置文件加载
        fusion_config = default_fusion_config
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'recommendation_fusion' in config:
                        fusion_config = config['recommendation_fusion']
                        print(f"[推荐度] 已从 {config_path} 加载融合权重配置")
            except Exception as e:
                print(f"[推荐度] 配置文件读取失败，使用默认权重: {e}")
        else:
            print(f"[推荐度] 配置文件不存在，使用默认权重")
        
        # 设置权重
        self.bayesian_weights = fusion_config.get('bayesian_features', 
                                                  default_fusion_config['bayesian_features'])
        self.visual_weights = fusion_config.get('visual_features',
                                                default_fusion_config['visual_features'])
        self.fusion_weights = fusion_config.get('weights',
                                                default_fusion_config['weights'])
        self.fusion_weights_no_visual = fusion_config.get('weights_no_visual',
                                                          default_fusion_config['weights_no_visual'])
        
        # 风险惩罚配置
        risk_config = fusion_config.get('risk_penalty', default_fusion_config['risk_penalty'])
        self.risk_per_tag_penalty = risk_config.get('per_tag_penalty', 5)
        self.risk_max_penalty = risk_config.get('max_penalty', 20)

        # 贝叶斯评分规则
        self.scoring_rules = fusion_config.get('scoring_rules')
    
    
    def calculate(self, product_data: Dict[str, Any], ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算综合推荐度
        
        Args:
            product_data: 完整的商品数据
            ai_analysis: AI分析结果
            
        Returns:
            {
                'recommendation_score': 85.5,  # 最终推荐度 0-100
                'bayesian': {...},             # 贝叶斯详情
                'visual_ai': {...},            # 视觉AI详情
                'fusion': {...}                # 融合详情
            }
        """
        # 1. 计算贝叶斯推荐度
        bayesian_result = self._calculate_bayesian_score(product_data, ai_analysis)
        
        # 2. 计算视觉AI推荐度
        visual_result = self._calculate_visual_ai_score(product_data, ai_analysis)
        
        # 3. 融合最终推荐度
        fusion_result = self._calculate_final_score(
            bayesian_result, 
            visual_result, 
            ai_analysis
        )
        
        return {
            'recommendation_score': fusion_result['score'],
            'bayesian': bayesian_result,
            'visual_ai': visual_result,
            'fusion': fusion_result
        }
    
    def _calculate_bayesian_score(self, product_data: Dict[str, Any], 
                                  ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        '''计算贝叶斯评分'''
        seller_info = product_data.get('卖家信息', {})
        product_info = product_data.get('商品信息', {})

        missing_rules: List[str] = []
        features: Dict[str, Optional[float]] = {}

        features['seller_tenure'] = self._normalize_tenure(
            seller_info.get('卖家注册时长', ''),
            missing_rules
        )
        features['positive_rate'] = self._normalize_positive_rate(
            seller_info.get('作为卖家的好评率', ''),
            missing_rules
        )
        features['seller_credit_level'] = self._normalize_seller_credit_level(
            seller_info.get('卖家信用等级')
            or seller_info.get('买家信用等级', ''),
            missing_rules
        )
        features['sales_ratio'] = self._calculate_sales_ratio(
            seller_info.get('卖家在售/已售商品数', ''),
            missing_rules
        )
        features['used_years'] = self._normalize_used_years(
            product_info.get('已用年限', ''),
            missing_rules
        )
        features['freshness'] = self._calculate_freshness(
            product_info.get('发布时间', ''),
            missing_rules
        )
        features['has_guarantee'] = self._check_guarantee(product_data, missing_rules)

        missing_features = [key for key, value in features.items() if not isinstance(value, (int, float))]
        missing_rule_score = self._get_missing_rule_score()

        features_used: Dict[str, Optional[float]] = {}
        for key, value in features.items():
            if isinstance(value, (int, float)):
                features_used[key] = float(value)
            elif isinstance(missing_rule_score, (int, float)):
                features_used[key] = float(missing_rule_score)
            else:
                features_used[key] = None

        if any(value is None for value in features_used.values()):
            bayesian_score = None
        else:
            bayesian_score = 0.0
            for key, value in features_used.items():
                weight = self.bayesian_weights.get(key, 0)
                if isinstance(weight, (int, float)):
                    bayesian_score += value * weight
            bayesian_score = self._adjust_by_seller_type(bayesian_score, ai_analysis)

        features_display = {
            key: (round(value, 4) if isinstance(value, (int, float)) else '缺失')
            for key, value in features.items()
        }
        features_used_display = {
            key: (round(value, 4) if isinstance(value, (int, float)) else None)
            for key, value in features_used.items()
        }

        return {
            'score': round(bayesian_score, 4) if isinstance(bayesian_score, (int, float)) else None,
            'features': features_display,
            'features_used': features_used_display,
            'weights': self.bayesian_weights,
            'raw_score': round(bayesian_score, 4) if isinstance(bayesian_score, (int, float)) else None,
            'missing_rules': missing_rules,
            'missing_features': missing_features
        }


    def _calculate_visual_ai_score(self, product_data: Dict[str, Any],
                                   ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        '''计算视觉AI评分'''
        product_info = product_data.get('商品信息', {})
        image_urls = product_info.get('商品图片列表', [])
        image_count = len([url for url in image_urls if isinstance(url, str) and url.startswith('http')])

        missing_rules: List[str] = []

        if image_count == 0:
            return {
                'score': 0.0,
                'breakdown': {},
                'note': '商品无有效图片',
                'missing_rules': missing_rules,
                'missing_features': []
            }

        visual_rules = self._get_scoring_rule('visual', missing_rules)
        if not isinstance(visual_rules, dict):
            return {
                'score': None,
                'breakdown': {},
                'note': '缺少评分规则',
                'missing_rules': missing_rules,
                'missing_features': ['image_quality', 'condition', 'authenticity', 'completeness']
            }

        criteria = ai_analysis.get('criteria_analysis', {})
        reason = ai_analysis.get('reason', '')

        visual_scores: Dict[str, Optional[float]] = {}

        image_quality_rule = self._get_visual_rule(visual_rules, 'image_quality', missing_rules)
        visual_scores['image_quality'] = self._extract_image_quality_score(reason, criteria, image_quality_rule)

        condition_rule = self._get_visual_rule(visual_rules, 'condition', missing_rules)
        visual_scores['condition'] = self._extract_condition_score(reason, criteria, condition_rule)

        authenticity_rule = self._get_visual_rule(visual_rules, 'authenticity', missing_rules)
        visual_scores['authenticity'] = self._extract_authenticity_score(reason, criteria, authenticity_rule)

        completeness_rule = self._get_visual_rule(visual_rules, 'completeness', missing_rules)
        if isinstance(completeness_rule, dict):
            max_images = completeness_rule.get('max_images')
            min_score = completeness_rule.get('min_score', 0)
            if isinstance(max_images, (int, float)) and max_images > 0:
                score = min(1.0, image_count / float(max_images))
                if isinstance(min_score, (int, float)):
                    score = max(float(min_score), score)
                visual_scores['completeness'] = score
            else:
                visual_scores['completeness'] = None
        else:
            visual_scores['completeness'] = None

        missing_features = [key for key, value in visual_scores.items() if not isinstance(value, (int, float))]
        missing_rule_score = self._get_missing_rule_score()

        visual_scores_used: Dict[str, Optional[float]] = {}
        for key, value in visual_scores.items():
            if isinstance(value, (int, float)):
                visual_scores_used[key] = float(value)
            elif isinstance(missing_rule_score, (int, float)):
                visual_scores_used[key] = float(missing_rule_score)
            else:
                visual_scores_used[key] = None

        if any(value is None for value in visual_scores_used.values()):
            visual_score = None
        else:
            visual_score = 0.0
            for key, value in visual_scores_used.items():
                weight = self.visual_weights.get(key, 0)
                if isinstance(weight, (int, float)):
                    visual_score += value * weight

        visual_scores_display = {
            key: (round(value, 4) if isinstance(value, (int, float)) else '缺失')
            for key, value in visual_scores.items()
        }
        visual_scores_used_display = {
            key: (round(value, 4) if isinstance(value, (int, float)) else None)
            for key, value in visual_scores_used.items()
        }

        return {
            'score': round(visual_score, 4) if isinstance(visual_score, (int, float)) else None,
            'breakdown': visual_scores_display,
            'breakdown_used': visual_scores_used_display,
            'weights': self.visual_weights,
            'image_count': image_count,
            'missing_rules': missing_rules,
            'missing_features': missing_features
        }


    def _calculate_final_score(self, bayesian_result: Dict[str, Any],
                              visual_result: Dict[str, Any],
                              ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        '''计算最终融合推荐度分数'''
        bayesian_score = bayesian_result.get('score')
        visual_score = visual_result.get('score')
        ai_confidence = ai_analysis.get('confidence_score', 0.5)

        missing_rules = []
        for item in (bayesian_result.get('missing_rules') or []):
            if item not in missing_rules:
                missing_rules.append(item)
        for item in (visual_result.get('missing_rules') or []):
            if item not in missing_rules:
                missing_rules.append(item)

        has_visual = isinstance(visual_score, (int, float)) and visual_score > 0
        weights = self.fusion_weights if has_visual else self.fusion_weights_no_visual

        if not isinstance(bayesian_score, (int, float)) or not isinstance(visual_score, (int, float)):
            return {
                'score': None,
                'bayesian_score': None,
                'visual_score': None,
                'ai_score': round(float(ai_confidence) * 100, 2) if isinstance(ai_confidence, (int, float)) else None,
                'weights': weights,
                'risk_penalty': 0,
                'risk_tags': ai_analysis.get('risk_tags', []),
                'missing_rules': missing_rules,
                'status': 'missing_rules'
            }

        final_score = (
            bayesian_score * weights.get('bayesian', 0) +
            visual_score * weights.get('visual', 0) +
            ai_confidence * weights.get('ai', 0)
        ) * 100

        risk_tags = ai_analysis.get('risk_tags', [])
        risk_penalty = 0
        if risk_tags and isinstance(risk_tags, list):
            risk_penalty = min(
                self.risk_max_penalty,
                len(risk_tags) * self.risk_per_tag_penalty
            )
            final_score -= risk_penalty

        final_score = max(0, min(100, final_score))

        return {
            'score': round(final_score, 2),
            'bayesian_score': round(bayesian_score * 100, 2),
            'visual_score': round(visual_score * 100, 2),
            'ai_score': round(ai_confidence * 100, 2),
            'weights': weights,
            'risk_penalty': risk_penalty,
            'risk_tags': risk_tags,
            'missing_rules': missing_rules,
            'status': 'ok' if not missing_rules else 'missing_rules'
        }


    def _normalize_tenure(self, tenure_str: str, missing_rules: List[str]) -> Optional[float]:
        '''归一化卖家注册时长'''
        rule = self._get_scoring_rule('seller_tenure', missing_rules)
        if not isinstance(rule, dict):
            return None

        if not tenure_str:
            return self._get_rule_score(rule, 'missing_score')

        tenure_lower = str(tenure_str).lower()
        year_regex = rule.get('year_regex')
        if isinstance(year_regex, str):
            year_match = re.search(year_regex, tenure_lower)
            if year_match:
                try:
                    years = int(year_match.group(1))
                except ValueError:
                    years = None
                if years is not None:
                    for item in rule.get('year_scores', []):
                        min_years = item.get('min_years')
                        score = item.get('score')
                        if isinstance(min_years, (int, float)) and isinstance(score, (int, float)):
                            if years >= min_years:
                                return float(score)

        month_regex = rule.get('month_regex')
        if isinstance(month_regex, str):
            month_match = re.search(month_regex, tenure_lower)
            if month_match:
                try:
                    months = int(month_match.group(1))
                except ValueError:
                    months = None
                if months is not None:
                    for item in rule.get('month_scores', []):
                        min_months = item.get('min_months')
                        score = item.get('score')
                        if isinstance(min_months, (int, float)) and isinstance(score, (int, float)):
                            if months >= min_months:
                                return float(score)

        return self._get_rule_score(rule, 'default_score')


    def _normalize_positive_rate(self, rate_str: str, missing_rules: List[str]) -> Optional[float]:
        '''归一化好评率'''
        rule = self._get_scoring_rule('positive_rate', missing_rules)
        if not isinstance(rule, dict):
            return None

        missing_score = self._get_rule_score(rule, 'missing_score')
        if not rate_str:
            return missing_score

        percentage_regex = rule.get('percentage_regex')
        if not isinstance(percentage_regex, str):
            return missing_score

        match = re.search(percentage_regex, str(rate_str))
        if not match:
            return missing_score

        try:
            percentage = float(match.group(1))
        except ValueError:
            return missing_score

        scale = rule.get('scale')
        if not isinstance(scale, (int, float)) or scale == 0:
            return missing_score

        value = percentage / float(scale)
        min_score = self._get_rule_score(rule, 'min_score')
        max_score = self._get_rule_score(rule, 'max_score')
        if isinstance(min_score, (int, float)):
            value = max(float(min_score), value)
        if isinstance(max_score, (int, float)):
            value = min(float(max_score), value)

        return value


    def _normalize_seller_credit_level(self, credit_str: str, missing_rules: List[str]) -> Optional[float]:
        '''归一化卖家信用等级'''
        rule = self._get_scoring_rule('seller_credit_level', missing_rules)
        if not isinstance(rule, dict):
            return None

        missing_score = self._get_rule_score(rule, 'missing_score')
        if not credit_str:
            return missing_score

        credit_text = str(credit_str).strip()
        if not credit_text:
            return missing_score

        for item in rule.get('text_mapping', []):
            keywords = item.get('keywords')
            score = item.get('score')
            if isinstance(keywords, list) and isinstance(score, (int, float)):
                if any(keyword in credit_text for keyword in keywords if isinstance(keyword, str)):
                    return float(score)

        match = re.search(r'(\d+)', credit_text)
        level = int(match.group(1)) if match else None

        level_rules = rule.get('level_rules', {})
        for key in ['heart', 'diamond', 'crown']:
            level_rule = level_rules.get(key)
            if not isinstance(level_rule, dict):
                continue
            keyword = level_rule.get('keyword')
            if not (isinstance(keyword, str) and keyword in credit_text):
                continue

            missing_level_score = self._get_rule_score(level_rule, 'missing_level_score')
            if level is None:
                return missing_level_score if isinstance(missing_level_score, (int, float)) else missing_score

            base = self._get_rule_score(level_rule, 'base')
            step = self._get_rule_score(level_rule, 'step')
            level_offset = level_rule.get('level_offset', 0)
            min_score = self._get_rule_score(level_rule, 'min')
            max_score = self._get_rule_score(level_rule, 'max')
            if not isinstance(base, (int, float)) or not isinstance(step, (int, float)):
                return missing_score

            if not isinstance(level_offset, (int, float)):
                level_offset = 0

            score = float(base) + float(step) * max(0, level - float(level_offset))
            if isinstance(min_score, (int, float)):
                score = max(float(min_score), score)
            if isinstance(max_score, (int, float)):
                score = min(float(max_score), score)
            return score

        return self._get_rule_score(rule, 'default_score')


    def _calculate_sales_ratio(self, sales_str: str, missing_rules: List[str]) -> Optional[float]:
        '''计算在售/已售比例分数'''
        rule = self._get_scoring_rule('sales_ratio', missing_rules)
        if not isinstance(rule, dict):
            return None

        missing_score = self._get_rule_score(rule, 'missing_score')
        if not sales_str:
            return missing_score

        pair_regex = rule.get('pair_regex')
        if not isinstance(pair_regex, str):
            return missing_score

        match = re.search(pair_regex, str(sales_str))
        if not match:
            return missing_score

        try:
            on_sale = int(match.group(1))
            sold = int(match.group(2))
        except ValueError:
            return missing_score

        sold_zero_score = self._get_rule_score(rule, 'sold_zero_score')
        if sold == 0:
            return sold_zero_score

        denominator = rule.get('sold_score_denominator')
        if not isinstance(denominator, (int, float)) or denominator == 0:
            return missing_score

        sold_score = min(1.0, sold / float(denominator))
        ratio = on_sale / (sold + 1)

        ratio_boost_threshold = rule.get('ratio_boost_threshold')
        ratio_neutral_threshold = rule.get('ratio_neutral_threshold')
        ratio_boost_factor = rule.get('ratio_boost_factor')
        ratio_penalty_factor = rule.get('ratio_penalty_factor')

        if isinstance(ratio_boost_threshold, (int, float)) and ratio < float(ratio_boost_threshold):
            if isinstance(ratio_boost_factor, (int, float)):
                return min(1.0, sold_score * float(ratio_boost_factor))
            return sold_score
        if isinstance(ratio_neutral_threshold, (int, float)) and ratio < float(ratio_neutral_threshold):
            return sold_score
        if isinstance(ratio_penalty_factor, (int, float)):
            return sold_score * float(ratio_penalty_factor)
        return sold_score


    def _normalize_used_years(self, used_years_str: str, missing_rules: List[str]) -> Optional[float]:
        '''归一化已用年限'''
        rule = self._get_scoring_rule('used_years', missing_rules)
        if not isinstance(rule, dict):
            return None

        missing_score = self._get_rule_score(rule, 'missing_score')
        if not used_years_str or used_years_str in ['??', 'N/A', '']:
            return missing_score

        used_years_lower = str(used_years_str).lower().strip()

        # 使用新的 text_mappings 格式进行匹配
        text_mappings = rule.get('text_mappings', [])
        if isinstance(text_mappings, list):
            for mapping in text_mappings:
                if not isinstance(mapping, dict):
                    continue
                
                keywords = mapping.get('keywords', [])
                score = mapping.get('score')
                excludes = mapping.get('_排除', [])  # 排除关键词，避免误匹配
                
                if not isinstance(keywords, list) or not isinstance(score, (int, float)):
                    continue
                
                # 检查是否匹配任何关键词
                matched = False
                for keyword in keywords:
                    if isinstance(keyword, str) and keyword.lower() in used_years_lower:
                        matched = True
                        break
                
                # 如果匹配了但也包含排除关键词，则跳过
                if matched and isinstance(excludes, list):
                    excluded = False
                    for exclude in excludes:
                        if isinstance(exclude, str) and exclude.lower() in used_years_lower:
                            excluded = True
                            break
                    if excluded:
                        continue
                
                if matched:
                    return float(score)

        # 无法匹配时返回默认分数
        return self._get_rule_score(rule, 'default_score')


    def _calculate_freshness(self, publish_time_str: str, missing_rules: List[str]) -> Optional[float]:
        '''计算发布时间新鲜度'''
        rule = self._get_scoring_rule('freshness', missing_rules)
        if not isinstance(rule, dict):
            return None

        missing_score = self._get_rule_score(rule, 'missing_score')
        if not publish_time_str or publish_time_str == '??':
            return missing_score

        try:
            publish_text = str(publish_time_str)
            recent_keywords = rule.get('recent_keywords', [])
            if isinstance(recent_keywords, list) and any(keyword in publish_text for keyword in recent_keywords if isinstance(keyword, str)):
                recent_score = self._get_rule_score(rule, 'recent_score')
                return recent_score

            day_regex = rule.get('day_regex')
            if isinstance(day_regex, str):
                match = re.search(day_regex, publish_text)
                if match:
                    days = int(match.group(1))
                    for item in rule.get('day_scores', []):
                        max_days = item.get('max_days')
                        score = item.get('score')
                        if isinstance(max_days, (int, float)) and isinstance(score, (int, float)):
                            if days <= max_days:
                                return float(score)

            absolute_date_regex = rule.get('absolute_date_regex')
            if isinstance(absolute_date_regex, str) and re.search(absolute_date_regex, publish_text):
                absolute_score = self._get_rule_score(rule, 'absolute_date_score')
                return absolute_score
        except Exception:
            return missing_score

        return self._get_rule_score(rule, 'default_score')


    def _check_guarantee(self, product_data: Dict[str, Any], missing_rules: List[str]) -> Optional[float]:
        '''检查是否有担保'''
        rule = self._get_scoring_rule('has_guarantee', missing_rules)
        if not isinstance(rule, dict):
            return None

        true_score = self._get_rule_score(rule, 'true_score')
        false_score = self._get_rule_score(rule, 'false_score')

        has_inspection = product_data.get('inspection_service', False)
        has_account_assurance = product_data.get('account_assurance', False)

        if has_inspection or has_account_assurance:
            return true_score

        return false_score


    def _adjust_by_seller_type(self, score: float, 
                               ai_analysis: Dict[str, Any]) -> float:
        """
        根据卖家类型调整贝叶斯评分
        
        优质卖家加分，疑似刷单/高风险减分
        """
        criteria = ai_analysis.get('criteria_analysis', {})
        seller_type = criteria.get('seller_type', {})
        persona = seller_type.get('persona', '')
        
        if not persona:
            return score
        
        persona_lower = persona.lower()
        
        # 惩罚因子
        if any(keyword in persona_lower for keyword in [
            '疑似刷单', '高风险', '异常', '欺诈'
        ]):
            return score * 0.5
        
        # 奖励因子
        if any(keyword in persona_lower for keyword in [
            '优质', '专业', '可信', '资深'
        ]):
            return min(1.0, score * 1.2)
        
        return score
    
    # ==================== 配置规则访问辅助方法 ====================
    
    def _get_scoring_rule(self, rule_name: str, missing_rules: List[str]) -> Optional[Dict[str, Any]]:
        """
        从配置中获取指定的评分规则
        
        Args:
            rule_name: 规则名称，如 'seller_tenure', 'visual' 等
            missing_rules: 缺失规则列表，用于记录未找到的规则
            
        Returns:
            规则字典，如果不存在则返回 None
        """
        if not isinstance(self.scoring_rules, dict):
            if rule_name not in missing_rules:
                missing_rules.append(rule_name)
            return None
        
        rule = self.scoring_rules.get(rule_name)
        if not isinstance(rule, dict):
            if rule_name not in missing_rules:
                missing_rules.append(rule_name)
            return None
        
        return rule
    
    def _get_rule_score(self, rule: Dict[str, Any], score_key: str) -> Optional[float]:
        """
        从规则字典中提取指定的分数值
        
        Args:
            rule: 规则字典
            score_key: 分数键名，如 'missing_score', 'default_score' 等
            
        Returns:
            分数值（0.0-1.0），如果不存在则返回 None
        """
        if not isinstance(rule, dict):
            return None
        
        score = rule.get(score_key)
        if isinstance(score, (int, float)):
            return float(score)
        
        return None
    
    def _get_visual_rule(self, visual_rules: Dict[str, Any], 
                        feature_name: str, 
                        missing_rules: List[str]) -> Optional[Dict[str, Any]]:
        """
        从视觉规则中获取指定特征的规则
        
        Args:
            visual_rules: 视觉规则字典
            feature_name: 特征名称，如 'image_quality', 'condition' 等
            missing_rules: 缺失规则列表
            
        Returns:
            特征规则字典，如果不存在则返回 None
        """
        if not isinstance(visual_rules, dict):
            rule_id = f"visual.{feature_name}"
            if rule_id not in missing_rules:
                missing_rules.append(rule_id)
            return None
        
        feature_rule = visual_rules.get(feature_name)
        if not isinstance(feature_rule, dict):
            rule_id = f"visual.{feature_name}"
            if rule_id not in missing_rules:
                missing_rules.append(rule_id)
            return None
        
        return feature_rule
    
    def _get_missing_rule_score(self) -> Optional[float]:
        """
        获取规则缺失时的默认分数
        
        Returns:
            默认分数（通常为 0.5），如果配置不存在则返回 None
        """
        if not isinstance(self.scoring_rules, dict):
            return None
        
        score = self.scoring_rules.get('missing_rule_score')
        if isinstance(score, (int, float)):
            return float(score)
        
        return None
    
    # ==================== 视觉AI特征提取方法 ====================
    
    def _extract_image_quality_score(self, reason: str, 
                                     criteria: Dict[str, Any],
                                     rule: Optional[Dict[str, Any]]) -> Optional[float]:
        '''从AI分析中提取图片质量分数'''
        if not isinstance(rule, dict):
            return None

        reason_lower = str(reason).lower()
        high_keywords = rule.get('high_keywords', [])
        mid_keywords = rule.get('mid_keywords', [])
        low_keywords = rule.get('low_keywords', [])

        if isinstance(high_keywords, list) and any(keyword in reason_lower for keyword in high_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'high_score')
        if isinstance(low_keywords, list) and any(keyword in reason_lower for keyword in low_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'low_score')
        if isinstance(mid_keywords, list) and any(keyword in reason_lower for keyword in mid_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'mid_score')

        return self._get_rule_score(rule, 'default_score')


    def _extract_condition_score(self, reason: str,
                                 criteria: Dict[str, Any],
                                 rule: Optional[Dict[str, Any]]) -> Optional[float]:
        '''从AI分析中提取物品成色分数'''
        if not isinstance(rule, dict):
            return None

        reason_lower = str(reason).lower()
        high_keywords = rule.get('high_keywords', [])
        good_keywords = rule.get('good_keywords', [])
        normal_keywords = rule.get('normal_keywords', [])
        bad_keywords = rule.get('bad_keywords', [])

        if isinstance(high_keywords, list) and any(keyword in reason_lower for keyword in high_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'high_score')
        if isinstance(good_keywords, list) and any(keyword in reason_lower for keyword in good_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'good_score')
        if isinstance(normal_keywords, list) and any(keyword in reason_lower for keyword in normal_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'normal_score')
        if isinstance(bad_keywords, list) and any(keyword in reason_lower for keyword in bad_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'bad_score')

        return self._get_rule_score(rule, 'default_score')


    def _extract_authenticity_score(self, reason: str,
                                    criteria: Dict[str, Any],
                                    rule: Optional[Dict[str, Any]]) -> Optional[float]:
        '''从AI分析中提取图片真实性分数'''
        if not isinstance(rule, dict):
            return None

        reason_lower = str(reason).lower()
        good_keywords = rule.get('good_keywords', [])
        bad_keywords = rule.get('bad_keywords', [])
        suspect_keywords = rule.get('suspect_keywords', [])

        if isinstance(good_keywords, list) and any(keyword in reason_lower for keyword in good_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'good_score')
        if isinstance(bad_keywords, list) and any(keyword in reason_lower for keyword in bad_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'bad_score')
        if isinstance(suspect_keywords, list) and any(keyword in reason_lower for keyword in suspect_keywords if isinstance(keyword, str)):
            return self._get_rule_score(rule, 'suspect_score')

        return self._get_rule_score(rule, 'default_score')

