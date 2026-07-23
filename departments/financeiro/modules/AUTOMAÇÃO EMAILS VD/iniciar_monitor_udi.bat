@echo off
set SCRIPT_DIR=%~dp0
set SCRIPT=%SCRIPT_DIR%monitor_emails_vd.py

echo Iniciando Monitor de Emails VD (UDI) em segundo plano...
start "" pythonw.exe "%SCRIPT%"

echo Log UDI disponivel em: %SCRIPT_DIR%monitor_vd.log
timeout /t 3 >nul
