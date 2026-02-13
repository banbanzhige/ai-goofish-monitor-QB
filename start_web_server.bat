@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem =====================================
rem   咸鱼智能监控机器人 启动脚本
rem =====================================

for /f "delims=" %%v in ('python -c "from src.version import VERSION; print(VERSION)" 2^>nul') do set "APP_VERSION=%%v"
if not defined APP_VERSION set "APP_VERSION=V1.0.0"

echo.
echo =====================================
echo   咸鱼智能监控机器人 %APP_VERSION%
echo =====================================
echo.

rem 读取当前存储后端配置
set "CURRENT_STORAGE_BACKEND=local"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if /i "%%a"=="STORAGE_BACKEND" set "CURRENT_STORAGE_BACKEND=%%b"
    )
)

if /i "!CURRENT_STORAGE_BACKEND!"=="postgres" (
    set "DEFAULT_CHOICE=2"
) else (
    set "DEFAULT_CHOICE=1"
)

echo 请选择运行模式:
echo.
echo   [1] 本地模式 (单用户, 文件存储)
echo   [2] 数据库模式 (多用户, PostgreSQL)
echo.
echo =====================================
echo.

set /p "MODE_CHOICE=请输入选择 [1/2] (默认!DEFAULT_CHOICE!): "

if "%MODE_CHOICE%"=="" set "MODE_CHOICE=!DEFAULT_CHOICE!"
if not "%MODE_CHOICE%"=="1" if not "%MODE_CHOICE%"=="2" (
    echo [警告] 无效输入，已沿用当前配置。
    set "MODE_CHOICE=!DEFAULT_CHOICE!"
)

if "%MODE_CHOICE%"=="2" (
    set "STORAGE_BACKEND=postgres"
    echo.
    echo [已选择] 数据库模式 - 多用户
    echo.
    
    rem 检查 DATABASE_URL 配置
    set "DATABASE_URL="
    if exist ".env" (
        for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
            if /i "%%a"=="DATABASE_URL" set "DATABASE_URL=%%b"
        )
    )
    
    if "!DATABASE_URL!"=="" (
        echo [警告] 未配置 DATABASE_URL
        echo.
        echo 请在 .env 文件中配置以下内容:
        echo   DATABASE_URL=postgresql://用户名:密码@主机:5432/数据库名
        echo   ENCRYPTION_MASTER_KEY=你的加密密钥
        echo.
        pause
        exit /b 1
    )
    echo [状态] 数据库连接已配置
) else (
    set "STORAGE_BACKEND=local"
    echo.
    echo [已选择] 本地模式 - 单用户
)
echo.

rem 同步写入 .env 文件（纯 batch 实现）
call :sync_env_storage_backend
echo.

rem Python 版本检查
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未安装Python，请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>nul') do set "PYTHON_VERSION=%%i"
if not defined PYTHON_VERSION (
    echo [错误] 无法获取Python版本信息
    pause
    exit /b 1
)
echo 当前Python版本: %PYTHON_VERSION%

for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set "PYTHON_MAJOR=%%a"
    set "PYTHON_MINOR=%%b"
)

if %PYTHON_MAJOR% lss 3 (
    echo [错误] Python版本需要3.8或更高
    pause
    exit /b 1
)
if %PYTHON_MAJOR% equ 3 if %PYTHON_MINOR% lss 8 (
    echo [错误] Python版本需要3.8或更高
    pause
    exit /b 1
)

echo [通过] Python版本检查 ^(3.8+^)
echo.

rem .env 完整性检查（兼容旧启动流程）
if exist "check_env.py" (
    echo 正在执行 .env 完整性检查...
    python check_env.py
    if !errorlevel! neq 0 (
        echo check_env.py 执行失败, 继续按当前配置启动
    )
    echo.
) else (
    echo 未找到 check_env.py, 跳过 .env 完整性检查
    echo.
)

rem 虚拟环境
if not exist "venv" (
    echo 正在创建虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo 虚拟环境创建成功
)

echo 正在激活虚拟环境...
call "venv\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [错误] 激活虚拟环境失败
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
pip install -r requirements.txt >nul 2>&1
if !errorlevel! neq 0 (
    echo 尝试国内镜像源...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ >nul 2>&1
)
if !errorlevel! neq 0 (
    echo 尝试阿里云镜像源...
    pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ >nul 2>&1
)
if !errorlevel! neq 0 (
    echo [错误] 依赖安装失败，请手动运行: pip install -r requirements.txt
    pause
    exit /b 1
)
echo 所有依赖安装完成
echo.

rem 数据库模式检查与初始化
if /i "!STORAGE_BACKEND!"=="postgres" (
    echo 正在检查 PostgreSQL 数据库状态...
    python -c "from src.config import STORAGE_BACKEND; from src.storage import get_storage; s=get_storage(); exit(0 if STORAGE_BACKEND().lower()=='postgres' and s.__class__.__name__=='PostgresAdapter' else 1)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [提示] 正在初始化数据库表...
        python -m src.storage.migration --create-tables-only >nul 2>&1
        if !errorlevel! equ 0 (
            echo [成功] 数据库表初始化完成
        ) else (
            echo [警告] 数据库初始化失败，请检查配置后在Web界面重试
        )
    ) else (
        echo [成功] 数据库连接正常
    )
    echo.
)

rem 读取端口
set "SERVER_PORT=8000"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if /i "%%a"=="SERVER_PORT" set "SERVER_PORT=%%b"
    )
)

rem 获取本机IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=*" %%b in ("%%a") do set "LOCAL_IP=%%b"
    goto :found_ip
)
:found_ip

echo 正在检查端口!SERVER_PORT!是否可用...
netstat -an | findstr /i "LISTENING" | findstr ":!SERVER_PORT! " >nul 2>&1
if !errorlevel! equ 0 (
    echo [错误] 端口!SERVER_PORT!已被占用
    echo 请修改.env文件中的SERVER_PORT配置
    pause
    exit /b 1
)
echo [通过] 端口!SERVER_PORT!可用
echo.

echo =====================================
echo   正在启动Web管理界面...
echo =====================================
echo.
echo 请在浏览器访问:
echo   - 本地: http://127.0.0.1:!SERVER_PORT!
if defined LOCAL_IP (
    echo   - 局域网: http:!LOCAL_IP!:!SERVER_PORT!
)
echo.

echo.
echo 按下 Ctrl+C 停止服务
echo.

python -u web_server.py

pause
goto :eof

rem =====================================
rem 子程序：同步 STORAGE_BACKEND 到 .env
rem =====================================
:sync_env_storage_backend
set "_tmp_env=.env.tmp"

rem 如果没有 .env 文件，直接创建
if not exist ".env" (
    echo STORAGE_BACKEND=!STORAGE_BACKEND!>.env
    echo [状态] 已创建 .env 并设置运行模式: !STORAGE_BACKEND!
    exit /b 0
)

rem 复制并替换/追加 STORAGE_BACKEND
set "_found=0"
(
    for /f "usebackq delims=" %%L in (".env") do (
        set "_line=%%L"
        echo !_line! | findstr /b /i "STORAGE_BACKEND=" >nul
        if !errorlevel! equ 0 (
            echo STORAGE_BACKEND=!STORAGE_BACKEND!
            set "_found=1"
        ) else (
            echo %%L
        )
    )
    if !_found! equ 0 (
        echo STORAGE_BACKEND=!STORAGE_BACKEND!
    )
)>"%_tmp_env%"

move /y "%_tmp_env%" ".env" >nul 2>&1
echo [状态] 已同步运行模式到 .env: !STORAGE_BACKEND!
exit /b 0
