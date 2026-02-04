"""
日志格式化器模块

提供多种日志格式化器：
- JSONLinesFormatter: 结构化JSON格式（文件存储）
- ColoredConsoleFormatter: 彩色易读格式（控制台输出）
- StructuredFilter: 添加上下文字段
"""

import json
import logging
import sys
from datetime import datetime
from typing import Optional


class JSONLinesFormatter(logging.Formatter):
    """JSON Lines 格式化器，用于文件存储"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON Lines格式"""
        log_data = {
            "ts": datetime.fromtimestamp(record.created).astimezone().isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        
        # 添加可选的结构化字段
        if hasattr(record, 'service'):
            log_data['service'] = record.service
        if hasattr(record, 'event'):
            log_data['event'] = record.event
        if hasattr(record, 'task_id'):
            log_data['task_id'] = record.task_id
        if hasattr(record, 'task_name'):
            log_data['task_name'] = record.task_name
        if hasattr(record, 'account'):
            log_data['account'] = record.account
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'processed_count'):
            log_data['processed_count'] = record.processed_count
        
        # 添加异常信息
        if record.exc_info:
            log_data['error'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """彩色控制台格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[1;31m', # 粗体红色
        'RESET': '\033[0m'        # 重置
    }
    
    def _should_use_color(self) -> bool:
        """仅在终端环境启用颜色，避免输出到文件时带ANSI码"""
        try:
            return sys.stderr.isatty() or sys.stdout.isatty()
        except Exception:
            return False

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为彩色控制台格式"""
        # 获取颜色（非终端时关闭颜色，避免污染文件日志）
        if self._should_use_color():
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
        else:
            color = ''
            reset = ''
        
        # 格式化时间
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建基础消息
        parts = [f"[{timestamp}]"]
        
        # 添加服务/任务信息
        if hasattr(record, 'task_name'):
            parts.append(f"[{record.task_name}]")
        elif hasattr(record, 'service'):
            parts.append(f"[{record.service}]")
        else:
            parts.append("[系统]")
        
        # 添加彩色等级
        parts.append(f"[{color}{record.levelname}{reset}]")
        
        # 添加消息
        parts.append(record.getMessage())
        
        message = " ".join(parts)
        
        # 添加异常信息
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return message


class StructuredFilter(logging.Filter):
    """为日志记录添加结构化上下文字段"""
    
    def __init__(
        self,
        service: Optional[str] = None,
        task_id: Optional[int] = None,
        task_name: Optional[str] = None
    ):
        super().__init__()
        self.service = service
        self.task_id = task_id
        self.task_name = task_name
    
    def filter(self, record: logging.LogRecord) -> bool:
        """添加上下文字段到日志记录"""
        if self.service and not hasattr(record, 'service'):
            record.service = self.service
        if self.task_id and not hasattr(record, 'task_id'):
            record.task_id = self.task_id
        if self.task_name and not hasattr(record, 'task_name'):
            record.task_name = self.task_name
        return True
