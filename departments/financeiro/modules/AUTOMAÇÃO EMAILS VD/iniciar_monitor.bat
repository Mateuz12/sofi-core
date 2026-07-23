@echo off
set SCRIPT_DIR=%~dp0

echo Finalizando versoes anteriores dos monitores pythonw...
taskkill /f /im pythonw.exe >nul 2>&1

echo Iniciando Monitores de Emails VD (UDI + BH) em segundo plano...
start "" pythonw.exe "%SCRIPT_DIR%monitor_emails_vd.py"
start "" pythonw.exe "%SCRIPT_DIR%BH\monitor_emails_vd_BH.py"

echo Logs disponiveis em:
echo   - UDI: %SCRIPT_DIR%monitor_vd.log
echo   - BH:  %SCRIPT_DIR%BH\monitor_vd.log
timeout /t 3 >nul

