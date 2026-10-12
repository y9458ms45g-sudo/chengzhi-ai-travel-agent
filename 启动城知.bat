@echo off
chcp 65001 >nul
title ChengZhi Wenlv Agent
cd /d "%~dp0"

set PY=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe
if not exist "%PY%" (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

echo ============================================
echo   ChengZhi Wenlv Agent Starting...
echo ============================================

netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [INFO] Backend already running.
) else (
    echo [1/2] Starting backend...
    start "ChengZhiBackend" /min "%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    timeout /t 8 /nobreak >nul
)

echo [2/2] Opening browser...
start "" "http://localhost:8000/dev"
echo.
echo Done. Close the minized backend window to stop.
timeout /t 5 /nobreak >nul