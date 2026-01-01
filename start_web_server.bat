@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "RESET=[0m"

set "SERVER_PORT=8000"
if exist ".env" (
    for /f "usebackq tokens=2 delims==" %%a in (`findstr /i "SERVER_PORT" ".env"`) do set "SERVER_PORT=%%a"
    for /f "tokens=*" %%a in ("!SERVER_PORT!") do set "SERVER_PORT=%%a"
)

rem 获取版本号
for /f "delims=" %%v in ('python -c "from src.version import VERSION; print(VERSION)"') do set "APP_VERSION=%%v"

echo !YELLOW!======================================!RESET!
echo  !YELLOW!咸鱼智能监控机器人启动脚本 %APP_VERSION%!RESET!
echo !YELLOW!======================================!RESET!
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo !RED![错误] 未安装Python，请先安装Python 3.8或更高版本!RESET!
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>nul') do set "PYTHON_VERSION=%%i"
if not defined PYTHON_VERSION (  
    echo !RED![错误] 无法获取Python版本信息!RESET!
    pause
    exit /b 1
) 
echo 当前Python版本: !PYTHON_VERSION!

for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
    set "PYTHON_MAJOR=%%a"
    set "PYTHON_MINOR=%%b"
)

if !PYTHON_MAJOR! lss 3 (  
    echo !RED![错误] Python版本需要3.8或更高!RESET!
    pause
    exit /b 1
)
if !PYTHON_MAJOR! equ 3 if !PYTHON_MINOR! lss 8 (  
    echo !RED![错误] Python版本需要3.8或更高!RESET!
    pause
    exit /b 1
)
   
echo Python版本检查通过 (3.8+)
echo.

if not exist "venv" (  
    echo 正在创建虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (  
        echo !RED![错误] 创建虚拟环境失败!RESET!
        pause
        exit /b 1
    )  
    echo 虚拟环境创建成功
)

echo 正在激活虚拟环境...
call "venv\Scripts\activate.bat"
if %errorlevel% neq 0 (  
    echo !RED![错误] 激活虚拟环境失败!RESET!
    pause
    exit /b 1
)  
echo 虚拟环境已激活
echo.
 
echo 正在检查pip版本...
python -m pip install --upgrade pip >nul 2>&1  
echo pip已更新到最新版本
echo.

echo 正在安装依赖库...
set "RETRY_COUNT=3"
set "CURRENT_RETRY=0"
set "INSTALL_SUCCESS=0"

:install_retry
if !CURRENT_RETRY! gtr 0 ( 
    echo 第 !CURRENT_RETRY! 次重试...
)

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

echo 尝试国内镜像源... 
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ >nul 2>&1
if !errorlevel! equ 0 (
    set "INSTALL_SUCCESS=1"
    goto install_success
)

echo 清华大学镜像源安装失败，尝试阿里云镜像源... 
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ >nul 2>&1
if !errorlevel! equ 0 (
    set "INSTALL_SUCCESS=1"
    goto install_success
)

echo !RED![错误] 所有镜像源安装依赖均失败!RESET! 
echo 请检查网络环境，或手动安装依赖: 
echo pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
pause
exit /b 1

:install_success
echo 所有依赖安装完成 
echo.

if not exist "xianyu_state.json" (  
    echo !RED![错误] 缺少闲鱼状态配置文件:xianyu_state.json!RESET!  
    echo 需要登录闲鱼之后才能获取数据，需要在管理界面获取cookie文件!
    echo.
)

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=*" %%b in ("%%a") do set "LOCAL_IP=%%b"
    goto :found_ip
)
:found_ip

echo 正在检查端口!SERVER_PORT!是否可用...
netstat -an | findstr /i "LISTENING" | findstr /C:":!SERVER_PORT! " >nul 2>&1
if !errorlevel! equ 0 (
    echo !RED![错误] 端口!SERVER_PORT!已被占用，请检查是否有其他服务正在使用此端口!RESET!
    echo 或修改.env文件中的SERVER_PORT配置
    pause
    exit /b 1
) 
echo 端口!SERVER_PORT!可用
echo.

echo !YELLOW!正在启动Web管理界面...  !RESET!
echo !YELLOW!请在浏览器访问web管理界面:!RESET!
echo - 本地访问地址: !GREEN!http://127.0.0.1:!SERVER_PORT!!RESET!
if defined LOCAL_IP (
    echo - 局域网访问地址:!GREEN!http://!LOCAL_IP!:!SERVER_PORT!!RESET!
)
echo 按下 Ctrl+C 停止服务 
echo.

python -u web_server.py

pause
