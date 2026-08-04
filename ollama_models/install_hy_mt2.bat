@echo off
chcp 65001 >nul
echo === Cai dat model chuyen dich HY-MT2-1.8B (Tencent) vao Ollama ===
echo Tai model (~2GB)...
ollama pull hf.co/tencent/Hy-MT2-1.8B-GGUF:Q8_0
if errorlevel 1 (
    echo [LOI] Khong tai duoc model. Kiem tra mang / Ollama dang chay.
    exit /b 1
)
echo Tao model hy-mt2:1.8b voi template da sua...
cd /d "%~dp0"
ollama create hy-mt2:1.8b -f Modelfile.hy-mt2
if errorlevel 1 (
    echo [LOI] Khong tao duoc model tu Modelfile.
    exit /b 1
)
ollama rm hf.co/tencent/Hy-MT2-1.8B-GGUF:Q8_0
echo.
echo [XONG] Model "hy-mt2:1.8b" da san sang. Chon no trong dropdown "Model Ollama" cua webui.
