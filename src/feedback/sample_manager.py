"""
样本管理器 - 用户反馈样本的存储与管理

负责贝叶斯训练样本的CRUD操作，支持本地和PostgreSQL双后端。
"""
from typing import Dict, List, Optional, Any

from src.storage import get_storage
from src.web.auth import is_multi_user_mode
from src.logging_config import get_logger
from .feature_extractor import FeatureExtractor


# 样本标签定义
LABEL_TRUSTED = 1       # 可信样本
LABEL_UNTRUSTED = 0     # 不可信样本

# 样本来源定义
SOURCE_USER = 'user'        # 用户反馈
SOURCE_PRESET = 'preset'    # 系统预置
LEGACY_SOURCE_USER = 'user_feedback'  # 兼容历史数据
DEFAULT_PROFILE_VERSION = 'bayes_v1'
VALID_FEEDBACK_TYPES = {'trusted', 'untrusted'}
USER_SOURCE_ALIASES = {SOURCE_USER, LEGACY_SOURCE_USER}

logger = get_logger(__name__, service="system")


class SampleManager:
    """贝叶斯训练样本管理器"""
    
    def __init__(self, user_id: str = None):
        """
        初始化样本管理器
        
        Args:
            user_id: 用户ID，用于数据隔离（多用户模式）
        """
        self.user_id = user_id
        self.storage = get_storage()

    def _resolve_owner_id(self) -> Optional[str]:
        """解析当前请求上下文的 owner_id（仅多用户模式启用）"""
        if not is_multi_user_mode():
            return None
        if not self.user_id:
            raise ValueError("多用户模式下缺少用户上下文，无法写入反馈数据")
        return str(self.user_id)

    def _load_product_data_from_storage(self, result_id: str, owner_id: Optional[str]) -> Dict[str, Any]:
        """在请求未携带商品数据时，尝试按 item_id 从结果存储回填"""
        try:
            record = self.storage.get_result_by_item_id(result_id, owner_id=owner_id)
            if isinstance(record, dict):
                return record
        except Exception as e:
            logger.warning(
                "回填商品数据失败，将使用空数据提取特征",
                extra={"event": "feedback_product_data_fallback_failed", "result_id": result_id, "owner_id": owner_id},
                exc_info=e
            )
        return {}

    def _resolve_profile_version(
        self,
        profile_version: Optional[str],
        product_data: Optional[Dict[str, Any]]
    ) -> str:
        """解析反馈样本应写入的 Bayes 版本。"""
        candidates: List[str] = []
        if profile_version:
            candidates.append(str(profile_version))

        payload = product_data if isinstance(product_data, dict) else {}
        ml_precalc = payload.get("ml_precalc", {}) if isinstance(payload, dict) else {}
        bayes_precalc = ml_precalc.get("bayes", {}) if isinstance(ml_precalc, dict) else {}

        payload_profile = payload.get("profile_version") or payload.get("bayes_profile")
        precalc_profile = bayes_precalc.get("profile") or bayes_precalc.get("version")
        if payload_profile:
            candidates.append(str(payload_profile))
        if precalc_profile:
            candidates.append(str(precalc_profile))

        for candidate in candidates:
            normalized = str(candidate or "").strip()
            if normalized.endswith(".json"):
                normalized = normalized[:-5]
            if normalized:
                return normalized
        return DEFAULT_PROFILE_VERSION

    def add_feedback(
        self,
        result_id: str,
        feedback_type: str,
        product_data: Dict[str, Any],
        keyword: str = None,
        profile_version: str = None
    ) -> Optional[Dict]:
        """
        添加用户反馈并生成训练样本
        
        Args:
            result_id: 商品结果ID
            feedback_type: 反馈类型 'trusted' 或 'untrusted'
            product_data: 商品数据
            keyword: 搜索关键词（用于特征提取）
        
        Returns:
            创建的反馈记录或None
        """
        feedback_type_normalized = str(feedback_type or '').strip().lower()
        if feedback_type_normalized not in VALID_FEEDBACK_TYPES:
            raise ValueError("feedback_type 必须为 trusted 或 untrusted")

        owner_id = self._resolve_owner_id()
        feedback_user_id = str(self.user_id) if self.user_id else "local_admin"

        # 确定标签
        label = LABEL_TRUSTED if feedback_type_normalized == 'trusted' else LABEL_UNTRUSTED

        # 未提供商品数据时，尝试从存储层回填（兼容仅上传 result_id/item_id 的场景）
        payload = product_data if isinstance(product_data, dict) else {}
        if not payload:
            payload = self._load_product_data_from_storage(result_id, owner_id)
        resolved_profile_version = self._resolve_profile_version(profile_version, payload)
        
        # 提取特征向量
        extractor = FeatureExtractor(keyword=keyword)
        feature_vector = extractor.extract(payload)

        # 创建反馈记录（用于审计和后续统计）
        feedback = self.storage.save_feedback(
            user_id=feedback_user_id,
            result_id=result_id,
            feedback_type=feedback_type_normalized,
            feature_vector=feature_vector
        )
        
        if feedback:
            # 同时创建贝叶斯样本
            sample_data = {
                'vector': feature_vector,
                'label': label,
                'source': SOURCE_USER,
                'item_id': result_id,
                'profile_version': resolved_profile_version
            }
            self.storage.add_bayes_sample(sample_data, owner_id=owner_id)
        
        return feedback

    def cancel_feedback(self, result_id: str) -> bool:
        """
        取消用户反馈，同时清除关联贝叶斯样本

        Args:
            result_id: 商品结果ID

        Returns:
            是否成功取消
        """
        feedback_user_id = str(self.user_id) if self.user_id else "local_admin"
        return self.storage.delete_feedback(
            user_id=feedback_user_id,
            result_id=result_id
        )
    
    def batch_add_feedback(
        self,
        feedbacks: List[Dict[str, Any]],
        keyword: str = None
    ) -> Dict[str, int]:
        """
        批量添加用户反馈
        
        Args:
            feedbacks: 反馈列表，每项包含 result_id, feedback_type, product_data
            keyword: 搜索关键词
        
        Returns:
            统计结果 {'success': n, 'failed': m}
        """
        success_count = 0
        failed_count = 0
        
        for item in feedbacks:
            try:
                result = self.add_feedback(
                    result_id=item.get('result_id'),
                    feedback_type=item.get('feedback_type'),
                    product_data=item.get('product_data', {}),
                    keyword=keyword,
                    profile_version=item.get('profile_version')
                )
                if result:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
        
        return {'success': success_count, 'failed': failed_count}
    
    def get_samples(
        self,
        label: int = None,
        source: str = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        获取训练样本
        
        Args:
            label: 筛选标签 (0=不可信, 1=可信, None=全部)
            source: 筛选来源 ('user', 'preset', None=全部)
            limit: 最大返回数量
        
        Returns:
            样本列表
        """
        owner_id = self._resolve_owner_id()
        samples = self.storage.get_bayes_samples(
            profile_version=DEFAULT_PROFILE_VERSION,
            owner_id=owner_id,
            label=label,
            include_system=True
        )

        if source:
            source_normalized = str(source).strip().lower()
            if source_normalized == SOURCE_USER:
                target_sources = USER_SOURCE_ALIASES
            elif source_normalized == SOURCE_PRESET:
                target_sources = {SOURCE_PRESET}
            else:
                target_sources = {source_normalized}

            samples = [
                sample for sample in samples
                if str(sample.get('source') or '').strip().lower() in target_sources
            ]

        if limit is not None and limit >= 0:
            return samples[:limit]
        return samples
    
    def get_sample_stats(self) -> Dict[str, int]:
        """
        获取样本统计信息
        
        Returns:
            统计信息字典
        """
        all_samples = self.get_samples(limit=10000)
        
        stats = {
            'total': len(all_samples),
            'trusted': sum(1 for s in all_samples if s.get('label') == LABEL_TRUSTED),
            'untrusted': sum(1 for s in all_samples if s.get('label') == LABEL_UNTRUSTED),
            'user_samples': sum(
                1 for s in all_samples
                if str(s.get('source') or '').strip().lower() in USER_SOURCE_ALIASES
            ),
            'preset_samples': sum(
                1 for s in all_samples
                if str(s.get('source') or '').strip().lower() == SOURCE_PRESET
            )
        }
        
        return stats
    
    def delete_sample(self, sample_id: str) -> bool:
        """
        删除单个样本
        
        Args:
            sample_id: 样本ID
        
        Returns:
            是否成功
        """
        owner_id = self._resolve_owner_id()
        return self.storage.delete_bayes_sample(sample_id, owner_id=owner_id)
    
    def clear_user_samples(self) -> int:
        """
        清空当前用户的所有样本
        
        Returns:
            删除的样本数量
        """
        samples = self.get_samples(source=SOURCE_USER, limit=10000)
        count = 0
        
        for sample in samples:
            sample_id = sample.get('id') or sample.get('sample_id') or sample.get('item_id')
            if sample_id and self.delete_sample(sample_id):
                count += 1
        
        return count
    
    def reset_to_preset(self) -> Dict[str, int]:
        """
        重置为系统预置样本
        
        清空用户样本，保留预置样本
        
        Returns:
            操作统计
        """
        deleted = self.clear_user_samples()
        preset_count = len(self.get_samples(source=SOURCE_PRESET))
        
        return {
            'deleted_user_samples': deleted,
            'remaining_preset_samples': preset_count
        }
    
    def export_samples(self, format: str = 'dict') -> Any:
        """
        导出样本数据
        
        Args:
            format: 导出格式 'dict' 或 'numpy'
        
        Returns:
            导出的数据
        """
        samples = self.get_samples(limit=10000)
        
        if format == 'numpy':
            try:
                import numpy as np
                vectors = [s.get('vector', []) for s in samples]
                labels = [s.get('label', 0) for s in samples]
                return {
                    'X': np.array(vectors),
                    'y': np.array(labels)
                }
            except ImportError:
                pass  # numpy 不可用，回退到 dict
        
        return {
            'samples': samples,
            'feature_names': FeatureExtractor.get_feature_names()
        }
    
    def import_preset_samples(self, samples: List[Dict]) -> int:
        """
        导入预置样本（仅管理员）
        
        Args:
            samples: 预置样本列表，每项包含 vector 和 label
        
        Returns:
            导入的样本数量
        """
        count = 0
        
        for sample in samples:
            sample_data = {
                'vector': sample.get('vector'),
                'label': sample.get('label'),
                'source': SOURCE_PRESET,
                'profile_version': sample.get('profile_version', DEFAULT_PROFILE_VERSION)
            }
            
            result = self.storage.add_bayes_sample(sample_data, owner_id=None)  # 系统预置
            if result:
                count += 1
        
        return count


# 单例管理
_sample_manager_cache: Dict[str, SampleManager] = {}


def get_sample_manager(user_id: str = None) -> SampleManager:
    """
    获取样本管理器实例
    
    Args:
        user_id: 用户ID，用于数据隔离
    
    Returns:
        SampleManager 实例
    """
    cache_key = user_id or '_system_'
    
    if cache_key not in _sample_manager_cache:
        _sample_manager_cache[cache_key] = SampleManager(user_id=user_id)
    
    return _sample_manager_cache[cache_key]


def clear_sample_manager_cache():
    """清空样本管理器缓存"""
    global _sample_manager_cache
    _sample_manager_cache = {}

