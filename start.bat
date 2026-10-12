@echo off
chcp 65001 >nul
title 城知AI文旅Agent
cd /d "%~dp0"

echo ========================================
echo   城知 AI文旅Agent 一键启动
echo ========================================
echo.

REM 启动后端
echo [1/2] 启动后端服务 (端口8000)...
start "城知后端" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

REM 等待后端启动
timeout /t 4 /nobreak >nul

REM 打开前端
echo [2/2] 打开网页前端...
start "" "web\index.html"

echo.
echo ========================================
echo   启动完成！浏览器已打开
echo   后端管理：http://localhost:8000/docs
echo   关闭本窗口不影响后端运行
echo ========================================
pause
