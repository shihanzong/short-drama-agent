@echo off
chcp 65001 >nul
echo ========================================
echo  AI短剧生产系统 - Web 启动器
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

echo [2/3] 检查依赖...
python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo 安装 fastapi...
    pip install fastapi --quiet
)

python -c "import uvicorn" >nul 2>&1
if %errorlevel% neq 0 (
    echo 安装 uvicorn...
    pip install uvicorn --quiet
)

echo [3/3] 启动 Web 服务器...
echo.
echo ========================================
echo  服务地址: http://127.0.0.1:8000
echo  按 Ctrl+C 停止
echo ========================================
echo.

python web/app.py

pause
