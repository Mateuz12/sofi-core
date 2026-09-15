# 🛠️ Integração NSSM (Windows Service Manager)

> **Status:** Ativo / Produção  
> **Versão:** 1.0.0  
> **Camada:** [[core_infraestrutura]] / Operações de Host  

---

## 🎯 1. Objetivo da Integração

O **NSSM (Non-Sucking Service Manager)** é utilizado no SOFI para encapsular a execução do **Streamlit Hub (`dashboard/app.py`)** e do **APScheduler (`core/scheduler/scheduler.py`)** como um **Serviço Nativo do Windows (`SOFI-Service`)**.

Essa arquitetura garante:
1. **Operação 24/7 ininterrupta:** O serviço roda em background sem necessidade de usuário logado na sessão interativa do Windows.
2. **Resiliência a Falhas:** Em caso de exceção não tratada, crash de memória ou reinicialização do Windows Server, o NSSM reinicia automaticamente a aplicação.
3. **Gestão Transparente de Logs:** Redirecionamento e rotação automática dos fluxos `stdout` e `stderr` para evitar estouro de disco.

---

## ⚙️ 2. Parâmetros do Serviço (`SOFI-Service`)

| Parâmetro | Valor Configurado | Descrição |
| :--- | :--- | :--- |
| **Nome do Serviço** | `SOFI-Service` | Identificador do serviço no Windows Service Control Manager (`services.msc`). |
| **Executável Base** | `tools/nssm/nssm.exe` | Versão 2.24 x64 empacotada no repositório local. |
| **Script de Entrada (`App`)** | `<raiz_projeto>\deploy\run_service.bat` | Script wrapper que orquestra a inicialização paralela do ngrok e do Streamlit. |
| **Túnel ngrok** | `C:\ngrok\ngrok.exe http 8501` | Inicialização automática do túnel seguro para a porta do Streamlit (8501). |
| **Path do Python** | `<raiz_projeto>\.venv\Scripts\python.exe` | Interpretador do ambiente virtual isolado (com fallback automático para AppData). |
| **Argumentos Streamlit** | `-m streamlit run dashboard/app.py --server.port 8501 --server.headless true --server.address 0.0.0.0` | Inicialização em modo headless e escuta em todas as interfaces de rede. |
| **Diretório de Trabalho (`AppDirectory`)** | `<raiz_projeto>` | Garantia de resolução de caminhos relativos e carregamento do `.env`. |
| **Log Stdout (`AppStdout`)** | `<raiz_projeto>\logs\service_stdout.log` | Captura de prints do sistema e logs de inicialização. |
| **Log Stderr (`AppStderr`)** | `<raiz_projeto>\logs\service_stderr.log` | Captura de tracebacks e erros não capturados. |
| **Rotação de Logs (`AppRotateBytes`)** | `10485760` (10 MB) | Rotação automática ao atingir 10 MB. |
| **Tipo de Inicialização** | `SERVICE_AUTO_START` | Inicialização automática junto com o Windows Server. |

---

## 🚀 3. Procedimentos Operacionais Padrão (POP)

Os scripts PowerShell em `deploy/` automatizam todo o ciclo de vida do serviço:

### 3.1 Instalação Inicial
```powershell
# Executar em terminal PowerShell (solicita UAC se não for Administrador)
.\deploy\install_service.ps1
```

### 3.2 Gerenciamento Diário (Painel Interativo)
```powershell
.\deploy\manage_service.ps1
```

### 3.3 Comandos Rápidos via CLI
- **Verificar Status:** `.\deploy\manage_service.ps1 status`
- **Iniciar Serviço:** `.\deploy\manage_service.ps1 start`
- **Parar Serviço:** `.\deploy\manage_service.ps1 stop`
- **Reiniciar Serviço:** `.\deploy\manage_service.ps1 restart`
- **Acompanhar Logs:** `.\deploy\manage_service.ps1 tail-logs`
- **Desinstalar Serviço:** `.\deploy\manage_service.ps1 uninstall`

---

## ⚠️ 4. Problemas Conhecidos / Boas Práticas (Gambiarras Intencionais)

1. **Permissões UAC / Elevadas:**
   - O NSSM exige privilégios de Administrador do Windows para criar/alterar serviços no Registro (`HKLM\SYSTEM\CurrentControlSet\Services`).
   - *Solução:* `install_service.ps1` e `manage_service.ps1` possuem auto-elevação via `Start-Process powershell -Verb RunAs`.

2. **Dependência do Ambiente Virtual (`.venv`):**
   - O serviço depende dos caminhos absolutos e das dependências instaladas no `.venv`. Se a pasta do projeto for movida de diretório, o serviço deve ser desinstalado e reinstalado via `install_service.ps1`.

3. **Mapeamentos de Rede SMB (`Z:\` e `T:\`) em Serviços Windows:**
   - Serviços do Windows rodam na Sessão 0 (`Session 0 Isolation`). Unidades mapeadas por letra de disco no login interativo do usuário (ex: `Z:\`) não ficam visíveis nativamente para o serviço do Windows a menos que utilizadas via caminhos UNC (`\\srv-dc01\File Server\`) ou remapeadas no contexto de serviço.

4. **Porta 8501 em Uso:**
   - Ao reiniciar o serviço, certifique-se de que o processo Python anterior encerrou completamente para liberar a porta 8501. O NSSM aguarda o encerramento do processo filho antes de subir uma nova instância.

---

## 🔗 Veja Também
- [[overview]]: Arquitetura geral do sistema.
- [[architecture]]: Conceito de desacoplamento e resiliência 24/7.
- [[modulo_dashboard_hub]]: Dashboard Streamlit monitorado pelo serviço.
- [[modulo_scheduler]]: Orquestrador APScheduler rodando junto ao Streamlit.
