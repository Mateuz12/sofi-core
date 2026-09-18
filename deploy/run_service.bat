@echo off
setlocal enabledelayedexpansion

:: Determine project root directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
pushd "%PROJECT_ROOT%"

echo ==============================================================================
echo                      SOFI SERVICE ENTRYPOINT (STREAMLIT + NGROK)
echo ==============================================================================

:: 1. Ensure network share authentication (SMB \\srv-dc01)
echo [*] Checking network share connection \\srv-dc01\File Server...
net use \\srv-dc01\"File Server" 2>NUL

:: 2. Check and launch ngrok tunnel with explicit authtoken config
set "NGROK_EXE=C:\ngrok\ngrok.exe"
set "NGROK_CONFIG="
if exist "C:\ngrok\ngrok.yml" (
    set "NGROK_CONFIG=--config C:\ngrok\ngrok.yml"
) else if exist "C:\Users\Administrator\AppData\Local\ngrok\ngrok.yml" (
    set "NGROK_CONFIG=--config C:\Users\Administrator\AppData\Local\ngrok\ngrok.yml"
)

if exist "%NGROK_EXE%" (
    tasklist /FI "IMAGENAME eq ngrok.exe" 2>NUL | find /I /N "ngrok.exe">NUL
    if "!ERRORLEVEL!"=="1" (
        echo [*] Starting ngrok tunnel on port 8501...
        start "SOFI-ngrok" /B "%NGROK_EXE%" http 8501 !NGROK_CONFIG! --log=stdout
    ) else (
        echo [*] ngrok is already running.
    )
) else (
    echo [!] WARNING: ngrok.exe not found at %NGROK_EXE%. Skipping tunnel startup.
)

:: 3. Locate Python executable with Streamlit
set "PYTHON_EXE="
if defined SOFI_PYTHON (
    set "PYTHON_EXE=%SOFI_PYTHON%"
) else if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
) else if exist "C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe" (
    set "PYTHON_EXE=C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe"
) else if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
) else (
    set "PYTHON_EXE=python.exe"
)

echo [*] Using Python executable: !PYTHON_EXE!
echo [*] Launching Streamlit Hub on port 8501...

:: 4. Run Streamlit Hub (Foreground process for NSSM monitoring)
"!PYTHON_EXE!" -m streamlit run dashboard/app.py --server.port 8501 --server.headless true --server.address 0.0.0.0

popd
