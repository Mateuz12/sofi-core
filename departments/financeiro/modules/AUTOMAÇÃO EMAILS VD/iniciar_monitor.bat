@echo off
set SCRIPT_DIR=%~dp0
set PY_CMD="C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"

echo Finalizando versoes anteriores dos monitores...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name like '%%python%%'\" | Where-Object { $_.CommandLine -like '*monitor_emails_vd*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
taskkill /f /im pythonw.exe >nul 2>&1

echo Iniciando Monitores de Emails VD (UDI + BH) em segundo plano...
start "" %PY_CMD% "%SCRIPT_DIR%monitor_emails_vd.py"
start "" %PY_CMD% "%SCRIPT_DIR%BH\monitor_emails_vd_BH.py"

echo Logs disponiveis em:
echo   - UDI: %SCRIPT_DIR%monitor_vd.log
echo   - BH:  %SCRIPT_DIR%BH\monitor_vd.log
timeout /t 3 >nul

