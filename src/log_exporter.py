"""
日志导出模块

提供日志导出和脱敏功能：
- 生成问题诊断包（ZIP格式）
- 自动脱敏敏感信息（API_KEY、Cookie、Token等）
- 收集系统信息（OS、Python版本、配置摘要）
- 支持按时间范围或大小限制导出
"""

import os
import re
import json
import zipfile
import platform
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from src.logging_config import get_logger
from src.version import VERSION

# 获取logger
logger = get_logger(__name__, service="system")

# 需要脱敏的敏感字段模式
SENSITIVE_PATTERNS = [
    # API Keys
    (r'(OPENAI_API_KEY\s*=\s*)[^\s\n]+', r'\1***MASKED***'),
    (r'(api_key\s*[=:]\s*)["\']?[^"\'\s\n]+["\']?', r'\1"***MASKED***"'),
    (r'("api_key"\s*:\s*")[^"]+(")', r'\1***MASKED***\2'),
    
    # Tokens
    (r'(token\s*[=:]\s*)["\']?[^"\'\s\n]+["\']?', r'\1"***MASKED***"', re.IGNORECASE),
    (r'("token"\s*:\s*")[^"]+(")', r'\1***MASKED***\2'),
    (r'(TELEGRAM_BOT_TOKEN\s*=\s*)[^\s\n]+', r'\1***MASKED***'),
    (r'(GOTIFY_TOKEN\s*=\s*)[^\s\n]+', r'\1***MASKED***'),
    
    # Secrets
    (r'(secret\s*[=:]\s*)["\']?[^"\'\s\n]+["\']?', r'\1"***MASKED***"', re.IGNORECASE),
    (r'("secret"\s*:\s*")[^"]+(")', r'\1***MASKED***\2'),
    (r'(WX_SECRET\s*=\s*)[^\s\n]+', r'\1***MASKED***'),
    (r'(DINGTALK_SECRET\s*=\s*)[^\s\n]+', r'\1***MASKED***'),
    
    # Passwords
    (r'(password\s*[=:]\s*)["\']?[^"\'\s\n]+["\']?', r'\1"***MASKED***"', re.IGNORECASE),
    (r'("password"\s*:\s*")[^"]+(")', r'\1***MASKED***\2'),
    (r'(WEB_PASSWORD\s*=\s*)[^\s\n]+', r'\1***MASKED***'),
    
    # Webhook URLs (可能包含密钥)
    (r'(WEBHOOK_URL\s*=\s*)[^\s\n]+', r'\1***MASKED_URL***'),
    (r'(DINGTALK_WEBHOOK\s*=\s*)[^\s\n]+', r'\1***MASKED_URL***'),
    (r'(NTFY_TOPIC_URL\s*=\s*)[^\s\n]+', r'\1***MASKED_URL***'),
    (r'(BARK_URL\s*=\s*)[^\s\n]+', r'\1***MASKED_URL***'),
    
    # Cookies
    (r'(cookie\s*[=:]\s*)["\']?[^"\'\s\n]{20,}["\']?', r'\1"***MASKED_COOKIE***"', re.IGNORECASE),
]


def mask_sensitive_data(content: str) -> str:
    """
    对内容进行脱敏处理
    
    Args:
        content: 原始内容
        
    Returns:
        脱敏后的内容
    """
    masked = content
    for pattern_tuple in SENSITIVE_PATTERNS:
        if len(pattern_tuple) == 3:
            pattern, replacement, flags = pattern_tuple
            masked = re.sub(pattern, replacement, masked, flags=flags)
        else:
            pattern, replacement = pattern_tuple
            masked = re.sub(pattern, replacement, masked)
    return masked


def get_system_info() -> dict:
    """
    收集系统信息
    
    Returns:
        系统信息字典
    """
    return {
        "export_time": datetime.now().isoformat(),
        "app_version": VERSION,
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
    }


def export_logs_package(
    output_dir: str = "logs/exports",
    log_dir: str = "logs",
    days: int = 7,
    max_size_mb: int = 50,
    include_config: bool = True,
    include_env: bool = True
) -> Optional[str]:
    """
    导出日志诊断包
    
    Args:
        output_dir: 导出目录
        log_dir: 日志目录
        days: 包含最近N天的日志
        max_size_mb: 最大导出大小（MB）
        include_config: 是否包含config.json（脱敏）
        include_env: 是否包含.env（脱敏）
    
    Returns:
        生成的ZIP文件路径，失败返回None
    """
    try:
        # 创建导出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"diagnostic_report_{timestamp}.zip"
        zip_path = os.path.join(output_dir, zip_filename)
        
        cutoff_time = datetime.now() - timedelta(days=days)
        total_size = 0
        max_size_bytes = max_size_mb * 1024 * 1024
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. 添加系统信息
            system_info = get_system_info()
            zf.writestr("system_info.json", json.dumps(system_info, ensure_ascii=False, indent=2))
            
            # 2. 添加日志文件
            log_path = Path(log_dir)
            if log_path.exists():
                for log_file in log_path.rglob("*.log*"):
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
                        
                        # 读取并添加到ZIP
                        try:
                            content = log_file.read_text(encoding='utf-8', errors='replace')
                            # 对日志内容也进行脱敏
                            masked_content = mask_sensitive_data(content)
                            arcname = f"logs/{log_file.relative_to(log_path)}"
                            zf.writestr(arcname, masked_content)
                            total_size += file_size
                        except Exception as e:
                            logger.error(f"读取日志文件失败: {log_file}, {e}")
            
            # 3. 添加脱敏配置文件
            if include_config and os.path.exists("config.json"):
                try:
                    with open("config.json", 'r', encoding='utf-8') as f:
                        config_content = f.read()
                    masked_config = mask_sensitive_data(config_content)
                    zf.writestr("config.json", masked_config)
                except Exception as e:
                    logger.error(f"读取config.json失败: {e}")
            
            # 4. 添加脱敏环境变量
            if include_env and os.path.exists(".env"):
                try:
                    with open(".env", 'r', encoding='utf-8') as f:
                        env_content = f.read()
                    masked_env = mask_sensitive_data(env_content)
                    zf.writestr(".env.masked", masked_env)
                except Exception as e:
                    logger.error(f"读取.env失败: {e}")
            
            # 5. 添加版本信息
            if os.path.exists("src/version.py"):
                try:
                    with open("src/version.py", 'r', encoding='utf-8') as f:
                        version_content = f.read()
                    zf.writestr("version.py", version_content)
                except Exception as e:
                    logger.error(f"读取version.py失败: {e}")
        
        logger.info(
            f"诊断包导出成功: {zip_filename}",
            extra={"event": "export_complete", "file": zip_filename, "size_bytes": os.path.getsize(zip_path)}
        )
        return zip_path
        
    except Exception as e:
        logger.error(f"导出诊断包失败: {e}", extra={"event": "export_error"})
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
            export_path.glob("diagnostic_report_*.zip"),
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
