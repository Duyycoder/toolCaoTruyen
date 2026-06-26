@echo off
setlocal

cd /d "%~dp0"
set PYTHONPATH=%~dp0

title Gemini API Server [Port 7860]
color 0A

echo.
echo  =========================================
echo   Gemini API Server v1.0
echo   URL : http://localhost:7860
echo   Docs: http://localhost:7860/docs
echo  =========================================
echo.

if not exist cookies.json (
    echo [ERROR] cookies.json not found!
    pause
    exit /b 1
)

if not exist api_keys.json (
    echo [INFO] Creating first API key...
    python -m server.config create-key default
    echo.
)

echo  Starting server... Press Ctrl+C to stop.
echo.

python -m uvicorn server.main:app --host 0.0.0.0 --port 7860

echo.
echo  Server stopped.
pause
