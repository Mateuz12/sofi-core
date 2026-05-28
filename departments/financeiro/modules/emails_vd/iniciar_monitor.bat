@echo off
set SCRIPT_DIR=%~dp0
set SCRIPT=%SCRIPT_DIR%monitor_emails_vd.py

echo Finalizando versões anteriores do monitor...
:: Finaliza o pythonw.exe se estiver rodando (ignora erro se não houver)
taskkill /f /im pythonw.exe >nul 2>&1

echo Iniciando Monitor de Emails VD em segundo plano...
start "" pythonw.exe "%SCRIPT%"

echo Log disponivel em: %SCRIPT_DIR%monitor_vd.log
timeout /t 3 >nul
