# ==============================================================================
# SOFI - Script de Gerenciamento do Serviço Windows (SOFI-Service)
# ==============================================================================
# Permite verificar status, iniciar, parar, reiniciar, desinstalar e acompanhar
# os logs do serviço SOFI via menu interativo ou parâmetros de linha de comando.
# ==============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("status", "start", "stop", "restart", "uninstall", "tail-logs", "menu")]
    [string]$Action = "menu"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Get-Item "$ScriptDir\..").FullName
$NssmExe = "$ProjectRoot\tools\nssm\nssm.exe"
$ServiceName = "SOFI-Service"
$LogsDir = "$ProjectRoot\logs"

function Check-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Elevate-If-Needed {
    if (-not (Check-Admin)) {
        Write-Host "[!] Ação requer privilégios de Administrador. Solicitando elevação UAC..." -ForegroundColor Yellow
        $scriptPath = $MyInvocation.MyCommand.Definition
        Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" $Action"
        exit
    }
}

function Show-Status {
    Write-Host "`n--- Status do Serviço SOFI ---" -ForegroundColor Cyan
    if (Test-Path $NssmExe) {
        $status = & $NssmExe status $ServiceName 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Serviço '$ServiceName': $status" -ForegroundColor Green
        } else {
            Write-Host "Serviço '$ServiceName' não está instalado ou não foi encontrado." -ForegroundColor Yellow
        }
    } else {
        $sysService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($sysService) {
            Write-Host "Serviço '$ServiceName': $($sysService.Status)" -ForegroundColor Green
        } else {
            Write-Host "Serviço '$ServiceName' não registrado no sistema." -ForegroundColor Yellow
        }
    }
}

function Start-SOFI {
    Elevate-If-Needed
    Write-Host "[*] Iniciando serviço '$ServiceName'..." -ForegroundColor Cyan
    & $NssmExe start $ServiceName
    Show-Status
}

function Stop-SOFI {
    Elevate-If-Needed
    Write-Host "[*] Interrompendo serviço '$ServiceName'..." -ForegroundColor Yellow
    & $NssmExe stop $ServiceName
    Stop-Process -Name ngrok -ErrorAction SilentlyContinue
    Show-Status
}

function Restart-SOFI {
    Elevate-If-Needed
    Write-Host "[*] Reiniciando serviço '$ServiceName'..." -ForegroundColor Cyan
    & $NssmExe stop $ServiceName
    Stop-Process -Name ngrok -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    & $NssmExe start $ServiceName
    Show-Status
}

function Uninstall-SOFI {
    Elevate-If-Needed
    Write-Host "[!] Desinstalando serviço '$ServiceName'..." -ForegroundColor Red
    & $NssmExe stop $ServiceName 2>$null
    Stop-Process -Name ngrok -ErrorAction SilentlyContinue
    & $NssmExe remove $ServiceName confirm
    Write-Host "[+] Serviço '$ServiceName' removido com sucesso." -ForegroundColor Green
}

function Tail-Logs {
    Write-Host "`n--- Visualizador de Logs do SOFI ---" -ForegroundColor Cyan
    Write-Host "1. Stdout Log (stdout/prints)"
    Write-Host "2. Stderr Log (erros/tracebacks)"
    $logChoice = Read-Host "Escolha o log para acompanhar [1/2]"
    
    $targetLog = "$LogsDir\service_stdout.log"
    if ($logChoice -eq "2") {
        $targetLog = "$LogsDir\service_stderr.log"
    }

    if (Test-Path $targetLog) {
        Write-Host "[*] Exibindo últimas linhas de '$targetLog' (Ctrl+C para sair)..." -ForegroundColor Green
        Get-Content -Path $targetLog -Tail 30 -Wait
    } else {
        Write-Host "[-] Arquivo de log '$targetLog' ainda não foi gerado." -ForegroundColor Yellow
    }
}

function Show-Menu {
    while ($true) {
        Clear-Host
        Write-Host "=================================================================" -ForegroundColor Cyan
        Write-Host "        PAINEL DE GERENCIAMENTO DO SERVIÇO SOFI" -ForegroundColor Cyan
        Write-Host "=================================================================" -ForegroundColor Cyan
        Show-Status
        Write-Host "-----------------------------------------------------------------" -ForegroundColor White
        Write-Host "1. Verificar Status"
        Write-Host "2. Iniciar Serviço (Start)"
        Write-Host "3. Parar Serviço (Stop)"
        Write-Host "4. Reiniciar Serviço (Restart)"
        Write-Host "5. Acompanhar Logs em Tempo Real (Tail-Logs)"
        Write-Host "6. Desinstalar Serviço (Uninstall)"
        Write-Host "0. Sair"
        Write-Host "-----------------------------------------------------------------" -ForegroundColor White
        
        $opt = Read-Host "Selecione uma opção [0-6]"
        switch ($opt) {
            "1" { Show-Status; Read-Host "`nPressione Enter para continuar" }
            "2" { Start-SOFI; Read-Host "`nPressione Enter para continuar" }
            "3" { Stop-SOFI; Read-Host "`nPressione Enter para continuar" }
            "4" { Restart-SOFI; Read-Host "`nPressione Enter para continuar" }
            "5" { Tail-Logs }
            "6" { Uninstall-SOFI; Read-Host "`nPressione Enter para continuar" }
            "0" { exit }
            default { Write-Host "Opção inválida!" -ForegroundColor Red; Start-Sleep -Seconds 1 }
        }
    }
}

# Execução baseada no parâmetro CLI
switch ($Action) {
    "status"    { Show-Status }
    "start"     { Start-SOFI }
    "stop"      { Stop-SOFI }
    "restart"   { Restart-SOFI }
    "uninstall" { Uninstall-SOFI }
    "tail-logs" { Tail-Logs }
    "menu"      { Show-Menu }
}
