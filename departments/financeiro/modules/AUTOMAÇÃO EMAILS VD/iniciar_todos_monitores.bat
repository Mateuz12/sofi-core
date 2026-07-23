@echo off
set SCRIPT_DIR=%~dp0

echo Finalizando versoes anteriores dos monitores pythonw...
taskkill /f /im pythonw.exe >nul 2>&1

echo [1/2] Iniciando Monitor VD UDI...
start "" pythonw.exe "%SCRIPT_DIR%monitor_emails_vd.py"

echo [2/2] Iniciando Monitor VD BH...
start "" pythonw.exe "%SCRIPT_DIR%BH\monitor_emails_vd_BH.py"

echo.
echo Monitores de Emails VD (UDI + BH) iniciados em segundo plano!
echo Logs:
echo   - UDI: %SCRIPT_DIR%monitor_vd.log
echo   - BH:  %SCRIPT_DIR%BH\monitor_vd.log
echo.
timeout /t 5 >nul
