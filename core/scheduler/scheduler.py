"""
scheduler.py — Scheduler automático dos relatórios Extranet (SOFI).

Carrega os jobs definidos em scheduler_config.json e os executa via
APScheduler (BackgroundScheduler) com timezone America/Sao_Paulo.

Lógica de retry:
  - exit code 0  → SUCESSO
  - exit code 1  → FALHA TRANSITÓRIA (Playwright) → retry até max_attempts
  - exit code 2  → FALHA PERMANENTE (dados vazios) → sem retry

Ao final de todos os jobs, envia e-mail consolidado via Gmail SMTP
(core/notifier/smtp_notifier.py) para os destinatários configurados em
SCHEDULER_NOTIFY_EMAILS no .env.

Integração com Streamlit via st.cache_resource (singleton garantido).
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# Resolução da raiz do projeto
# ─────────────────────────────────────────────

_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
load_sofi_env()

import os
_DB_PATH = _ROOT / os.getenv("LOG_DB_PATH", "core/database/sofi.db")

# ─────────────────────────────────────────────
# APScheduler
# ─────────────────────────────────────────────

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
    _APSCHEDULER_OK = True
except ImportError:
    _APSCHEDULER_OK = False

# ─────────────────────────────────────────────
# Exit codes
# ─────────────────────────────────────────────

EXIT_OK        = 0
EXIT_RETRYABLE = 1
EXIT_PERMANENT = 2

# ─────────────────────────────────────────────
# Utilitários de log no sofi.db
# ─────────────────────────────────────────────

def _log(status: str, mensagem: str, modulo: str = "Scheduler") -> None:
    """Grava um registro diretamente em execution_logs (sem decorator)."""
    try:
        import getpass
        usuario = getpass.getuser()
        with sqlite3.connect(str(_DB_PATH), timeout=10.0) as conn:
            conn.execute(
                "INSERT INTO execution_logs (modulo, status, mensagem, usuario) VALUES (?, ?, ?, ?)",
                (modulo, status, mensagem, usuario),
            )
    except Exception as exc:
        print(f"[Scheduler] Erro ao gravar log: {exc}")


# ─────────────────────────────────────────────
# Carregamento de config
# ─────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).resolve().parent / "scheduler_config.json"


def load_config(path: Path = _CONFIG_PATH) -> dict:
    """Lê e retorna o conteúdo de scheduler_config.json."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# Lógica de execução de um job (loop de retry)
# ─────────────────────────────────────────────

def run_job(job_config: dict) -> dict:
    """
    Executa um job via subprocess com loop interno de retry.

    A data D-1 é calculada uma única vez no início e mantida
    constante em todas as tentativas (comportamento intencional).

    Returns:
        dict com chaves:
            - name          (str)  — nome do job
            - status        (str)  — "SUCESSO" | "ERRO" | "FALHA PERMANENTE"
            - tentativas    (int)  — tentativas realizadas
            - duracao       (str)  — duração formatada "Xm Ys"
            - mensagem_erro (str)  — descrição do erro (vazio se SUCESSO)
    """
    name         = job_config["name"]
    script       = _ROOT / job_config["script"]
    dias         = job_config.get("dias", 5)
    max_attempts = job_config["retry"]["max_attempts"]
    delay_s      = job_config["retry"]["delay_seconds"]

    # Congela D-1 no momento do disparo
    target_date = datetime.now() - timedelta(days=1)
    date_str    = target_date.strftime("%d/%m/%Y")

    _log("INFO", f"Job '{name}' disparado. Data D-1={date_str}", modulo="Scheduler")
    print(f"[Scheduler] Iniciando '{name}' | D-1={date_str} | dias={dias}")

    cmd = [sys.executable, str(script), "--data", date_str, "--dias", str(dias)]
    if "unidade" in job_config:
        cmd.extend(["--unidade", str(job_config["unidade"])])

    inicio = datetime.now()

    for tentativa in range(1, max_attempts + 1):
        print(f"[Scheduler] '{name}' — tentativa {tentativa}/{max_attempts}")
        try:
            result = subprocess.run(cmd, check=False)
            rc = result.returncode
        except Exception as exc:
            _log("ERRO", f"Exceção ao executar '{name}': {exc}", modulo="Scheduler")
            print(f"[Scheduler] Exceção inesperada em '{name}': {exc}")
            rc = EXIT_RETRYABLE

        if rc == EXIT_OK:
            duracao = _formatar_duracao(inicio)
            _log("SUCESSO", f"Job '{name}' concluído com sucesso (tentativa {tentativa}).", modulo="Scheduler")
            print(f"[Scheduler] '{name}' SUCESSO na tentativa {tentativa}.")
            return {
                "name": name,
                "status": "SUCESSO",
                "tentativas": tentativa,
                "duracao": duracao,
                "mensagem_erro": "",
            }

        if rc == EXIT_PERMANENT:
            duracao = _formatar_duracao(inicio)
            msg = f"Job '{name}' — FALHA PERMANENTE (dados vazios). Sem retry."
            _log("ERRO", msg, modulo="Scheduler")
            print(f"[Scheduler] '{name}' FALHA PERMANENTE — sem retry.")
            return {
                "name": name,
                "status": "FALHA PERMANENTE",
                "tentativas": tentativa,
                "duracao": duracao,
                "mensagem_erro": msg,
            }

        # EXIT_RETRYABLE (ou código inesperado)
        msg = f"Job '{name}' — FALHA TRANSITÓRIA (exit code {rc}), tentativa {tentativa}/{max_attempts}."
        _log("AVISO", msg, modulo="Scheduler")
        print(f"[Scheduler] {msg}")

        if tentativa < max_attempts:
            print(f"[Scheduler] Aguardando {delay_s}s antes da próxima tentativa...")
            time.sleep(delay_s)

    # Esgotou todas as tentativas
    duracao = _formatar_duracao(inicio)
    msg_final = f"Job '{name}' — FALHA DEFINITIVA. {max_attempts}/{max_attempts} tentativas esgotadas."
    _log("ERRO", msg_final, modulo="Scheduler")
    print(f"[Scheduler] '{name}' FALHA DEFINITIVA — {max_attempts} tentativas esgotadas.")

    return {
        "name": name,
        "status": "ERRO",
        "tentativas": max_attempts,
        "duracao": duracao,
        "mensagem_erro": msg_final,
    }


def _formatar_duracao(inicio: datetime) -> str:
    """Retorna a duração desde `inicio` formatada como 'Xm Ys'."""
    delta = datetime.now() - inicio
    total = int(delta.total_seconds())
    minutos, segundos = divmod(total, 60)
    return f"{minutos}m {segundos}s"


# ─────────────────────────────────────────────
# Execução consolidada de todos os jobs
# ─────────────────────────────────────────────

def run_all_jobs(jobs_configs: list[dict]) -> None:
    """
    Executa todos os jobs sequencialmente (incluindo desabilitados como registro),
    coleta os resultados e envia e-mail consolidado ao final via Gmail SMTP.

    Chamado pelo APScheduler como job único para garantir que a notificação
    só seja enviada após todos os jobs terminarem.
    """
    import traceback

    config = load_config()
    notif_cfg = config.get("notification", {})

    nomes = [j["name"] for j in jobs_configs]
    _log("INFO", f"run_all_jobs iniciado. Jobs configurados: {nomes}", modulo="Scheduler")
    print(f"[Scheduler] run_all_jobs iniciado. Jobs: {nomes}")

    resultados: list[dict] = []

    for job_cfg in jobs_configs:
        name = job_cfg["name"]
        
        if not job_cfg.get("enabled", True):
            # Registra como desabilitado sem executar
            resultados.append({
                "name": name,
                "status": "DESABILITADO",
                "tentativas": 0,
                "duracao": "—",
                "mensagem_erro": "",
            })
            print(f"[Scheduler] Job '{name}' desabilitado — ignorado.")
            continue

        try:
            resultado = run_job(job_cfg)
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"Exceção não capturada no job '{name}': {exc}\n{tb}"
            _log("ERRO", msg, modulo="Scheduler")
            print(f"[Scheduler] EXCEÇÃO NÃO CAPTURADA em '{name}': {exc}")
            resultado = {
                "name": name,
                "status": "ERRO",
                "tentativas": 0,
                "duracao": "—",
                "mensagem_erro": msg,
            }
        resultados.append(resultado)

    # ── Resumo ──
    resumo = ", ".join(f"{r['name']}={r['status']}" for r in resultados)
    _log("INFO", f"run_all_jobs concluído. Resultados: {resumo}", modulo="Scheduler")
    print(f"[Scheduler] run_all_jobs concluído. Resultados: {resumo}")

    # ── Decide se envia o e-mail ──
    if not notif_cfg.get("enabled", True):
        print("[Scheduler] Notificações desabilitadas no config. E-mail não enviado.")
        return

    tem_erro = any(r["status"] not in ("SUCESSO", "DESABILITADO") for r in resultados)

    deve_enviar = (
        (tem_erro and notif_cfg.get("send_on_error", True)) or
        (not tem_erro and notif_cfg.get("send_on_success", True))
    )

    if not deve_enviar:
        print("[Scheduler] Condição de notificação não atingida. E-mail não enviado.")
        return

    # ── Envia notificação ──
    try:
        from core.notifier import send_scheduler_notification
        send_scheduler_notification(resultados)
    except Exception as exc:
        # Garante que falha na notificação nunca derruba o scheduler
        _log("ERRO", f"Erro inesperado ao enviar notificação: {exc}", modulo="Scheduler")
        print(f"[Scheduler] Erro inesperado ao enviar notificação: {exc}")


# ─────────────────────────────────────────────
# Notificação (mantida para compatibilidade de API)
# ─────────────────────────────────────────────

def send_alert(email: str, job_name: str, error: str) -> None:
    """
    Acionada para alerta pontual de um job específico.
    Registra o evento no banco; o e-mail consolidado é enviado por run_all_jobs().
    """
    _log(
        "AVISO",
        f"[send_alert] Alerta gerado para '{job_name}': {error}",
        modulo="Scheduler",
    )
    print(f"[Scheduler] send_alert registrado: {job_name} | {error}")


# ─────────────────────────────────────────────
# Inicialização e status do scheduler
# ─────────────────────────────────────────────

_scheduler_instance: "BackgroundScheduler | None" = None
_jobs_meta: list[dict] = []  # cache de metadados dos jobs para get_scheduler_status()


def start_scheduler() -> "BackgroundScheduler | None":
    """
    Cria, configura e inicia o BackgroundScheduler.

    Agenda run_all_jobs() no horário do primeiro job habilitado,
    passando todos os configs (habilitados e desabilitados) para que
    o e-mail consolidado inclua todos eles.

    Deve ser chamado via st.cache_resource para garantir singleton:

        @st.cache_resource
        def _get_scheduler():
            from core.scheduler import start_scheduler
            return start_scheduler()

    Retorna None se APScheduler não estiver instalado ou se o
    scheduler estiver desabilitado no config.
    """
    global _scheduler_instance, _jobs_meta

    if not _APSCHEDULER_OK:
        print("[Scheduler] APScheduler não instalado. Instale com: pip install apscheduler")
        return None

    config = load_config()

    if not config.get("enabled", True):
        print("[Scheduler] Scheduler desabilitado no config.")
        return None

    tz = config.get("timezone", "America/Sao_Paulo")
    scheduler = BackgroundScheduler(timezone=tz)

    all_jobs = config.get("jobs", [])
    _jobs_meta = []

    # Agrupa jobs por horário (hora e minuto)
    schedule_groups: dict[tuple[int, int], list[dict]] = {}
    for job_cfg in all_jobs:
        j_sched = job_cfg.get("schedule", {})
        h = j_sched.get("hour", 8)
        m = j_sched.get("minute", 0)
        schedule_groups.setdefault((h, m), []).append(job_cfg)

    if not schedule_groups:
        print("[Scheduler] Nenhum job configurado. Scheduler não iniciado.")
        return None

    # Agenda cada grupo no APScheduler para seu respectivo horário
    for (h, m), group_jobs in schedule_groups.items():
        enabled_count = sum(1 for j in group_jobs if j.get("enabled", True))
        if enabled_count == 0:
            continue

        job_id = f"sofi_jobs_{h:02d}_{m:02d}"
        scheduler.add_job(
            func=run_all_jobs,
            trigger="cron",
            hour=h,
            minute=m,
            args=[group_jobs],
            id=job_id,
            name=f"SOFI Jobs {h:02d}:{m:02d}",
            max_instances=1,
            replace_existing=True,
        )
        print(f"[Scheduler] Jobs agendados para {h:02d}:{m:02d} ({tz}): {[j['name'] for j in group_jobs if j.get('enabled', True)]}")

    # Monta metadados para get_scheduler_status() — apenas habilitados
    for job_cfg in all_jobs:
        if not job_cfg.get("enabled", True):
            continue
        j_sched = job_cfg.get("schedule", {})
        _jobs_meta.append({
            "name": job_cfg["name"],
            "hour": j_sched.get("hour", 8),
            "minute": j_sched.get("minute", 0),
        })

    # Listener para exceções internas do APScheduler
    def _on_job_error(event):
        _log(
            "ERRO",
            f"Exceção inesperada no job '{event.job_id}': {event.exception}",
            modulo="Scheduler",
        )
        print(f"[Scheduler] Exceção inesperada capturada pelo listener: {event.exception}")

    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    scheduler.start()
    _scheduler_instance = scheduler

    _log("INFO", f"Scheduler iniciado. Jobs: {[j['name'] for j in all_jobs]}", modulo="Scheduler")
    print(f"[Scheduler] Iniciado com {len(all_jobs)} job(s) configurado(s).")

    return scheduler


def stop_scheduler() -> None:
    """Para o BackgroundScheduler, se estiver rodando."""
    global _scheduler_instance
    if _scheduler_instance and _scheduler_instance.running:
        _scheduler_instance.shutdown(wait=False)
        _log("INFO", "Scheduler encerrado.", modulo="Scheduler")
        print("[Scheduler] Encerrado.")
    _scheduler_instance = None


def get_scheduler_status() -> dict:
    """
    Retorna um dict com o status atual do scheduler para exibição no badge do topbar.

    Retorno:
        {
            "running": bool,
            "next_job": str,   # ex: "SOFI Daily Jobs 09:00" ou "—"
            "jobs": [{"name": str, "hour": int, "minute": int}, ...]
        }
    """
    running = bool(_scheduler_instance and _scheduler_instance.running)

    next_job = "—"
    if running and _jobs_meta:
        now = datetime.now()
        candidates = []
        for j in _jobs_meta:
            candidate = now.replace(hour=j["hour"], minute=j["minute"], second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            candidates.append((candidate, j))
        candidates.sort(key=lambda x: x[0])
        _, nxt = candidates[0]
        next_job = f"{nxt['name']} {nxt['hour']:02d}:{nxt['minute']:02d}"

    return {
        "running": running,
        "next_job": next_job,
        "jobs": list(_jobs_meta),
    }
