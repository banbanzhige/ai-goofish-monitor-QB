import os
import aiofiles
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse


LOG_FILE = os.path.join("logs", "fetcher.log")


def sys_log(message: str, level: str = "INFO"):
    """
    同步记录系统日志到fetcher.log和控制台
    格式: [时间] [系统] [级别] 消息
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [系统] [{level}] {message}"
    
    # 输出到控制台
    print(log_line)
    
    # 追加到日志文件
    try:
        os.makedirs("logs", exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")
    except Exception as e:
        print(f"写入日志文件失败: {e}")


router = APIRouter()


@router.get("/api/logs")
async def get_logs(from_pos: int = 0, task_name: str = None, limit: int = 100):
    """获取爬虫日志文件的内容。支持从指定位置增量读取和任务名称筛选。默认限制100条。"""
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
        
        # 按行分割
        lines = [line for line in new_content.split('\n') if line.strip()]

        if task_name and task_name.strip():
            filtered_lines = []
            for line in lines:
                if task_name == '系统':
                    if '[系统]' in line:
                        filtered_lines.append(line)
                else:
                    if task_name in line or task_name.lower() in line.lower():
                        filtered_lines.append(line)
            lines = filtered_lines
        
        # 限制返回的行数，保留最新的N条
        if limit > 0 and len(lines) > limit:
            lines = lines[-limit:]
        
        new_content = '\n'.join(lines)

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
