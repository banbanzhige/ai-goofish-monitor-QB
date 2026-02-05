"""
日志导出模块

提供日志导出功能：
- 生成日志包（ZIP格式）
- 支持按时间范围或大小限制导出
"""

import os
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.logging_config import get_logger

# 获取logger
logger = get_logger(__name__, service="system")


def export_logs_package(
    output_dir: str = "logs/exports",
    log_dir: str = "logs",
    days: int = 7,
    max_size_mb: int = 50
) -> Optional[str]:
    """
    导出日志包
    
    Args:
        output_dir: 导出目录
        log_dir: 日志目录
        days: 包含最近N天的日志
        max_size_mb: 最大导出大小（MB）
    
    Returns:
        生成的ZIP文件路径，失败返回None
    """
    try:
        # 创建导出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"logs_export_{timestamp}.zip"
        zip_path = os.path.join(output_dir, zip_filename)
        
        cutoff_time = datetime.now() - timedelta(days=days)
        total_size = 0
        max_size_bytes = max_size_mb * 1024 * 1024
        file_count = 0
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 添加日志文件
            log_path = Path(log_dir)
            if log_path.exists():
                for log_file in log_path.rglob("*.log*"):
                    # 跳过 exports 目录
                    if "exports" in log_file.parts:
                        continue
                    
                    if log_file.is_file():
                        # 检查文件修改时间
                        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if mtime < cutoff_time:
                            continue
                        
                        # 检查大小限制
                        file_size = log_file.stat().st_size
                        if total_size + file_size > max_size_bytes:
                            logger.warning(
                                f"导出大小超限，跳过文件: {log_file.name}",
                                extra={"event": "export_size_limit", "file": log_file.name}
                            )
                            continue
                        
                        # 添加到ZIP
                        try:
                            arcname = f"logs/{log_file.relative_to(log_path)}"
                            zf.write(log_file, arcname)
                            total_size += file_size
                            file_count += 1
                        except Exception as e:
                            logger.error(f"读取日志文件失败: {log_file}, {e}")
        
        logger.info(
            f"日志导出成功: {zip_filename}",
            extra={"event": "export_complete", "file": zip_filename, "size_bytes": os.path.getsize(zip_path), "file_count": file_count}
        )
        return zip_path
        
    except Exception as e:
        logger.error(f"导出日志失败: {e}", extra={"event": "export_error"})
        return None


def cleanup_old_exports(export_dir: str = "logs/exports", keep_count: int = 5) -> int:
    """
    清理旧的导出文件，只保留最新的N个
    
    Args:
        export_dir: 导出目录
        keep_count: 保留的文件数量
        
    Returns:
        删除的文件数量
    """
    try:
        export_path = Path(export_dir)
        if not export_path.exists():
            return 0
        
        # 获取所有ZIP文件，按修改时间排序
        zip_files = sorted(
            export_path.glob("logs_export_*.zip"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # 删除多余的文件
        deleted = 0
        for old_file in zip_files[keep_count:]:
            try:
                old_file.unlink()
                deleted += 1
                logger.info(f"已删除旧导出文件: {old_file.name}", extra={"event": "export_cleanup"})
            except Exception as e:
                logger.error(f"删除文件失败: {old_file}, {e}")
        
        return deleted
        
    except Exception as e:
        logger.error(f"清理导出文件失败: {e}", extra={"event": "export_cleanup_error"})
        return 0
