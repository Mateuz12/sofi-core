@echo off
set SCRIPT_DIR=%~dp0
set SCRIPT=%SCRIPT_DIR%monitor_emails_vd.py
set PY_CMD="C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"

echo Iniciando Monitor de Emails VD (UDI) em segundo plano...
start "" %PY_CMD% "%SCRIPT%"

echo Log UDI disponivel em: %SCRIPT_DIR%monitor_vd.log
timeout /t 3 >nul
