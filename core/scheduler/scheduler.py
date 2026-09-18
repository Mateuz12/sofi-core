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

EXIT_OK              = 0
EXIT_RETRYABLE       = 1
EXIT_PERMANENT       = 2
EXIT_SEM_FATURAMENTO = 3

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
    """Lê e retorna a configuração do scheduler, priorizando ConfigManager (YAML)."""
    try:
        from core.config.config_manager import ConfigManager
        cfg = ConfigManager().get_scheduler_config()
        # Converte para dict compatível com a estrutura esperada
        notif_cfg = ConfigManager().get_notificacoes_config()
        groups = {}
        for gname, ginfo in notif_cfg.grupos.items():
            groups[gname] = {
                "emails": ginfo.emails,
                "jobs": ginfo.jobs_vinculados
            }
        data = cfg.model_dump()
        data["notification_groups"] = groups
        data["notification"] = {
            "send_on_success": notif_cfg.enviar_em_sucesso,
            "send_on_error": notif_cfg.enviar_em_erro
        }
        return data
    except Exception as e:
        # Fallback legado para scheduler_config.json
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        raise e


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
            - status        (str)  — "SUCESSO" | "SEM FATURAMENTO" | "ERRO" | "FALHA PERMANENTE"
            - tentativas    (int)  — tentativas realizadas
            - duracao       (str)  — duração formatada "Xm Ys"
            - mensagem_erro (str)  — descrição do erro (vazio se SUCESSO/SEM FATURAMENTO)
    """
    name         = job_config["name"]
    script       = _ROOT / job_config["script"]
    dias         = job_config.get("dias", 5)
    max_attempts = job_config["retry"]["max_attempts"]
    delay_s      = job_config["retry"]["delay_seconds"]

    # Calcula a data de referência respeitando a configuração do job (D-0 para DFC, D-1 para Retaguarda/Extranet)
    offset_dias = job_config.get("offset_dias", 0 if dias == 0 else 1)
    target_date = datetime.now() - timedelta(days=offset_dias)
    date_str    = target_date.strftime("%d/%m/%Y")

    _log("INFO", f"Job '{name}' disparado. Data de Referência={date_str}", modulo="Scheduler")
    print(f"[Scheduler] Iniciando '{name}' | Ref={date_str} | dias={dias}")

    cmd = [sys.executable, str(script), "--data", date_str, "--dias", str(dias)]
    if job_config.get("unidade"):
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
            status_txt = "COM FATURAMENTO" if "xml" in name.lower() else "SUCESSO"
            _log("SUCESSO", f"Job '{name}' concluído com sucesso ({status_txt}) (tentativa {tentativa}).", modulo="Scheduler")
            print(f"[Scheduler] '{name}' {status_txt} na tentativa {tentativa}.")
            return {
                "name": name,
                "status": status_txt,
                "tentativas": tentativa,
                "duracao": duracao,
                "mensagem_erro": "",
            }

        if rc == EXIT_SEM_FATURAMENTO:
            duracao = _formatar_duracao(inicio)
            _log("INFO", f"Job '{name}' concluído sem novas notas faturadas (SEM FATURAMENTO).", modulo="Scheduler")
            print(f"[Scheduler] '{name}' concluído (SEM FATURAMENTO).")
            return {
                "name": name,
                "status": "SEM FATURAMENTO",
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
# Buffer de resultados por grupo de notificação
# ─────────────────────────────────────────────

import threading

_group_lock = threading.Lock()
# { "Retaguarda": { "pending": {"Fluxo Analítico DFC UDI", ...}, "results": [...] }, ... }
_group_buffers: dict[str, dict] = {}


def _get_group_jobs_list(group_data: list | dict) -> list[str]:
    """Retorna a lista de nomes de jobs contidos na definição do grupo."""
    if isinstance(group_data, list):
        return group_data
    if isinstance(group_data, dict):
        return group_data.get("jobs", [])
    return []


def _get_group_emails(group_data: list | dict) -> str | list[str] | None:
    """Retorna os destinatários de e-mail configurados para o grupo, se houver."""
    if isinstance(group_data, dict):
        return group_data.get("emails")
    return None


def _find_group(job_name: str, config: dict) -> str | None:
    """Retorna o nome do grupo de notificação ao qual o job pertence, ou None."""
    groups = config.get("notification_groups", {})
    for group_name, group_data in groups.items():
        jobs_list = _get_group_jobs_list(group_data)
        if job_name in jobs_list:
            return group_name
    return None


def _init_group_buffers(config: dict) -> None:
    """Inicializa os buffers de grupo para o ciclo do dia."""
    global _group_buffers
    groups = config.get("notification_groups", {})
    all_jobs = config.get("jobs", [])
    enabled_names = {j["name"] for j in all_jobs if j.get("enabled", True)}

    with _group_lock:
        _group_buffers = {}
        for group_name, group_data in groups.items():
            members = _get_group_jobs_list(group_data)
            active = {m for m in members if m in enabled_names}
            if active:
                _group_buffers[group_name] = {
                    "pending": set(active),
                    "results": [],
                }


def _get_or_create_group_buffer(group_name: str, config: dict) -> dict:
    """Garante a existência do buffer para um grupo, criando-o sob demanda se necessário."""
    global _group_buffers
    all_jobs = config.get("jobs", [])
    enabled_names = {j["name"] for j in all_jobs if j.get("enabled", True)}

    if group_name not in _group_buffers or not _group_buffers[group_name].get("pending"):
        groups = config.get("notification_groups", {})
        group_data = groups.get(group_name, {})
        members = _get_group_jobs_list(group_data)
        active = {m for m in members if m in enabled_names}
        _group_buffers[group_name] = {
            "pending": set(active),
            "results": [],
        }
    else:
        # Mantém apenas os jobs que continuam habilitados no config atual
        _group_buffers[group_name]["pending"] = {
            m for m in _group_buffers[group_name]["pending"] if m in enabled_names
        }

    return _group_buffers[group_name]


def _record_and_maybe_notify(job_name: str, resultado: dict, config: dict) -> None:
    """
    Registra o resultado de um job.
    - Se o job roda em horário isolado em relação aos outros jobs ativos do grupo,
      envia a notificação daquele job imediatamente.
    - Se compartilha horário com outros jobs do grupo, acumula e envia quando o grupo concluir.
    """
    notif_cfg = config.get("notification", {})
    group_name = _find_group(job_name, config)
    groups = config.get("notification_groups", {})
    group_data = groups.get(group_name) if group_name else None
    group_emails = _get_group_emails(group_data) if group_data else None

    if not group_name:
        # Job sem grupo: envia notificação individual
        _send_notification_if_needed([resultado], notif_cfg, group_name=job_name, group_emails=None)
        return

    # Mapeia os horários dos jobs ativos do grupo
    all_jobs = config.get("jobs", [])
    job_schedule_map = {}
    enabled_jobs = {}
    for j in all_jobs:
        if j.get("enabled", True):
            enabled_jobs[j["name"]] = j
            s = j.get("schedule", {})
            job_schedule_map[j["name"]] = (s.get("hour"), s.get("minute"))

    group_members = [m for m in _get_group_jobs_list(group_data) if m in enabled_jobs]
    current_job_sched = job_schedule_map.get(job_name)

    # Verifica se outros jobs ativos do grupo compartilham este mesmo horário
    same_time_members = {
        m for m in group_members if job_schedule_map.get(m) == current_job_sched
    }

    should_notify = False
    group_results = []

    with _group_lock:
        buf = _get_or_create_group_buffer(group_name, config)
        buf["results"].append(resultado)
        buf["pending"].discard(job_name)

        # Se o job é isolado no seu horário (nenhum outro job ativo do grupo roda neste horário)
        if len(same_time_members) <= 1:
            should_notify = True
            group_results = [resultado]
            # Remove o resultado do buffer global para não duplicar no consolidado de outros horários
            buf["results"] = [r for r in buf["results"] if r.get("name") != job_name]
        elif not buf["pending"]:
            # Todos os jobs do grupo terminaram
            should_notify = True
            members_order = _get_group_jobs_list(group_data)
            order_map = {name: i for i, name in enumerate(members_order)}
            group_results = sorted(
                buf["results"],
                key=lambda r: order_map.get(r["name"], 999)
            )
            _group_buffers.pop(group_name, None)

    if should_notify:
        resumo = ", ".join(f"{r['name']}={r['status']}" for r in group_results)
        _log("INFO", f"Notificação disparada para grupo '{group_name}'. Resultados: {resumo}", modulo="Scheduler")
        print(f"[Scheduler] Notificação disparada para grupo '{group_name}': {resumo}")
        _send_notification_if_needed(group_results, notif_cfg, group_name=group_name, group_emails=group_emails)


def _send_notification_if_needed(
    resultados: list[dict],
    notif_cfg: dict,
    group_name: str | None = None,
    group_emails: str | list[str] | None = None
) -> None:
    """Decide se envia e-mail e envia se necessário."""
    if not notif_cfg.get("enabled", True):
        print("[Scheduler] Notificacoes desabilitadas no config. E-mail nao enviado.")
        return

    tem_erro = any(r["status"] not in ("SUCESSO", "COM FATURAMENTO", "SEM FATURAMENTO", "DESABILITADO") for r in resultados)

    deve_enviar = (
        (tem_erro and notif_cfg.get("send_on_error", True)) or
        (not tem_erro and notif_cfg.get("send_on_success", True))
    )

    if not deve_enviar:
        print("[Scheduler] Condicao de notificacao nao atingida. E-mail nao enviado.")
        return

    try:
        from core.notifier import send_scheduler_notification
        send_scheduler_notification(resultados, destinatarios=group_emails, grupo_nome=group_name)
    except Exception as exc:
        _log("ERRO", f"Erro inesperado ao enviar notificacao: {exc}", modulo="Scheduler")
        print(f"[Scheduler] Erro inesperado ao enviar notificacao: {exc}")



# ─────────────────────────────────────────────
# Execução de um job individual (com notificação de grupo)
# ─────────────────────────────────────────────

def run_single_job(job_config: dict) -> None:
    """
    Wrapper para o APScheduler: executa o job e registra o resultado
    no buffer do grupo de notificação correspondente.
    """
    import traceback

    config = load_config()
    name = job_config["name"]

    if not job_config.get("enabled", True):
        resultado = {
            "name": name,
            "status": "DESABILITADO",
            "tentativas": 0,
            "duracao": "--",
            "mensagem_erro": "",
        }
        _record_and_maybe_notify(name, resultado, config)
        return

    _log("INFO", f"run_single_job iniciado: {name}", modulo="Scheduler")
    print(f"[Scheduler] run_single_job iniciado: {name}")

    try:
        resultado = run_job(job_config)
    except Exception as exc:
        tb = traceback.format_exc()
        msg = f"Excecao nao capturada no job '{name}': {exc}\n{tb}"
        _log("ERRO", msg, modulo="Scheduler")
        print(f"[Scheduler] EXCECAO NAO CAPTURADA em '{name}': {exc}")
        resultado = {
            "name": name,
            "status": "ERRO",
            "tentativas": 0,
            "duracao": "--",
            "mensagem_erro": msg,
        }

    _log("INFO", f"run_single_job concluido: {name} = {resultado['status']}", modulo="Scheduler")
    _record_and_maybe_notify(name, resultado, config)


# ─────────────────────────────────────────────
# Compatibilidade: run_all_jobs (chamado se jobs compartilham horário)
# ─────────────────────────────────────────────

def run_all_jobs(jobs_configs: list[dict]) -> None:
    """
    Executa todos os jobs sequencialmente e registra cada resultado
    no buffer de grupo. Mantido para compatibilidade e para jobs
    no mesmo horário.
    """
    for job_cfg in jobs_configs:
        run_single_job(job_cfg)


# ─────────────────────────────────────────────
# Notificação pontual (mantida para compatibilidade de API)
# ─────────────────────────────────────────────

def send_alert(email: str, job_name: str, error: str) -> None:
    """
    Acionada para alerta pontual de um job específico.
    Registra o evento no banco; o e-mail consolidado é enviado por grupo.
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

    Agenda cada job individualmente no seu horário cron.
    Resultados são acumulados por notification_group, e o email
    consolidado só é enviado quando o último job do grupo finaliza.

    Deve ser chamado via st.cache_resource para garantir singleton:

        @st.cache_resource
        def _get_scheduler():
            from core.scheduler import start_scheduler
            return start_scheduler()

    Retorna None se APScheduler não estiver instalado ou se o
    scheduler estiver desabilitado no config.
    """
    global _scheduler_instance, _jobs_meta

    if _scheduler_instance is not None and getattr(_scheduler_instance, "running", False):
        try:
            from apscheduler.schedulers.base import STATE_PAUSED
            if getattr(_scheduler_instance, "state", None) == STATE_PAUSED:
                _scheduler_instance.resume()
        except Exception:
            pass
        return _scheduler_instance

    if not _APSCHEDULER_OK:
        print("[Scheduler] APScheduler nao instalado. Instale com: pip install apscheduler")
        return None

    config = load_config()

    if not config.get("enabled", True):
        print("[Scheduler] Scheduler desabilitado no config.")
        return None

    tz = config.get("timezone", "America/Sao_Paulo")
    scheduler = BackgroundScheduler(timezone=tz)

    all_jobs = config.get("jobs", [])
    _jobs_meta = []

    # Inicializa os buffers de grupo para o dia
    _init_group_buffers(config)

    # Agenda reinicialização diária dos buffers (meia-noite)
    def _reset_buffers_daily():
        _init_group_buffers(load_config())
        _log("INFO", "Buffers de grupo reinicializados para o novo dia.", modulo="Scheduler")
        print("[Scheduler] Buffers de grupo reinicializados para o novo dia.")

    scheduler.add_job(
        func=_reset_buffers_daily,
        trigger="cron",
        hour=0,
        minute=0,
        id="sofi_reset_buffers",
        name="Reset buffers diario",
        max_instances=1,
        replace_existing=True,
    )

    # Agrupa jobs por horário e dia da semana
    schedule_groups: dict[tuple[int, int, str], list[dict]] = {}
    for job_cfg in all_jobs:
        if not job_cfg.get("enabled", True):
            continue
        j_sched = job_cfg.get("schedule", {})
        h = j_sched.get("hour", 8)
        m = j_sched.get("minute", 0)
        raw_dow = j_sched.get("day_of_week")
        if not raw_dow or str(raw_dow).lower().strip() in ("none", "null", ""):
            dow = "mon-fri"
        else:
            dow = str(raw_dow).lower().strip()
            if dow in ("seg-sex", "segunda-sexta", "segunda_a_sexta", "dias_uteis"):
                dow = "mon-fri"
            elif dow in ("todos", "diario", "diário"):
                dow = "*"
        schedule_groups.setdefault((h, m, dow), []).append(job_cfg)

    if not schedule_groups:
        print("[Scheduler] Nenhum job configurado. Scheduler nao iniciado.")
        return None

    for (h, m, dow), group_jobs in schedule_groups.items():
        trigger_kwargs = {"hour": h, "minute": m}
        if dow and dow != "*":
            trigger_kwargs["day_of_week"] = dow

        dow_label = f" ({dow})" if dow and dow != "*" else ""

        if len(group_jobs) == 1:
            # Job individual — agenda diretamente
            job_cfg = group_jobs[0]
            job_id = f"sofi_{job_cfg['name'].replace(' ', '_').lower()}"
            scheduler.add_job(
                func=run_single_job,
                trigger="cron",
                args=[job_cfg],
                id=job_id,
                name=job_cfg["name"],
                max_instances=1,
                replace_existing=True,
                misfire_grace_time=3600,
                coalesce=True,
                **trigger_kwargs,
            )
            print(f"[Scheduler] Job '{job_cfg['name']}' agendado para {h:02d}:{m:02d}{dow_label} ({tz})")
        else:
            # Múltiplos jobs no mesmo horário — run_all_jobs sequencial
            clean_dow = dow.replace("-", "_").replace(",", "_")
            job_id = f"sofi_jobs_{h:02d}_{m:02d}_{clean_dow}"
            scheduler.add_job(
                func=run_all_jobs,
                trigger="cron",
                args=[group_jobs],
                id=job_id,
                name=f"SOFI Jobs {h:02d}:{m:02d}",
                max_instances=1,
                replace_existing=True,
                misfire_grace_time=3600,
                coalesce=True,
                **trigger_kwargs,
            )
            nomes = [j["name"] for j in group_jobs]
            print(f"[Scheduler] Jobs agendados para {h:02d}:{m:02d}{dow_label} ({tz}): {nomes}")

    # Monta metadados para get_scheduler_status()
    for job_cfg in all_jobs:
        if not job_cfg.get("enabled", True):
            continue
        j_sched = job_cfg.get("schedule", {})
        _jobs_meta.append({
            "name": job_cfg["name"],
            "hour": j_sched.get("hour", 8),
            "minute": j_sched.get("minute", 0),
            "day_of_week": j_sched.get("day_of_week", "mon-fri"),
        })

    # Listener para exceções internas do APScheduler
    def _on_job_error(event):
        _log(
            "ERRO",
            f"Excecao inesperada no job '{event.job_id}': {event.exception}",
            modulo="Scheduler",
        )
        print(f"[Scheduler] Excecao inesperada capturada pelo listener: {event.exception}")

    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    scheduler.start()
    _scheduler_instance = scheduler

    # Log dos grupos de notificação
    groups = config.get("notification_groups", {})
    for gname, members in groups.items():
        print(f"[Scheduler] Grupo de notificacao '{gname}': {members}")

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


def pause_scheduler() -> bool:
    """Pausa a execução de jobs pelo scheduler em memória."""
    global _scheduler_instance
    if _scheduler_instance and _scheduler_instance.running:
        try:
            _scheduler_instance.pause()
            _log("INFO", "Scheduler pausado manualmente.", modulo="Scheduler")
            return True
        except Exception as e:
            print(f"[Scheduler] Erro ao pausar: {e}")
    return False


def resume_scheduler() -> bool:
    """Retoma ou inicia a execução de jobs pelo scheduler em memória."""
    global _scheduler_instance
    if _scheduler_instance and _scheduler_instance.running:
        try:
            from apscheduler.schedulers.base import STATE_PAUSED
            if getattr(_scheduler_instance, "state", None) == STATE_PAUSED:
                _scheduler_instance.resume()
                _log("INFO", "Scheduler despausado/retomado.", modulo="Scheduler")
            return True
        except Exception as e:
            print(f"[Scheduler] Erro ao despausar: {e}")
    # Se não estava ativo ou era None, inicia
    res = start_scheduler()
    return bool(res and res.running)


def get_scheduler_status() -> dict:
    """
    Retorna um dict com o status atual do scheduler para exibição no badge do topbar.

    Retorno:
        {
            "running": bool,
            "is_paused": bool,
            "next_job": str,   # ex: "SOFI Daily Jobs 09:00" ou "--"
            "jobs": [{"name": str, "hour": int, "minute": int}, ...]
        }
    """
    is_running = bool(_scheduler_instance and _scheduler_instance.running)
    is_paused = False
    if is_running and hasattr(_scheduler_instance, "state"):
        try:
            from apscheduler.schedulers.base import STATE_PAUSED
            is_paused = (_scheduler_instance.state == STATE_PAUSED)
        except Exception:
            pass

    effective_running = is_running and not is_paused

    next_job = "--"
    if effective_running and _jobs_meta:
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
        "running": effective_running,
        "is_paused": is_paused,
        "next_job": next_job,
        "jobs": list(_jobs_meta),
    }


def reload_scheduler_jobs(scheduler_instance=None, new_config: dict = None) -> None:
    """
    Recarrega e reagenda dinamicamente todos os jobs em memória sem reiniciar o processo.
    Se o reagendamento falhar, propaga exceção para permitir rollback no ConfigManager.
    """
    global _scheduler_instance, _jobs_meta

    target_scheduler = scheduler_instance or _scheduler_instance
    if target_scheduler is None or not getattr(target_scheduler, "running", False):
        return

    if new_config is None:
        new_config = load_config()

    all_jobs = new_config.get("jobs", [])
    new_jobs_meta = []

    # 1. Remover jobs cron atuais (exceto jobs internos como reset de buffers)
    for job in list(target_scheduler.get_jobs()):
        if job.id != "sofi_reset_buffers":
            try:
                target_scheduler.remove_job(job.id)
            except Exception:
                pass

    # 2. Agrupar novos jobs por horário
    schedule_groups: dict[tuple[int, int, str], list[dict]] = {}
    for job_cfg in all_jobs:
        if not job_cfg.get("enabled", True):
            continue
        j_sched = job_cfg.get("schedule", {})
        h = j_sched.get("hour", 8)
        m = j_sched.get("minute", 0)
        raw_dow = j_sched.get("day_of_week")
        if not raw_dow or str(raw_dow).lower().strip() in ("none", "null", ""):
            dow = "mon-fri"
        else:
            dow = str(raw_dow).lower().strip()
            if dow in ("seg-sex", "segunda-sexta", "segunda_a_sexta", "dias_uteis"):
                dow = "mon-fri"
            elif dow in ("todos", "diario", "diário"):
                dow = "*"
        schedule_groups.setdefault((h, m, dow), []).append(job_cfg)

    # 3. Recadastrar jobs
    for (h, m, dow), group_jobs in schedule_groups.items():
        trigger_kwargs = {"hour": h, "minute": m}
        if dow and dow != "*":
            trigger_kwargs["day_of_week"] = dow

        if len(group_jobs) == 1:
            job_cfg = group_jobs[0]
            job_id = f"sofi_{job_cfg['name'].replace(' ', '_').lower()}"
            target_scheduler.add_job(
                func=run_single_job,
                trigger="cron",
                args=[job_cfg],
                id=job_id,
                name=job_cfg["name"],
                max_instances=1,
                replace_existing=True,
                **trigger_kwargs,
            )
            new_jobs_meta.append({"name": job_cfg["name"], "hour": h, "minute": m})
        else:
            group_name = f"SOFI Grupo {h:02d}:{m:02d}"
            job_id = f"sofi_group_{h:02d}_{m:02d}"
            target_scheduler.add_job(
                func=run_all_jobs,
                trigger="cron",
                args=[group_jobs],
                id=job_id,
                name=group_name,
                max_instances=1,
                replace_existing=True,
                **trigger_kwargs,
            )
            new_jobs_meta.append({"name": group_name, "hour": h, "minute": m})

    _jobs_meta = new_jobs_meta
    _log("INFO", f"Scheduler recarregado com sucesso ({len(new_jobs_meta)} gatilho(s) ativo(s)).", modulo="Scheduler")
    print(f"[Scheduler] Recarregado com sucesso com {len(new_jobs_meta)} gatilho(s).")

