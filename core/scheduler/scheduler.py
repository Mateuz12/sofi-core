"""
scheduler.py — Scheduler automático dos relatórios Extranet (SOFI).

Carrega os jobs definidos em scheduler_config.json e os executa via
APScheduler (BackgroundScheduler) com timezone America/Sao_Paulo.

Lógica de retry:
  - exit code 0  → SUCESSO
  - exit code 1  → FALHA TRANSITÓRIA (Playwright) → retry até max_attempts
  - exit code 2  → FALHA PERMANENTE (dados vazios) → sem retry

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

def run_job(job_config: dict) -> None:
    """
    Executa um job via subprocess com loop interno de retry.

    A data D-1 é calculada uma única vez no início e mantida
    constante em todas as tentativas (comportamento intencional).
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
            _log("SUCESSO", f"Job '{name}' concluído com sucesso (tentativa {tentativa}).", modulo="Scheduler")
            print(f"[Scheduler] '{name}' SUCESSO na tentativa {tentativa}.")
            return

        if rc == EXIT_PERMANENT:
            _log("ERRO", f"Job '{name}' — FALHA PERMANENTE (dados vazios). Sem retry.", modulo="Scheduler")
            print(f"[Scheduler] '{name}' FALHA PERMANENTE — sem retry.")
            return

        # rc == EXIT_RETRYABLE (ou outro código inesperado)
        msg = f"Job '{name}' — FALHA TRANSITÓRIA (exit code {rc}), tentativa {tentativa}/{max_attempts}."
        _log("AVISO", msg, modulo="Scheduler")
        print(f"[Scheduler] {msg}")

        if tentativa < max_attempts:
            print(f"[Scheduler] Aguardando {delay_s}s antes da próxima tentativa...")
            time.sleep(delay_s)

    # Esgotou todas as tentativas
    _log(
        "ERRO",
        f"Job '{name}' — FALHA DEFINITIVA. {max_attempts}/{max_attempts} tentativas esgotadas.",
        modulo="Scheduler",
    )
    print(f"[Scheduler] '{name}' FALHA DEFINITIVA — {max_attempts} tentativas esgotadas.")

    # Placeholder de notificação por e-mail (não implementado no MVP)
    email = job_config.get("notification", {}).get("email")
    if email:
        send_alert(email, name, f"Falha após {max_attempts} tentativas.")


# ─────────────────────────────────────────────
# Notificação (placeholder)
# ─────────────────────────────────────────────

def send_alert(email: str, job_name: str, error: str) -> None:
    """
    Placeholder para envio de alerta por e-mail.
    Não implementado no MVP — registra apenas um log de aviso.
    """
    _log(
        "AVISO",
        f"[send_alert] e-mail para '{email}' sobre '{job_name}': {error} — NÃO IMPLEMENTADO.",
        modulo="Scheduler",
    )
    print(f"[Scheduler] send_alert: {email} | {job_name} | {error} (não implementado)")


# ─────────────────────────────────────────────
# Inicialização e status do scheduler
# ─────────────────────────────────────────────

_scheduler_instance: "BackgroundScheduler | None" = None
_jobs_meta: list[dict] = []  # cache de metadados dos jobs para get_scheduler_status()


def start_scheduler() -> "BackgroundScheduler | None":
    """
    Cria, configura e inicia o BackgroundScheduler.

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

    _jobs_meta = []

    for job_cfg in config.get("jobs", []):
        if not job_cfg.get("enabled", True):
            print(f"[Scheduler] Job '{job_cfg['name']}' desabilitado — ignorado.")
            continue

        sched = job_cfg["schedule"]
        if sched["type"] != "cron":
            print(f"[Scheduler] Tipo '{sched['type']}' não suportado para '{job_cfg['name']}'. Ignorado.")
            continue

        scheduler.add_job(
            func=run_job,
            trigger="cron",
            hour=sched["hour"],
            minute=sched["minute"],
            args=[job_cfg],
            id=job_cfg["name"],
            name=job_cfg["name"],
            max_instances=1,
            replace_existing=True,
        )

        _jobs_meta.append({
            "name": job_cfg["name"],
            "hour": sched["hour"],
            "minute": sched["minute"],
        })

        print(f"[Scheduler] Job registrado: '{job_cfg['name']}' às {sched['hour']:02d}:{sched['minute']:02d} ({tz})")

    # Listener para capturar exceções inesperadas no próprio scheduler.py
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

    _log("INFO", f"Scheduler iniciado. Jobs: {[j['name'] for j in _jobs_meta]}", modulo="Scheduler")
    print(f"[Scheduler] Iniciado com {len(_jobs_meta)} job(s).")

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
            "next_job": str,   # ex: "BH 09:00" ou "—"
            "jobs": [{"name": str, "hour": int, "minute": int}, ...]
        }
    """
    running = bool(_scheduler_instance and _scheduler_instance.running)

    next_job = "—"
    if running and _jobs_meta:
        now = datetime.now()
        candidates = []
        for j in _jobs_meta:
            # Próxima ocorrência hoje ou amanhã
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
