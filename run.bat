@echo off
chcp 65001 >nul 2>&1
title Tool Cào Truyện - Đang chạy...

echo.
echo ════════════════════════════════════════════════════════════
echo    📖  Tool Cào Truyện - Khởi động
echo ════════════════════════════════════════════════════════════
echo.

REM === Kiểm tra Python ===
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Chưa cài Python! Hãy chạy install.bat trước.
    pause
    exit /b 1
)

REM === Kiểm tra thư viện ===
python -c "import selenium; from bs4 import BeautifulSoup" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Chưa cài thư viện! Đang tự động cài đặt...
    echo.
    pip install -r requirements.txt
    echo.
)

REM === Chạy tool ===
python main.py

echo.
echo ────────────────────────────────────────────────────────────
echo    Nhấn phím bất kỳ để đóng cửa sổ...
echo ────────────────────────────────────────────────────────────
pause >nul
