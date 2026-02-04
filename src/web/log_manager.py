import os
import json
import re
import aiofiles
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from src.logging_config import get_logger

# 获取logger
logger = get_logger(__name__, service="web")

# ANSI 转义序列匹配（用于清理控制台颜色码）
_ANSI_ESCAPE_RE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

# 日志目录配置
LOG_DIR = os.path.join("logs")
LEGACY_LOG_FILE = os.path.join(LOG_DIR, "fetcher.log")
SYSTEM_LOG_FILE = os.path.join(LOG_DIR, "system.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")
TASKS_LOG_DIR = os.path.join(LOG_DIR, "tasks")


def sys_log(message: str, level: str = "INFO"):
    """
    兼容性封装：使用新日志系统记录系统日志
    保留此函数以兼容可能的外部调用
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, extra={"event": "sys_log"})


def _strip_ansi(text: str) -> str:
    """移除日志中的ANSI颜色码，避免Web端出现乱码样式"""
    if not text:
        return text
    return _ANSI_ESCAPE_RE.sub('', text)


router = APIRouter()


@router.get("/api/logs")
async def get_logs(
    from_pos: int = 0,
    task_name: str = None,
    limit: int = 100,
    file: str = Query("fetcher", description="日志文件: fetcher/system/error"),
    level: str = Query(None, description="日志等级筛选: DEBUG/INFO/WARNING/ERROR/CRITICAL")
):
    """
    获取日志文件内容。
    支持从指定位置增量读取、任务名称筛选、等级筛选。
    
    Args:
        from_pos: 起始位置（用于增量读取）
        task_name: 任务名称筛选
        limit: 返回行数限制，默认100
        file: 日志文件类型 (fetcher/system/error)
        level: 日志等级筛选
    """
    # 选择日志文件
    if file == "system":
        log_file_path = SYSTEM_LOG_FILE
    elif file == "error":
        log_file_path = ERROR_LOG_FILE
    else:
        log_file_path = LEGACY_LOG_FILE
    
    if not os.path.exists(log_file_path):
        return JSONResponse(content={"new_content": "日志文件不存在或尚未创建。", "new_pos": 0})

    try:
        async with aiofiles.open(log_file_path, 'rb') as f:
            await f.seek(0, os.SEEK_END)
            file_size = await f.tell()

            if from_pos >= file_size:
                return {"new_content": "", "new_pos": file_size}

            await f.seek(from_pos)
            new_bytes = await f.read()

        new_content = new_bytes.decode('utf-8', errors='replace')
        new_content = _strip_ansi(new_content)
        
        # 按行分割
        lines = [line for line in new_content.split('\n') if line.strip()]

        # 任务名称筛选
        if task_name and task_name.strip():
            filtered_lines = []
            for line in lines:
                if task_name == '系统':
                    if '[系统]' in line or '"service": "system"' in line or '"service": "web"' in line:
                        filtered_lines.append(line)
                else:
                    if task_name in line or task_name.lower() in line.lower():
                        filtered_lines.append(line)
            lines = filtered_lines
        
        # 等级筛选
        if level and level.strip():
            level_upper = level.upper()
            filtered_lines = []
            for line in lines:
                # 支持传统格式 [INFO] 和 JSON格式 "level": "INFO"
                if f'[{level_upper}]' in line or f'"level": "{level_upper}"' in line:
                    filtered_lines.append(line)
            lines = filtered_lines
        
        # 限制返回的行数，保留最新的N条
        if limit > 0 and len(lines) > limit:
            lines = lines[-limit:]
        
        new_content = '\n'.join(lines)

        return {"new_content": new_content, "new_pos": file_size}

    except Exception as e:
        logger.error(f"读取日志文件时出错: {e}", extra={"event": "log_read_error", "file": file})
        return JSONResponse(
            status_code=500,
            content={"new_content": f"\n读取日志文件时出错: {e}", "new_pos": from_pos}
        )


@router.get("/api/logs/files")
async def list_log_files():
    """列出所有可用的日志文件"""
    files = []
    
    # 检查主日志文件
    for name, path in [
        ("fetcher", LEGACY_LOG_FILE),
        ("system", SYSTEM_LOG_FILE),
        ("error", ERROR_LOG_FILE)
    ]:
        if os.path.exists(path):
            stat = os.stat(path)
            files.append({
                "name": name,
                "path": path,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    # 检查任务日志
    if os.path.exists(TASKS_LOG_DIR):
        for task_file in Path(TASKS_LOG_DIR).glob("task_*.log"):
            stat = task_file.stat()
            files.append({
                "name": task_file.stem,
                "path": str(task_file),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    return {"files": files}


@router.get("/api/logs/tasks/{task_id}")
async def get_task_logs(task_id: int, limit: int = 100):
    """获取特定任务的日志"""
    task_log_path = os.path.join(TASKS_LOG_DIR, f"task_{task_id}.log")
    
    if not os.path.exists(task_log_path):
        return JSONResponse(
            status_code=404,
            content={"message": f"任务 {task_id} 的日志文件不存在"}
        )
    
    try:
        async with aiofiles.open(task_log_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        lines = [line for line in content.split('\n') if line.strip()]
        
        if limit > 0 and len(lines) > limit:
            lines = lines[-limit:]
        
        return {"task_id": task_id, "content": '\n'.join(lines), "line_count": len(lines)}
    
    except Exception as e:
        logger.error(f"读取任务日志时出错: {e}", extra={"event": "task_log_read_error", "task_id": task_id})
        raise HTTPException(status_code=500, detail=f"读取任务日志时出错: {e}")


@router.post("/api/logs/cleanup")
async def cleanup_logs(retention_days: int = Query(7, description="保留天数")):
    """
    清理过期日志文件
    
    删除超过指定天数的日志文件和轮转备份
    """
    from src.logging_config import cleanup_old_logs
    
    try:
        cleanup_old_logs(retention_days=retention_days)
        logger.info(f"已清理 {retention_days} 天前的日志", extra={"event": "log_cleanup_api", "retention_days": retention_days})
        return {"message": f"已清理 {retention_days} 天前的日志文件"}
    except Exception as e:
        logger.error(f"清理日志时出错: {e}", extra={"event": "log_cleanup_error"})
        raise HTTPException(status_code=500, detail=f"清理日志时出错: {e}")


@router.delete("/api/logs")
async def clear_logs(file: str = Query("fetcher", description="要清空的日志文件")):
    """清空指定的日志文件内容。"""
    if file == "system":
        log_file_path = SYSTEM_LOG_FILE
    elif file == "error":
        log_file_path = ERROR_LOG_FILE
    else:
        log_file_path = LEGACY_LOG_FILE
    
    if not os.path.exists(log_file_path):
        return {"message": "日志文件不存在，无需清空。"}

    try:
        async with aiofiles.open(log_file_path, 'w', encoding='utf-8') as f:
            await f.write("")
        logger.info(f"已清空日志文件: {file}", extra={"event": "log_cleared", "file": file})
        return {"message": f"日志 {file} 已成功清空。"}
    except Exception as e:
        logger.error(f"清空日志文件时出错: {e}", extra={"event": "log_clear_error", "file": file})
        raise HTTPException(status_code=500, detail=f"清空日志文件时出错: {e}")


@router.delete("/api/logs/tasks/{task_id}")
async def clear_task_logs(task_id: int):
    """清空特定任务的日志文件"""
    task_log_path = os.path.join(TASKS_LOG_DIR, f"task_{task_id}.log")
    
    if not os.path.exists(task_log_path):
        return {"message": f"任务 {task_id} 的日志文件不存在"}
    
    try:
        async with aiofiles.open(task_log_path, 'w', encoding='utf-8') as f:
            await f.write("")
        logger.info(f"已清空任务日志: task_{task_id}", extra={"event": "task_log_cleared", "task_id": task_id})
        return {"message": f"任务 {task_id} 的日志已成功清空。"}
    except Exception as e:
        logger.error(f"清空任务日志时出错: {e}", extra={"event": "task_log_clear_error", "task_id": task_id})
        raise HTTPException(status_code=500, detail=f"清空任务日志时出错: {e}")


@router.post("/api/logs/export")
async def export_diagnostic_package(
    days: int = Query(7, description="包含最近N天的日志"),
    max_size_mb: int = Query(50, description="最大导出大小(MB)")
):
    """
    导出诊断日志包
    
    生成一个包含以下内容的ZIP文件：
    - 系统信息
    - 近N天的日志文件
    - 脱敏后的config.json
    - 脱敏后的.env
    - 版本信息
    """
    from src.log_exporter import export_logs_package, cleanup_old_exports
    from fastapi.responses import FileResponse
    
    try:
        # 导出日志包
        zip_path = export_logs_package(
            days=days,
            max_size_mb=max_size_mb
        )
        
        if not zip_path or not os.path.exists(zip_path):
            raise HTTPException(status_code=500, detail="导出诊断包失败")
        
        # 清理旧的导出文件
        cleanup_old_exports(keep_count=5)
        
        # 返回文件下载
        filename = os.path.basename(zip_path)
        return FileResponse(
            path=zip_path,
            filename=filename,
            media_type="application/zip"
        )
        
    except Exception as e:
        logger.error(f"导出诊断包时出错: {e}", extra={"event": "export_api_error"})
        raise HTTPException(status_code=500, detail=f"导出诊断包时出错: {e}")


@router.get("/api/logs/exports")
async def list_exports():
    """列出已导出的诊断包"""
    export_dir = os.path.join(LOG_DIR, "exports")
    
    if not os.path.exists(export_dir):
        return {"exports": []}
    
    exports = []
    for f in Path(export_dir).glob("diagnostic_report_*.zip"):
        stat = f.stat()
        exports.append({
            "filename": f.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    # 按创建时间倒序排列
    exports.sort(key=lambda x: x["created"], reverse=True)
    
    return {"exports": exports}


@router.get("/api/logs/exports/{filename}")
async def download_export(filename: str):
    """下载指定的导出文件"""
    from fastapi.responses import FileResponse
    
    # 安全检查：确保文件名格式正确
    if not filename.startswith("diagnostic_report_") or not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="无效的文件名")
    
    export_path = os.path.join(LOG_DIR, "exports", filename)
    
    if not os.path.exists(export_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        path=export_path,
        filename=filename,
        media_type="application/zip"
    )


@router.delete("/api/logs/exports/{filename}")
async def delete_export(filename: str):
    """删除指定的导出文件"""
    # 安全检查
    if not filename.startswith("diagnostic_report_") or not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="无效的文件名")
    
    export_path = os.path.join(LOG_DIR, "exports", filename)
    
    if not os.path.exists(export_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        os.remove(export_path)
        logger.info(f"已删除导出文件: {filename}", extra={"event": "export_deleted", "filename": filename})
        return {"message": f"已删除: {filename}"}
    except Exception as e:
        logger.error(f"删除导出文件时出错: {e}", extra={"event": "export_delete_error"})
        raise HTTPException(status_code=500, detail=f"删除文件时出错: {e}")

