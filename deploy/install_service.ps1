# ==============================================================================
# SOFI - Script de Instalação do Serviço Windows via NSSM
# ==============================================================================
# Este script registra e configura o SOFI (Streamlit Hub + APScheduler) como
# um Serviço Nativo do Windows 24/7 com auto-rotação de logs e reinicialização.
# ==============================================================================

# 1. Verificação de Elevação de Privilégios (Administrador)
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[!] Privilégios de Administrador são necessários para registrar um serviço Windows." -ForegroundColor Yellow
    Write-Host "[*] Solicitando elevação UAC..." -ForegroundColor Cyan
    
    $scriptPath = $MyInvocation.MyCommand.Definition
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    exit
}

# 2. Definição de Caminhos Principais
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Get-Item "$ScriptDir\..").FullName
$NssmExe = "$ProjectRoot\tools\nssm\nssm.exe"
$ServiceName = "SOFI-Service"
$LogsDir = "$ProjectRoot\logs"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "        INSTALAÇÃO DO SERVIÇO WINDOWS SOFI (NSSM)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Raiz do Projeto : $ProjectRoot" -ForegroundColor White
Write-Host "Executável NSSM : $NssmExe" -ForegroundColor White

# 3. Validação da Presença do NSSM
if (-not (Test-Path $NssmExe)) {
    Write-Host "[-] ERRO: NSSM não encontrado em '$NssmExe'." -ForegroundColor Red
    Write-Host "[-] Certifique-se de que o executável 'tools\nssm\nssm.exe' existe." -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

# 4. Detecção do Interpretador Python (.venv, Streamlit no AppData ou Sistema)
$pythonCandidates = @(
    "$ProjectRoot\.venv\Scripts\python.exe",
    "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
)

# Tentar encontrar python através da localização do streamlit.exe
$streamlitCmd = Get-Command streamlit.exe -ErrorAction SilentlyContinue
if ($streamlitCmd) {
    $streamlitDir = Split-Path -Parent $streamlitCmd.Path
    $pyFromStreamlit = Join-Path (Split-Path -Parent $streamlitDir) "python.exe"
    if (Test-Path $pyFromStreamlit) {
        $pythonCandidates = @($pyFromStreamlit) + $pythonCandidates
    }
}

# Adicionar fallback do sistema
$sysPython = (Get-Command python.exe -ErrorAction SilentlyContinue).Path
if ($sysPython) {
    $pythonCandidates += $sysPython
}

$PythonPath = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -and (Test-Path $candidate)) {
        # Testar se o candidato possui o módulo streamlit instalado
        $testResult = & $candidate -m streamlit --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonPath = $candidate
            break
        }
    }
}

if (-not $PythonPath) {
    Write-Host "[-] ERRO: Nenhum interpretador Python com 'streamlit' instalado foi localizado." -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}
Write-Host "[+] Python com Streamlit Detectado : $PythonPath" -ForegroundColor Green

# 5. Garantir Existência do Diretório de Logs
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
    Write-Host "[+] Diretório de logs criado em: $LogsDir" -ForegroundColor Green
}

# 6. Definir Script de Inicialização do Serviço (run_service.bat)
$ServiceBatch = "$ProjectRoot\deploy\run_service.bat"
if (-not (Test-Path $ServiceBatch)) {
    Write-Host "[-] ERRO: Script de entrada '$ServiceBatch' não foi encontrado." -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

# 7. Remoção de Serviço Existente (se houver)
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "[*] Interrompendo e removendo serviço '$ServiceName' existente..." -ForegroundColor Yellow
    & $NssmExe stop $ServiceName 2>$null
    Stop-Process -Name ngrok -ErrorAction SilentlyContinue
    & $NssmExe remove $ServiceName confirm 2>$null
    Start-Sleep -Seconds 2
}

# 8. Instalação e Configuração do Serviço via NSSM
Write-Host "[*] Instalando serviço '$ServiceName' apontando para '$ServiceBatch'..." -ForegroundColor Cyan
& $NssmExe install $ServiceName "$ServiceBatch"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] ERRO: Falha ao instalar o serviço via NSSM." -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

Write-Host "[*] Configurando parâmetros operacionais do serviço..." -ForegroundColor Cyan
& $NssmExe set $ServiceName AppDirectory "$ProjectRoot"
& $NssmExe set $ServiceName AppEnvironmentExtra "SOFI_PYTHON=$PythonPath"
& $NssmExe set $ServiceName AppStdout "$LogsDir\service_stdout.log"
& $NssmExe set $ServiceName AppStderr "$LogsDir\service_stderr.log"
& $NssmExe set $ServiceName AppRotateFiles 1
& $NssmExe set $ServiceName AppRotateBytes 10485760 # 10 MB
& $NssmExe set $ServiceName Start SERVICE_AUTO_START
& $NssmExe set $ServiceName DisplayName "SOFI - Streamlit Hub & APScheduler Service"
& $NssmExe set $ServiceName Description "Serviço nativo do SOFI (Sistema Operacional Financeiro Integrado) para execução 24/7 do Dashboard Streamlit e Orquestrador APScheduler."

# 9. Inicialização do Serviço
Write-Host "[*] Iniciando o serviço '$ServiceName'..." -ForegroundColor Cyan
& $NssmExe start $ServiceName

Start-Sleep -Seconds 3

# 10. Relatório de Status Final
$status = & $NssmExe status $ServiceName
if ($status -eq "SERVICE_RUNNING") {
    Write-Host "=================================================================" -ForegroundColor Green
    Write-Host "  [SUCCESS] Serviço SOFI instalado e iniciado com SUCESSO!" -ForegroundColor Green
    Write-Host "=================================================================" -ForegroundColor Green
    Write-Host "  Status do Serviço : $status" -ForegroundColor White
    Write-Host "  Dashboard URL    : http://localhost:8501" -ForegroundColor White
    Write-Host "  Log Stdout       : $LogsDir\service_stdout.log" -ForegroundColor White
    Write-Host "  Log Stderr       : $LogsDir\service_stderr.log" -ForegroundColor White
    Write-Host "=================================================================" -ForegroundColor Green
} else {
    Write-Host "[!] O serviço foi configurado, mas seu status atual é: $status" -ForegroundColor Yellow
    Write-Host "[!] Verifique os arquivos em '$LogsDir' para mais detalhes." -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Pressione Enter para concluir"
