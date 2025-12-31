@echo off
:: 设置UTF-8编码
chcp 65001 >nul
:: 启用变量延迟扩展
setlocal enabledelayedexpansion

:: 定义颜色常量
set "RED=[91m"
set "GREEN=[92m"
set "RESET=[0m"

:: 读取.env文件中的端口配置
set "SERVER_PORT=8000"
if exist ".env" (
    for /f "usebackq tokens=2 delims==" %%a in (`findstr /i "SERVER_PORT" ".env"`) do set "SERVER_PORT=%%a"
    :: 去除端口值周围的空格
    for /f "tokens=*" %%a in ("!SERVER_PORT!") do set "SERVER_PORT=%%a"
)

echo ==========================
echo  咸鱼鱼智能监控机器人启动脚本
echo ==========================
echo.

:: 检查Python是否安装
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo !RED![异常] Python未安装，请先安装Python 3.8或更高版本！!RESET!
    pause
    exit /b 1
)

:: 获取Python版本
for /f "tokens=2" %%i in ('python --version 2^>nul') do set "PYTHON_VERSION=%%i"
if not defined PYTHON_VERSION (  
    echo !RED![异常] 无法获取Python版本信息！!RESET!
    pause
    exit /b 1
) 
echo 当前Python版本: !PYTHON_VERSION!

:: 简化的Python版本检查
for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
    set "PYTHON_MAJOR=%%a"
    set "PYTHON_MINOR=%%b"
)

if !PYTHON_MAJOR! lss 3 (  
    echo !RED![异常] Python版本需要3.8或更高！!RESET!
    pause
    exit /b 1
)
if !PYTHON_MAJOR! equ 3 if !PYTHON_MINOR! lss 8 (  
    echo !RED![异常] Python版本需要3.8或更高！!RESET!
    pause
    exit /b 1
)
  
echo Python版本检查通过 (3.8+)
echo.

:: 创建虚拟环境（如果不存在）
if not exist "venv" (  
    echo 正在创建虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (  
        echo !RED![异常] 创建虚拟环境失败！!RESET!
        pause
        exit /b 1
    )  
    echo 虚拟环境创建成功
)

:: 激活虚拟环境   
echo 正在激活虚拟环境...
call "venv\Scripts\activate.bat"
if %errorlevel% neq 0 (  
    echo !RED![异常] 激活虚拟环境失败！!RESET!
    pause
    exit /b 1
)  
echo 虚拟环境已激活
echo.
 
:: 更新pip  
echo 正在检查pip版本...
python -m pip install --upgrade pip >nul 2>&1  
echo pip已更新到最新版本
echo.

:: 安装依赖 - 添加网络重试和镜像源备用机制，并隐藏已安装提示  
echo 正在安装项目依赖...
set "RETRY_COUNT=3"
set "CURRENT_RETRY=0"
set "INSTALL_SUCCESS=0"

:install_retry
if !CURRENT_RETRY! gtr 0 ( 
    echo 第 !CURRENT_RETRY! 次重试...
)

:: 尝试用默认源安装，隐藏已安装提示
pip install -r requirements.txt >nul 2>&1
if !errorlevel! equ 0 (
    set "INSTALL_SUCCESS=1"
    goto install_success
)

set /a CURRENT_RETRY+=1
if !CURRENT_RETRY! leq !RETRY_COUNT! ( 
    echo 安装失败，正在重试...
    timeout /t 3 /nobreak >nul
    goto install_retry
)

:: 默认源多次重试失败，尝试用清华大学镜像源 
echo 默认源安装失败，尝试使用清华大学镜像源... 
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ >nul 2>&1
if !errorlevel! equ 0 (
    set "INSTALL_SUCCESS=1"
    goto install_success
)

:: 清华大学镜像源也失败，尝试用阿里云镜像源 
echo 清华大学镜像源安装失败，尝试使用阿里云镜像源... 
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ >nul 2>&1
if !errorlevel! equ 0 (
    set "INSTALL_SUCCESS=1"
    goto install_success
)

:: 所有镜像源都失败 
echo !RED![异常] 所有镜像源安装依赖均失败！!RESET! 
echo 请检查网络连接，或尝试手动安装依赖： 
echo pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
pause
exit /b 1

:install_success
echo 所有依赖安装完成 
echo.

:: 检查登录状态文件 
if not exist "xianyu_state.json" (  
    echo !RED![异常] 登录状态文件cookie文件：xianyu_state.json 不存在！!RESET!  
    echo 需要登录咸鱼才能正常爬取数据，需要在管理界面获取cookie文件！
    echo.
)

:: 检测本地IP地址
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=*" %%b in ("%%a") do set "LOCAL_IP=%%b"
    goto :found_ip
)
:found_ip

:: 端口可用性检测
echo 正在检测端口!SERVER_PORT!是否可用...
netstat -an | findstr /i "LISTENING" | findstr /C:":!SERVER_PORT! " >nul 2>&1
if !errorlevel! equ 0 (
    echo !RED![异常] 端口!SERVER_PORT!已被占用，请检查是否有其他服务正在使用该端口！!RESET!
    echo 建议修改.env文件中的SERVER_PORT配置
    pause
    exit /b 1
)
echo 端口!SERVER_PORT!可用
echo.

echo 正在启动Web管理界面...  
echo 请在浏览器访问web管理界面:
echo - 本地访问地址: !GREEN!http://127.0.0.1:!SERVER_PORT!!RESET!
if defined LOCAL_IP (
    echo - 局域网访问地址:!GREEN!http://!LOCAL_IP!:!SERVER_PORT!!RESET!
)
echo 按下 Ctrl+C 可停止服务 
echo.

:: 启动Web服务器
python -u web_server.py

pause
