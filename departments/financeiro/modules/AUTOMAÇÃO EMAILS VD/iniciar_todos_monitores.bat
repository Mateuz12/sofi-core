@echo off
set SCRIPT_DIR=%~dp0
set PY_CMD="C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"

echo Finalizando versoes anteriores dos monitores...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name like '%%python%%'\" | Where-Object { $_.CommandLine -like '*monitor_emails_vd*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
taskkill /f /im pythonw.exe >nul 2>&1

echo [1/2] Iniciando Monitor VD UDI...
start "" %PY_CMD% "%SCRIPT_DIR%monitor_emails_vd.py"

ping 127.0.0.1 -n 4 >nul

echo [2/2] Iniciando Monitor VD BH...
start "" %PY_CMD% "%SCRIPT_DIR%BH\monitor_emails_vd_BH.py"

echo.
echo Monitores de Emails VD (UDI + BH) iniciados em segundo plano!
echo Logs:
echo   - UDI: %SCRIPT_DIR%monitor_vd.log
echo   - BH:  %SCRIPT_DIR%BH\monitor_vd.log
echo.
ping 127.0.0.1 -n 6 >nul
