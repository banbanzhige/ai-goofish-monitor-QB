"""
咸鱼公开内容查看智能处理程序 - Web服务器入口文件

此文件是重构后的项目入口文件，保持与原文件相同的接口，
所有功能已拆分为多个模块，提高了代码的可读性和可维护性。
"""

from src.web.main import app, fetcher_processes, login_process, scheduler

if __name__ == "__main__":
    from src.web.main import app as main_app
    import uvicorn
    from dotenv import dotenv_values
    import os

    config = dotenv_values(".env")
    server_port = int(config.get("SERVER_PORT", 8000))
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    print(f"启动 Web 管理界面，请在浏览器访问 http://127.0.0.1:{server_port}")
    import sys
    sys.stdout.flush()
    uvicorn.run(main_app, host="0.0.0.0", port=server_port, log_level="warning")
