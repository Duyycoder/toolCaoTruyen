@echo off
rem Set console page to standard US/English (OEM) or just leave it default
chcp 437 >nul 2>&1
title Cau hinh va Cai dat he thong Tool Cao Truyen

echo.
echo ============================================================
echo    [PACK]  CAI DAT TU DONG DU AN VA DICH THUAT (OLLAMA)
echo ============================================================
echo.

rem === 1. Kiem tra Python ===
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] CHUA CAI PYTHON!
    echo.
    echo     Vui long tai Python 3 tai: https://www.python.org/downloads/
    echo     Khi cai dat, nho tich chon "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
echo [OK] Da tim thay Python:
python --version
echo.

rem === 2. Kiem tra Google Chrome ===
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo [OK] Da tim thay Google Chrome.
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    echo [OK] Da tim thay Google Chrome.
) else (
    echo [ERROR] CHUA CAI GOOGLE CHROME!
    echo.
    echo     Trinh duyet Chrome la bat buoc de bypass Cloudflare.
    echo     Hay tai va cai dat tai: https://www.google.com/chrome/
    echo.
    pause
    exit /b 1
)
echo.

rem === 3. Cai dat cac thu vien Python ===
echo [->] Dang cai dat/cap nhat cac thu vien Python...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi cai dat thu vien Python.
    pause
    exit /b 1
)
echo [OK] Da cai dat xong cac thu vien Python.
echo.

rem === 4. Cau hinh Ollama & Translator ===
echo ============================================================
echo    [AI]  CAU HINH TRINH DICH AI (OLLAMA)
echo ============================================================
echo.

set "OLLAMA_PATH=%localappdata%\Programs\Ollama\ollama.exe"
set "OLLAMA_CMD=ollama"

rem Kiem tra xem lenh ollama co chay duoc truc tiep khong
ollama --version >nul 2>&1
if %errorlevel% equ 0 (
    goto :ollama_found
)

rem Neu khong co trong PATH, kiem tra trong thu muc cai mac dinh
if exist "%OLLAMA_PATH%" (
    set "OLLAMA_CMD=%OLLAMA_PATH%"
    goto :ollama_found
)

rem Neu chua cai dat, tien hanh tai va cai dat Ollama
echo [i] Khong tim thay Ollama tren may tinh. Dang tu dong tai ve...
echo [->] Dang tai OllamaSetup.exe tu ollama.com (Direct Link)...
curl -L -o OllamaSetup.exe https://ollama.com/download/OllamaSetup.exe
if %errorlevel% neq 0 (
    echo [ERROR] Tai OllamaSetup.exe that bai. Vui long kiem tra ket noi mang.
    pause
    exit /b 1
)

echo [->] Dang chay bo cai dat Ollama (Silent Install)...
echo [i] Qua trinh nay se dien ra ngam trong vai giay. Vui long cho...
start /wait OllamaSetup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
del OllamaSetup.exe

rem Xac thuc lai sau khi cai dat
if exist "%OLLAMA_PATH%" (
    set "OLLAMA_CMD=%OLLAMA_PATH%"
    echo [OK] Cai dat Ollama thanh cong.
) else (
    echo [ERROR] Cai dat that bai hoac khong tim thay Ollama tai: %OLLAMA_PATH%
    echo     Vui long tai va cai dat Ollama thu cong tai: https://ollama.com
    pause
    exit /b 1
)

:ollama_found
echo [OK] Da nhan dien Ollama:
"%OLLAMA_CMD%" --version
echo.

rem === 5. Khoi chay Ollama Daemon neu chua chay ===
"%OLLAMA_CMD%" list >nul 2>&1
if %errorlevel% neq 0 (
    echo [i] Ollama daemon [server] chua hoat dong. Dang khoi chay...
    
    if exist "%localappdata%\Programs\Ollama\ollama app.exe" (
        start "" "%localappdata%\Programs\Ollama\ollama app.exe"
    ) else (
        start /b "" "%OLLAMA_CMD%" serve
    )
    
    echo [WAIT] Dang cho Ollama khoi dong [5 giay]...
    timeout /t 5 >nul
)

rem Kiem tra lai ket noi lan 2
"%OLLAMA_CMD%" list >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Chua ket noi duoc Ollama server. Thu khoi chay truc tiep...
    start /b "" "%OLLAMA_CMD%" serve
    timeout /t 5 >nul
)

"%OLLAMA_CMD%" list >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Khong the giao tiep voi Ollama daemon. Vui long mo thu cong ung dung Ollama.
    pause
    exit /b 1
)
echo [OK] Da ket noi voi Ollama server.
echo.

rem === 6. Tai Model qwen2.5:7b-instruct ===
echo [->] Dang kiem tra Model qwen2.5:7b-instruct...
"%OLLAMA_CMD%" list | findstr "qwen2.5:7b-instruct" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Model qwen2.5:7b-instruct da co san tren may.
    goto :setup_complete
)

echo [i] Model qwen2.5:7b-instruct chua duoc tai.
echo ------------------------------------------------------------
echo   [WARN] CANH BAO TAI FILE DUNG LUONG LON:
echo   He thong se tai file model qwen2.5:7b-instruct (Khoang 4.7 GB).
echo   Qua trinh nay co the ton vai phut den vai chuc phut tuy mang.
echo   Hay chac chan o dia con trong hon 5GB.
echo ------------------------------------------------------------
echo.

"%OLLAMA_CMD%" pull qwen2.5:7b-instruct
if %errorlevel% neq 0 (
    echo [ERROR] Tai model qwen2.5:7b-instruct that bai!
    echo     Vui long kiem tra ket noi internet va dung luong dia trong.
    pause
    exit /b 1
)

rem === 7. Xac nhan hoan tat ===
:setup_complete
echo.
"%OLLAMA_CMD%" list | findstr "qwen2.5:7b-instruct" >nul 2>&1
if %errorlevel% equ 0 (
    echo ============================================================
    echo    [OK] HE THONG DA SAN SANG!
    echo ============================================================
    echo    - Thu vien Python: Da san sang.
    echo    - Ollama server: Dang hoat dong.
    echo    - Model AI: qwen2.5:7b-instruct da duoc cai dat thanh cong.
    echo.
    echo    Bay gio ban co the khoi chay ung dung bang cach:
    echo      1. Nhap dup vao file "run.bat" de cao qua CLI.
    echo      2. Hoac go lenh: python app.py de mo giao dien Web UI.
    echo ============================================================
) else (
    echo [ERROR] Co loi xay ra trong qua trinh xac thuc model cuoi cung.
    pause
    exit /b 1
)

echo.
pause
