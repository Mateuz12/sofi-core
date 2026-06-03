@echo off
:: Script de execução automática dos Relatórios Retaguarda UDI + BH
:: Agendado para rodar todos os dias às 08:15

set PROJETO_DIR=c:\Users\luma.dias\Documents\PROJETO\SOFI-core\departments\financeiro\modules\retaguarda
set PYTHON_EXE=C:\Users\luma.dias\AppData\Local\Python\pythoncore-3.14-64\python.exe
set LOG_FILE=%PROJETO_DIR%\log_execucao.txt

echo ============================================== >> "%LOG_FILE%"
echo [%date% %time%] Inicio da execucao automatica >> "%LOG_FILE%"
echo ============================================== >> "%LOG_FILE%"

:: --- RELATÓRIO UDI ---
echo [%date% %time%] Iniciando relatorio UDI... >> "%LOG_FILE%"
cd /d "%PROJETO_DIR%"
"%PYTHON_EXE%" "extrator_retaguarda.py" --unidade UDI >> "%LOG_FILE%" 2>&1
echo [%date% %time%] Relatorio UDI finalizado (codigo: %ERRORLEVEL%) >> "%LOG_FILE%"

:: --- RELATÓRIO BH ---
echo [%date% %time%] Iniciando relatorio BH... >> "%LOG_FILE%"
"%PYTHON_EXE%" "extrator_retaguarda.py" --unidade BH >> "%LOG_FILE%" 2>&1
echo [%date% %time%] Relatorio BH finalizado (codigo: %ERRORLEVEL%) >> "%LOG_FILE%"

echo ============================================== >> "%LOG_FILE%"
echo [%date% %time%] Execucao concluida >> "%LOG_FILE%"
echo ============================================== >> "%LOG_FILE%"
