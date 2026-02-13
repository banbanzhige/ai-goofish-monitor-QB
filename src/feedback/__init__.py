"""
反馈闭环系统 - 初始化模块

提供用户反馈处理、特征提取和样本管理功能。
"""
from .feature_extractor import FeatureExtractor, extract_features
from .sample_manager import SampleManager, get_sample_manager

__all__ = [
    'FeatureExtractor',
    'extract_features',
    'SampleManager',
    'get_sample_manager'
]
