@echo off
chcp 65001 >nul
title VisionGuide Server

echo ========================================
echo   VisionGuide Server 一键启动
echo ========================================
echo.

:: 激活 conda 环境
call conda activate vgllm
if errorlevel 1 (
    echo [错误] 无法激活 conda 环境 vgllm，请确认已创建该环境
    pause
    exit /b 1
)

:: 加载 .env 环境变量
if exist "%~dp0.env" (
    echo [信息] 加载 .env 配置...
    for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" set "%%a=%%b"
    )
)

echo [信息] 启动 WebSocket 服务器 (端口 8765)...
echo [信息] 按 Ctrl+C 停止服务器
echo.

python "%~dp0server\main.py"

pause
