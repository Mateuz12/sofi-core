@echo off
set SCRIPT_DIR=%~dp0
set SCRIPT=%SCRIPT_DIR%BH\monitor_emails_vd_BH.py

echo Iniciando Monitor de Emails VD (BH) em segundo plano...
start "" pythonw.exe "%SCRIPT%"

echo Log BH disponivel em: %SCRIPT_DIR%BH\monitor_vd.log
timeout /t 3 >nul
