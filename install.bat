@echo off
chcp 65001 >nul 2>&1
title Cài đặt Tool Cào Truyện

echo.
echo ════════════════════════════════════════════════════════════
echo    📦  CÀI ĐẶT TỰ ĐỘNG - Tool Cào Truyện
echo ════════════════════════════════════════════════════════════
echo.

REM === Kiểm tra Python đã cài chưa ===
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] CHƯA CÀI PYTHON!
    echo.
    echo     Hãy tải Python 3 tại: https://www.python.org/downloads/
    echo     Khi cài, nhớ TICK vào ô "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [✓] Đã tìm thấy Python:
python --version
echo.

REM === Kiểm tra Google Chrome ===
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo [✓] Đã tìm thấy Google Chrome.
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    echo [✓] Đã tìm thấy Google Chrome.
) else (
    echo [!] CHƯA CÀI GOOGLE CHROME!
    echo.
    echo     Hãy tải Chrome tại: https://www.google.com/chrome/
    echo     Cài xong rồi chạy lại file này.
    echo.
    pause
    exit /b 1
)

echo.
echo [→] Đang cài đặt thư viện Python cần thiết...
echo.

pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [!] Cài đặt thất bại! Thử chạy lại bằng cách:
    echo     Nhấp chuột phải → "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo.
echo ════════════════════════════════════════════════════════════
echo    ✅  CÀI ĐẶT HOÀN TẤT!
echo ════════════════════════════════════════════════════════════
echo.
echo    Bây giờ bạn có thể chạy tool bằng cách:
echo      - Nhấp đúp vào file "run.bat"
echo      - Hoặc mở Terminal gõ: python main.py
echo.
pause
