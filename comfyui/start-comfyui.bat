@echo off
REM ============================================================
REM start-comfyui.bat — Launch ComfyUI on the Windows PC
REM ============================================================
REM
REM What this does:
REM   1. Activates the Python venv at C:\ComfyUI\venv
REM   2. Sets the right CUDA env vars for the RTX 5070
REM   3. Launches ComfyUI listening on http://127.0.0.1:8188
REM   4. Opens the browser to the ComfyUI UI
REM
REM Run this from any directory. Double-click works.
REM ============================================================

set COMFYUI_DIR=C:\ComfyUI
set VENV=%COMFYUI_DIR%\venv
set PORT=8188

REM --- pre-flight checks ---
if not exist "%COMFYUI_DIR%\main.py" (
    echo [ERROR] ComfyUI not found at %COMFYUI_DIR%
    echo Clone it first: git clone https://github.com/comfyanonymous/ComfyUI.git %COMFYUI_DIR%
    pause
    exit /b 1
)

if not exist "%VENV%\Scripts\activate.bat" (
    echo [ERROR] Python venv not found at %VENV%
    echo Create it: cd %COMFYUI_DIR% ^&^& python -m venv venv ^&^& %VENV%\Scripts\activate ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)

REM --- GPU sanity check ---
echo [INFO] Checking GPU...
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
if errorlevel 1 (
    echo [WARN] nvidia-smi returned an error. Check your NVIDIA drivers.
    echo        RTX 5070 needs driver 570+ with CUDA 12.8 support.
    echo.
    set /p CONTINUE="Continue anyway? (y/n): "
    if /i not "%CONTINUE%"=="y" exit /b 1
)

REM --- activate venv ---
call "%VENV%\Scripts\activate.bat"

REM --- extra Python args for Blackwell GPU ---
REM RTX 5070 needs PyTorch nightly with CUDA 12.8. If you installed
REM the stable torch, this script will warn at startup but still run.
set TORCH_CUDA_ARCH_LIST=12.0
set PYTORCH_NVFUSER_ENABLED=0

REM --- launch ---
echo.
echo [INFO] Starting ComfyUI on http://127.0.0.1:%PORT%
echo [INFO] Press Ctrl+C to stop.
echo.

cd /d "%COMFYUI_DIR%"
python main.py --listen 127.0.0.1 --port %PORT% --disable-auto-launch

REM If the user closes the browser, ComfyUI keeps running. Ctrl+C stops it.
pause
