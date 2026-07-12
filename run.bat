@echo off
chcp 437 >nul 2>&1
title Khoi chay Tool Cao va Dich Truyen Chu
cls

rem -- Thiet lap thu muc Cache cuc bo trong du an --
set "PROJ_DIR=%~dp0"
if "%PROJ_DIR:~-1%"=="\" set "PROJ_DIR=%PROJ_DIR:~0,-1%"
set "HF_HOME=%PROJ_DIR%\scratch\.cache\huggingface"
set "TORCH_HOME=%PROJ_DIR%\scratch\.cache\torch"
set "XDG_CACHE_HOME=%PROJ_DIR%\scratch\.cache\xdg"


echo ============================================================
echo    Tool Cao va Dich Truyen Chu - Web UI
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please run setup.bat first to configure and install dependencies.
    echo.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Starting application using Virtual Environment venv...
    .venv\Scripts\python app.py
) else (
    echo [WARN] Virtual environment venv not found.
    echo Attempting to run using system Python...
    python app.py
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application failed to start.
    echo Please run setup.bat to reconfigure and install requirements.
    echo.
    pause
)
