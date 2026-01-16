import os
import aiofiles
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse


router = APIRouter()


@router.get("/api/logs")
async def get_logs(from_pos: int = 0, task_name: str = None):
    """获取爬虫日志文件的内容。支持从指定位置增量读取和任务名称筛选。"""
    log_file_path = os.path.join("logs", "fetcher.log")
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

        if task_name and task_name.strip():
            filtered_lines = []
            for line in new_content.split('\n'):
                if line:
                    if task_name == '系统':
                        if '[系统]' in line:
                            filtered_lines.append(line)
                    else:
                        if task_name in line or task_name.lower() in line.lower():
                            filtered_lines.append(line)
            new_content = '\n'.join(filtered_lines)

        return {"new_content": new_content, "new_pos": file_size}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"new_content": f"\n读取日志文件时出错: {e}", "new_pos": from_pos}
        )


@router.delete("/api/logs")
async def clear_logs():
    """清空日志文件内容。"""
    log_file_path = os.path.join("logs", "fetcher.log")
    if not os.path.exists(log_file_path):
        return {"message": "日志文件不存在，无需清空。"}

    try:
        async with aiofiles.open(log_file_path, 'w', encoding='utf-8') as f:
            await f.write("")
        return {"message": "日志已成功清空。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空日志文件时出错: {e}")
