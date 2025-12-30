@echo off
chcp 65001 >nul 2>&1
cls
title 咸鱼智能监控机器人 - Web管理界面启动器

:: 清理临时变量，避免环境变量污染
set "PYTHON_VERSION="
set "PYTHON_MAJOR="
set "PYTHON_MINOR="

:: 1. 定义转义字符，用于设置颜色
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do (
  set ESC=%%b
)


echo.
echo ================================================
echo 咸鱼智能监控机器人 - Web管理界面启动器
echo ================================================
echo.

:: -------------------------- 1. 检查Python环境（严格校验3.9+） --------------------------
echo 1. 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  错误：未找到Python环境，请先安装Python 3.9或更高版本。
    echo  官方下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 提取Python版本号（拆分主/次版本，用于校验）
for /f "tokens=2 delims=." %%a in ('python --version 2^>^&1') do set "PYTHON_MAJOR=%%a"
for /f "tokens=3 delims=." %%b in ('python --version 2^>^&1') do set "PYTHON_MINOR=%%b"
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%i"

:: 校验Python版本≥3.9
if %PYTHON_MAJOR% lss 3 (
    echo  错误：Python版本过低（当前%PYTHON_VERSION%），需安装3.9及以上版本！
    pause
    exit /b 1
)
if %PYTHON_MAJOR% equ 3 if %PYTHON_MINOR% lss 9 (
    echo  错误：Python版本过低（当前%PYTHON_VERSION%），需安装3.9及以上版本！
    pause
    exit /b 1
)

echo  Python %PYTHON_VERSION% 已安装（符合3.9+版本要求）
echo.

:: -------------------------- 2. 检查依赖配置文件 --------------------------
echo 2. 检查依赖配置文件...
if not exist "requirements.txt" (
    echo  错误：未找到requirements.txt文件！
    echo  请确保本批处理文件在项目根目录下运行。
    pause
    exit /b 1
)
echo  requirements.txt 文件存在
echo.

:: -------------------------- 3. 检查8000端口占用 --------------------------
echo 3. 检查8000端口占用情况...
netstat -ano | findstr ":8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo   警告：8000端口已被占用！
    echo  解决方案：1.关闭占用端口的程序 2.修改web_server.py的端口号
    choice /c YN /m "是否继续启动（可能失败）？[Y/N]"
    if errorlevel 2 (
        echo  用户取消启动
        pause
        exit /b 0
    )
) else (
    echo  8000端口未被占用
)
echo.

:: -------------------------- 4. 检查并安装依赖（优化pip路径问题） --------------------------
echo 4. 检查项目依赖...
python -c "import fastapi, playwright, openai" >nul 2>&1
if %errorlevel% equ 0 (
    echo  项目依赖已安装，无需重复安装
) else (
    echo  正在安装项目依赖（可能需要1-3分钟）...
    echo  若安装缓慢，可手动用国内源：python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    :: 优先用python -m pip（避免pip路径缺失问题），并升级pip
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    if %errorlevel% neq 0 (
        echo  依赖安装失败！
        echo  排查方向：1.检查网络连接 2.确认Python环境正常 3.检查requirements.txt语法
        pause
        exit /b 1
    ) else (
        echo  项目依赖安装完成
    )
)
echo.

:: -------------------------- 5. 启动Web服务器（捕获启动失败） --------------------------
echo 5. 启动Web管理界面...
echo  访问地址：%ESC%[34m【http://localhost:8000】%ESC%[0m (可Ctrl+左键链接直接打开)
echo  默认用户名：admin 
echo  默认密码：admin123
echo.
echo   提示：按 Ctrl+C 可停止Web服务器（停止后按任意键退出）
echo   第一次启动提示：若出现.env配置相关警告/错误、重新加载定时任务相关警告/错误，可忽略（首次配置后会自动消失）
echo ================================================
echo.

:: 启动服务并捕获启动失败场景
python web_server.py || (
    echo.
    echo  Web服务器启动失败！
    pause
    exit /b 1
)

:: 清理临时变量
set "PYTHON_VERSION="
set "PYTHON_MAJOR="
set "PYTHON_MINOR="

pause
exit /b 0