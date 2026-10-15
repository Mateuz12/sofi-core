@echo off
set SCRIPT_DIR=%~dp0
set SCRIPT=%SCRIPT_DIR%BH\monitor_emails_vd_BH.py
set "PY_CMD=pythonw.exe"
if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\pythonw.exe" set "PY_CMD=%LOCALAPPDATA%\Python\pythoncore-3.14-64\pythonw.exe"
if exist "%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe" set "PY_CMD=%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"

echo Iniciando Monitor de Emails VD (BH) em segundo plano...
start "" %PY_CMD% "%SCRIPT%"

echo Log BH disponivel em: %SCRIPT_DIR%BH\monitor_vd.log
timeout /t 3 >nul
