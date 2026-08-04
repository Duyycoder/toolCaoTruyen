@echo off
rem Set console page to standard US/English (OEM)
chcp 437 >nul 2>&1
title Cau hinh va Cai dat he thong Tool Cao Truyen
cls

echo ============================================================
echo    CAI DAT TU DONG HE THONG CAO VA DICH TRUYEN CHU
echo ============================================================
echo.

rem === 1. Kiem tra Python ===
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] CHUA CAI PYTHON!
    echo.
    echo     Vui long tai va cai dat Python 3 tai: https://www.python.org/downloads/
    echo     Khi cai dat, NHO tich chon "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
echo [OK] Da tim thay Python:
python --version
echo.

rem === 2. Tao Virtual Environment ===
if not exist ".venv" (
    echo [INFO] Dang tao thu muc ao venv de co lap thu vien...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Tao thu muc ao venv that bai.
        pause
        exit /b 1
    )
    echo [OK] Da tao thu muc ao venv.
) else (
    echo [OK] Da co san thu muc ao venv.
)
echo.

rem === 3. Cai dat thu vien vao .venv ===
echo [INFO] Dang cap nhat pip va cai dat cac thu vien Python...
.venv\Scripts\python -m pip install --upgrade pip >nul 2>&1
.venv\Scripts\python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi cai dat thu vien Python.
    pause
    exit /b 1
)
echo [OK] Da cai dat xong cac thu vien Python.
echo.

rem === 4. Kiem tra Google Chrome ===
rem Chrome CHI can khi cao truyen tu web (bypass Cloudflare). Nguon "thu muc cuc bo"
rem va "AI sang tac" khong dung den, nen thieu Chrome chi canh bao - KHONG dung setup.
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo [OK] Da tim thay Google Chrome.
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    echo [OK] Da tim thay Google Chrome.
) else (
    echo [WARN] Chua cai Google Chrome.
    echo        Van cai dat tiep duoc. Chi khi CAO TRUYEN TU WEB moi can Chrome.
    echo        Neu can, tai tai: https://www.google.com/chrome/
)
echo.

rem === 5. Lua chon Engine dich thuat ===
echo ============================================================
echo    CHON ENGINE DICH THUAT MAC DINH
echo ============================================================
echo [1] Ollama - Dich Local Offline, can card do hoa roi tu 6GB VRAM tro len
echo [2] Gemini API - Dich Online toc do cao, can Gemini API Key
echo [3] Gemini API (Offline/Local) - Dich qua cookies, tu dong chay server
echo [4] Su dung tat ca cac option tren
echo ------------------------------------------------------------
rem setup.bat cua repo tong dat NON_INTERACTIVE=1 roi goi file nay. Truoc day
rem cac dong "set /p" duoi day van hoi, khien setup dung im cho go phim - nguoi
rem dung tuong treo. Che do khong tuong tac -> lay mac dinh, khong hoi gi ca.
if "%NON_INTERACTIVE%"=="1" (
    echo [INFO] Che do cai dat tu dong - chon mac dinh [4] va bo qua nhap API Key.
    echo        Dien Gemini API Key sau trong giao dien - muc Cau Hinh Chung.
    set CHOICE=4
) else (
    set /p CHOICE="Nhap lua chon cua ban [1, 2, 3, 4] - Mac dinh la 4: "
)

if "%CHOICE%"=="" set CHOICE=4

if "%CHOICE%"=="2" goto :setup_gemini_only
if "%CHOICE%"=="3" goto :setup_gemini_offline
if "%CHOICE%"=="4" goto :setup_both
goto :setup_ollama_only

:setup_gemini_only
echo.
if not "%NON_INTERACTIVE%"=="1" (
    set /p GEMINI_KEY="Nhap Gemini API Key cua ban - Lay tai aistudio.google.com: "
)
.venv\Scripts\python setup_helper.py gemini "%GEMINI_KEY%"
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi cap nhat cau hinh.
    pause
    exit /b 1
)
echo.
echo [OK] Da cau hinh default engine la Gemini API.
echo [INFO] Da qua buoc tai model Ollama 4.7GB de tiet kiem dung luong.
goto :setup_complete

:setup_gemini_offline
echo.
echo [INFO] Da chon Gemini API (Offline/Local) lam Engine mac dinh.
echo [INFO] Sau khi setup xong, ban can mo file "Gemini-API\cookies.json" va dien cookies.
.venv\Scripts\python setup_helper.py gemini_api ""
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi cap nhat cau hinh.
    pause
    exit /b 1
)
echo.
echo [OK] Da cau hinh default engine la Gemini API Offline/Local.
echo [INFO] Bo qua buoc tai model Ollama de tiet kiem dung luong o dia.
goto :setup_complete

:setup_both
echo.
if not "%NON_INTERACTIVE%"=="1" (
    set /p GEMINI_KEY="Nhap Gemini API Key - Nhan Enter de bo qua hoac dien sau: "
)
.venv\Scripts\python setup_helper.py ollama "%GEMINI_KEY%"
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi cap nhat cau hinh.
    pause
    exit /b 1
)
goto :setup_ollama_install

:setup_ollama_only
.venv\Scripts\python setup_helper.py ollama ""
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi cap nhat cau hinh.
    pause
    exit /b 1
)
goto :setup_ollama_install

:setup_ollama_install
echo.
echo ============================================================
echo    CAU HINH OLLAMA ^& MODEL AI
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

rem Tai va cai dat Ollama
echo [INFO] Khong tim thay Ollama. Dang tu dong tai ve...
echo [INFO] Dang tai OllamaSetup.exe tu ollama.com...
curl -L -o OllamaSetup.exe https://ollama.com/download/OllamaSetup.exe
if %errorlevel% neq 0 (
    echo [ERROR] Tai OllamaSetup.exe that bai. Vui long kiem tra ket noi.
    pause
    exit /b 1
)

echo [INFO] Dang chay bo cai dat Ollama - Silent Install...
echo [INFO] Vui long cho trong giay lat...
start /wait OllamaSetup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
del OllamaSetup.exe

if exist "%OLLAMA_PATH%" (
    set "OLLAMA_CMD=%OLLAMA_PATH%"
    echo [OK] Cai dat Ollama thanh cong.
) else (
    echo [WARN] Cai Ollama that bai hoac khong tim thay tai: %OLLAMA_PATH%
    echo        Bo qua buoc tai model Ollama. Ung dung van chay duoc voi engine
    echo        Gemini. Muon dung Ollama thi cai tay tai https://ollama.com
    echo        roi mo lai ung dung - model se duoc tai tu dong.
    goto :setup_complete
)

:ollama_found
echo [OK] Da nhan dien Ollama:
"%OLLAMA_CMD%" --version
echo.

rem === Khoi chay Ollama Daemon neu chua chay ===
"%OLLAMA_CMD%" list >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Ollama server chua hoat dong. Dang khoi chay...
    if exist "%localappdata%\Programs\Ollama\ollama app.exe" (
        start "" "%localappdata%\Programs\Ollama\ollama app.exe"
    ) else (
        start /b "" "%OLLAMA_CMD%" serve
    )
    echo [WAIT] Dang cho Ollama khoi dong - 5 giay...
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
    echo [WARN] Chua ket noi duoc Ollama server - bo qua buoc tai model o day.
    echo        Ung dung se tu khoi dong Ollama va tu tai model khi can dung.
    goto :setup_complete
)
echo [OK] Da ket noi voi Ollama server.
echo.

rem === Tai Model qwen2.5:3b-instruct (Lightweight Translation Model) ===
echo [INFO] Dang kiem tra Model qwen2.5:3b-instruct...
"%OLLAMA_CMD%" list | findstr "qwen2.5:3b-instruct" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Model qwen2.5:3b-instruct da co san.
) else (
    echo [INFO] Model qwen2.5:3b-instruct chua duoc tai. Dang tai...
    "%OLLAMA_CMD%" pull qwen2.5:3b-instruct
)

rem === Tai Model qwen2.5:7b-instruct (Main LLM Model) ===
echo [INFO] Dang kiem tra Model qwen2.5:7b-instruct...
"%OLLAMA_CMD%" list | findstr "qwen2.5:7b-instruct" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Model qwen2.5:7b-instruct da co san.
) else (
    echo [INFO] Model qwen2.5:7b-instruct chua duoc tai. Dang tai...
    "%OLLAMA_CMD%" pull qwen2.5:7b-instruct
)

rem === Cai dat Model chuyen dich hy-mt2:1.8b ===
echo [INFO] Dang kiem tra Model hy-mt2:1.8b...
"%OLLAMA_CMD%" list | findstr "hy-mt2:1.8b" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Model hy-mt2:1.8b da co san.
) else (
    echo [INFO] Model hy-mt2:1.8b chua duoc tai. Dang cai dat...
    pushd ollama_models
    call install_hy_mt2.bat
    popd
)

:setup_complete
echo.
echo ============================================================
echo    [OK] HE THONG DA SAN SANG!
echo ============================================================
echo    - Moi truong ao venv: Da duoc thiet lap.
echo    - Cac thu vien Python: Da duoc cai dat.
echo    - Cau hinh: Da duoc cap nhat vao config.json.
echo.
echo    Bay gio ban chi can nhap dup chuot vao file:
echo        "run.bat"
echo    de mo giao dien Web UI va su dung.
echo ============================================================
echo.
pause
