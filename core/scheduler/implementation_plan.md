# Implementation Plan — Scheduler Extranet (SOFI)

> **Revisão 2 — 09/06/2026**: Corrigido singleton via `st.cache_resource`, retry por loop interno, timezone explícito, hot reload definido.

## 1. Visão Geral

Agendamento automático dos relatórios Extranet (Financeiro BH e UDI) usando APScheduler integrado ao Streamlit Dashboard. Execução diária às 09:00 (BH) e 09:15 (UDI), com retry automático e logging centralizado no `sofi.db`.

---

## 2. Decisões de Design

| Decisão | Escolha |
|---|---|
| Mecanismo de scheduling | APScheduler (`BackgroundScheduler`) |
| Scripts agendados | Somente Financeiro BH e UDI |
| Frequência | Diário, 365 dias/ano |
| Horário | BH 09:00, UDI 09:15 |
| Timezone | `America/Sao_Paulo` (explícito no config e no APScheduler) |
| Ordem | Sequencial por horário (jobs independentes) |
| Data de referência | Sempre D-1, congelada no 1º disparo |
| Período | Sempre `--dias 5` (D-5 a D-1) |
| Retry | 3 tentativas, intervalo 120s, **loop interno** na função do job |
| Retry — erros de Playwright | Sim (exit code 1) |
| Retry — dados vazios | Não (exit code 2) |
| Conflito de execução | Skip (APScheduler `max_instances=1`) |
| Persistência | MemoryJobStore |
| Localização | `core/scheduler/` |
| Configuração | `scheduler_config.json` (versionado) |
| Integração com dashboard | `st.cache_resource` singleton + badge no topbar |
| Logging | `sofi.db` via `@log_execution` (2 camadas: scheduler + script) |
| Notificação (MVP) | Placeholder — campo `email: null` no config (não implementado) |
| Processo 24/7 | Background thread dentro do Streamlit (singleton garantido) |
| Hot reload do config | Não — alterações no JSON exigem restart do Streamlit |

---

## 3. Estrutura de Arquivos

```
core/scheduler/
  __init__.py               # exporta start_scheduler()
  scheduler.py              # APScheduler, lógica de jobs, retry, subprocess
  scheduler_config.json     # configuração de jobs (versionado)

Arquivos a alterar:
  departments/financeiro/modules/extranet/BH/extranet_reports_bh.py
  departments/financeiro/modules/extranet/UDI/extranet_reports_udi.py
  dashboard/app.py
  dashboard/components/layout.py
```

---

## 4. scheduler_config.json

```json
{
  "enabled": true,
  "timezone": "America/Sao_Paulo",
  "jobs": [
    {
      "name": "Extranet BH",
      "enabled": true,
      "script": "departments/financeiro/modules/extranet/BH/extranet_reports_bh.py",
      "schedule": { "type": "cron", "hour": 9, "minute": 0 },
      "dias": 5,
      "retry": { "max_attempts": 3, "delay_seconds": 120 },
      "notification": { "email": null }
    },
    {
      "name": "Extranet UDI",
      "enabled": true,
      "script": "departments/financeiro/modules/extranet/UDI/extranet_reports_udi.py",
      "schedule": { "type": "cron", "hour": 9, "minute": 15 },
      "dias": 5,
      "retry": { "max_attempts": 3, "delay_seconds": 120 },
      "notification": { "email": null }
    }
  ]
}
```

### Campo `notification.email`
- `null` → placeholder. **Nenhuma notificação será enviada** (funcionalidade não implementada no MVP).
- String com e-mail → hook para implementação futura de alerta via Outlook.

### Campo `timezone`
- Define o fuso horário usado pelo APScheduler para disparar os jobs.
- Obrigatório. Deve ser um timezone válido do `pytz` / `zoneinfo`.

---

## 5. scheduler.py — Arquitetura

### 5.1 Fluxo de execução de um job (loop interno de retry)

> **Importante**: O retry é implementado como um **loop `for` dentro da função do job**, e não via listener de evento do APScheduler. Isso porque `subprocess.run()` não levanta exceção ao retornar exit code ≠ 0 — ele simplesmente retorna o `returncode`. Usar listener de `EVENT_JOB_ERROR` não capturaria essas falhas.

```
job disparado (09:00)
  │
  ├─ Calcula D-1 (datetime.now() - 1 dia), congela
  ├─ for tentativa in range(1, max_attempts + 1):
  │     ├─ Monta CLI: python <script> --data <D-1> --dias 5
  │     ├─ Executa subprocess.run()
  │     │
  │     ├─ exit code 0 → SUCESSO
  │     │     └─ Loga no sofi.db: "SUCESSO"
  │     │     └─ return (encerra loop)
  │     │
  │     ├─ exit code 2 (dados vazios) → FALHA PERMANENTE
  │     │     └─ Loga: "FALHA PERMANENTE — sem retry"
  │     │     └─ return (encerra loop, não faz retry)
  │     │
  │     └─ exit code 1 (Playwright/transitório) → RETRY
  │           ├─ Loga: "FALHA TRANSITÓRIA — tentativa X/3"
  │           └─ time.sleep(120) se não for última tentativa
  │
  └─ Se esgotou tentativas:
        └─ Loga: "FALHA DEFINITIVA — 3/3 tentativas esgotadas"
```

### 5.2 APScheduler — configuração

- **`max_instances=1`** por job para evitar execuções simultâneas
- **Timezone**: carregado do `scheduler_config.json` (`America/Sao_Paulo`)
- **Listener `EVENT_JOB_ERROR`**: registrado apenas para capturar **exceções inesperadas** (erros no próprio `scheduler.py`, não nos scripts). Loga o traceback no `sofi.db`.
- Se `notification.email` != null → chama `send_alert()` (placeholder, não implementado no MVP)

### 5.3 Funções principais

```python
def load_config(path: Path) -> dict
def start_scheduler() -> BackgroundScheduler
def stop_scheduler()
def get_scheduler_status() -> dict        # para o badge do Streamlit
def run_job(job_config: dict) -> None     # loop interno de retry + subprocess
def send_alert(email: str, job_name: str, error: str)  # placeholder (não implementado)
```

### 5.4 Integração com Streamlit

> **Crítico**: O Streamlit re-executa o script `app.py` a cada interação do usuário e a cada aba do navegador. Sem `st.cache_resource`, um novo `BackgroundScheduler` seria criado a cada vez, duplicando jobs.

```python
# dashboard/app.py
import streamlit as st
from core.scheduler import start_scheduler

@st.cache_resource
def _get_scheduler():
    """Singleton — garante que só existe um scheduler por processo Streamlit."""
    return start_scheduler()

scheduler = _get_scheduler()
```

```python
# dashboard/components/layout.py (topbar)
from core.scheduler import get_scheduler_status

status = get_scheduler_status()
if status["running"]:
    st.markdown(f"🟢 Scheduler: OK | Próx: {status['next_job']}")
else:
    st.markdown("🔴 Scheduler: PAUSADO")
```

---

## 6. Exit Codes nos Scripts BH/UDI

### 6.1 Adicionar ao topo de cada script

```python
EXIT_OK = 0
EXIT_RETRYABLE = 1
EXIT_PERMANENT = 2
```

### 6.2 Alterar `if __name__ == "__main__"`

```python
if __name__ == "__main__":
    try:
        main()
        sys.exit(EXIT_OK)
    except RuntimeError as e:
        msg = str(e).upper()
        if "EM BRANCO" in msg or "VAZIO" in msg:
            sys.exit(EXIT_PERMANENT)
        sys.exit(EXIT_RETRYABLE)
    except Exception:
        sys.exit(EXIT_RETRYABLE)
```

---

## 7. Integração com sofi.db

### 7.1 Logs existentes (não alterar)

Cada script já grava em `execution_logs` via `@log_execution(modulo="Extranet BH")` / `@log_execution(modulo="Extranet UDI")`:
- `status = "INICIADO"` ao começar
- `status = "SUCESSO"` ao terminar
- `status = "ERRO"` em caso de exceção

### 7.2 Log do scheduler (camada de orquestração)

O próprio `scheduler.py` usará **chamadas diretas** ao `sofi.db` (não o decorator `@log_execution`, pois precisa logar eventos granulares) com `modulo="Scheduler"` para registrar eventos de orquestração:
- "Job Extranet BH disparado com data D-1=XX/XX/XXXX"
- "Retry 2/3 para Extranet BH"
- "Falha permanente em Extranet UDI: dados vazios"

> **Nota — Logs duplos (intencional)**: Cada execução gera **2 registros** no `execution_logs`:
> 1. **Camada script**: gravado pelo `@log_execution` dentro do próprio script (ex: `modulo="Extranet BH"`).
> 2. **Camada scheduler**: gravado pelo `scheduler.py` (ex: `modulo="Scheduler"`).
>
> Isso é **intencional** — permite rastrear tanto o resultado do script quanto a decisão do scheduler (retry, skip, etc.).

### 7.3 Leitura pelo dashboard

A página `/extranet` já consulta `execution_logs` e exibirá automaticamente tanto os logs dos scripts quanto os do scheduler. O filtro por `modulo` permite separar as camadas se necessário.

---

## 8. Dependências

```text
APScheduler>=3.10.0   # adicionar ao requirements.txt (se existir)
```

Nenhuma outra dependência nova. `subprocess`, `json`, `datetime`, `pathlib` são stdlib.

---

## 9. Teste Manual

Ao final da implementação, iniciar o Streamlit e verificar:
1. Badge do topbar aparece verde com status
2. Job BH dispara e loga no `sofi.db`
3. Job UDI dispara e loga no `sofi.db`
4. Exit code 2 (simulado) não gera retry
5. Exit code 1 (simulado) gera retry 3x
6. `scheduler_config.json` com `enabled: false` pausa todos os jobs

---

## 10. Próximos Passos (fora do escopo MVP)

- Implementar `send_alert()` com envio real de e-mail via Outlook
- Página dedicada "Agendamentos" no dashboard
- Adicionar suporte a outros módulos (Retaguarda, Compras/MAR)
- Toggle de pausar/retomar via botão no dashboard
