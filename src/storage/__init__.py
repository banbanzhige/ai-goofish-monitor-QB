"""
Storage Module - 数据访问层

提供统一的存储接口，支持本地文件存储和PostgreSQL数据库存储。
根据 STORAGE_BACKEND 环境变量自动选择存储后端。
"""

import os
from typing import TYPE_CHECKING

from sqlalchemy.engine.url import make_url

from src.config import get_env_value, STORAGE_BACKEND, normalize_database_url
from src.logging_config import get_logger

if TYPE_CHECKING:
    from .interface import StorageInterface

_storage_instance = None
logger = get_logger(__name__, service="system")


def _validate_database_url(database_url: str) -> str:
    """校验并规范化数据库连接地址，避免常见输入错误"""
    if not database_url:
        return ""
    
    normalized = normalize_database_url(database_url)
    if normalized != database_url:
        logger.warning(
            "检测到 DATABASE_URL 包含 http(s) 前缀，已自动修正",
            extra={"event": "database_url_normalized"}
        )
    
    try:
        make_url(normalized)
    except Exception as e:
        logger.error(
            "DATABASE_URL 格式错误",
            extra={"event": "database_url_invalid"},
            exc_info=e
        )
        raise ValueError(
            "DATABASE_URL 格式错误，请检查是否在主机中包含 http:// 或 https://，"
            "正确格式: postgresql://user:pass@host:port/dbname"
        ) from e
    
    return normalized


def get_storage() -> "StorageInterface":
    """
    获取存储实例（单例模式）
    
    根据 STORAGE_BACKEND 环境变量返回对应的存储适配器：
    - 'local': 本地文件存储（默认）
    - 'postgres': PostgreSQL 数据库存储
    
    Returns:
        StorageInterface: 存储接口实例
    """
    global _storage_instance
    
    if _storage_instance is not None:
        return _storage_instance
    
    backend = STORAGE_BACKEND()
    
    if backend == 'postgres':
        from .postgres_adapter import PostgresAdapter
        raw_database_url = get_env_value("DATABASE_URL", "")
        database_url = _validate_database_url(raw_database_url)
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required for postgres backend")
        _storage_instance = PostgresAdapter(database_url)
        try:
            _storage_instance.create_tables()
            logger.info(
                "PostgreSQL schema ensure completed",
                extra={"event": "postgres_schema_ensure_done"}
            )
        except Exception as e:
            logger.error(
                "PostgreSQL schema ensure failed",
                extra={"event": "postgres_schema_ensure_failed"},
                exc_info=e
            )
            raise
    else:
        from .local_adapter import LocalStorageAdapter
        _storage_instance = LocalStorageAdapter()
    
    return _storage_instance


def reset_storage():
    """重置存储实例（用于测试）"""
    global _storage_instance
    _storage_instance = None


__all__ = ['get_storage', 'reset_storage']
