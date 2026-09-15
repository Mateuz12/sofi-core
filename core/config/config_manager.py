"""
core/config/config_manager.py — Gestor Centralizado de Configurações do SOFI.
Implementa:
  - 3 arquivos YAML por domínio (scheduler, notificacoes, parametros_negocio)
  - Validação via Pydantic Schemas
  - Lock de concorrência com filelock
  - Escrita atômica real (tmp + os.replace)
  - Transação com rollback automático em caso de falha de reload
  - Diff recursivo e auditoria granular no SQLite
  - Retenção FIFO de backups (máx 30 por domínio)
  - Fallbacks legados
"""
import os
import sys
import yaml
import sqlite3
import shutil
import getpass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from filelock import FileLock

# Resolução da raiz
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config.schemas import (
    SchedulerSchema,
    NotificacoesSchema,
    ParametrosNegocioSchema
)
from core.config.diff import compute_diff, DiffEntry

_CONFIG_DIR = _ROOT / "config"
_BACKUPS_DIR = _CONFIG_DIR / "backups"
_DB_PATH = _ROOT / os.getenv("LOG_DB_PATH", "core/database/sofi.db")

@dataclass
class SaveResult:
    success: bool
    errors: List[str] = field(default_factory=list)
    diff_entries: List[DiffEntry] = field(default_factory=list)
    backup_file: Optional[str] = None

class ConfigManager:
    """Singleton de gerenciamento de configurações."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_lock(self, domain: str) -> FileLock:
        lock_file = _CONFIG_DIR / f"{domain}.yaml.lock"
        return FileLock(str(lock_file), timeout=10.0)

    # ─────────────────────────────────────────────────────────────
    # Backups e Retenção
    # ─────────────────────────────────────────────────────────────
    def _create_backup(self, domain: str) -> Optional[Path]:
        src = _CONFIG_DIR / f"{domain}.yaml"
        if not src.exists():
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = _BACKUPS_DIR / f"{domain}_{ts}.yaml"
        shutil.copy2(src, backup_path)
        self._enforce_retention(domain)
        return backup_path

    def _enforce_retention(self, domain: str, max_backups: int = 30):
        try:
            pattern = f"{domain}_*.yaml"
            backups = sorted(_BACKUPS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
            while len(backups) > max_backups:
                oldest = backups.pop(0)
                oldest.unlink(missing_ok=True)
        except Exception as e:
            print(f"[ConfigManager] Aviso de retenção: {e}")

    def _atomic_write(self, domain: str, data: dict) -> None:
        target = _CONFIG_DIR / f"{domain}.yaml"
        tmp = _CONFIG_DIR / f"{domain}.yaml.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp, target)

    def _record_audit(self, usuario: str, domain: str, diffs: List[DiffEntry]):
        if not diffs:
            return
        try:
            with sqlite3.connect(_DB_PATH, timeout=10.0) as conn:
                for d in diffs:
                    conn.execute("""
                        INSERT INTO configuration_audit_logs (usuario, dominio, chave, valor_anterior, valor_novo)
                        VALUES (?, ?, ?, ?, ?)
                    """, (usuario, domain, d.chave, d.valor_anterior, d.valor_novo))
        except Exception as e:
            print(f"[ConfigManager] Erro ao gravar auditoria: {e}")

    # ─────────────────────────────────────────────────────────────
    # Leitura
    # ─────────────────────────────────────────────────────────────
    def get_scheduler_config(self) -> SchedulerSchema:
        file_path = _CONFIG_DIR / "scheduler.yaml"
        with self._get_lock("scheduler"):
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return SchedulerSchema(**data)
            # Fallback legado
            legacy = _ROOT / "core" / "scheduler" / "scheduler_config.json"
            if legacy.exists():
                import json
                with open(legacy, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return SchedulerSchema(**data)
            return SchedulerSchema(jobs=[])

    def get_notificacoes_config(self) -> NotificacoesSchema:
        file_path = _CONFIG_DIR / "notificacoes.yaml"
        with self._get_lock("notificacoes"):
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return NotificacoesSchema(**data)
            return NotificacoesSchema(grupos={})

    def get_parametros_config(self) -> ParametrosNegocioSchema:
        file_path = _CONFIG_DIR / "parametros_negocio.yaml"
        with self._get_lock("parametros_negocio"):
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return ParametrosNegocioSchema(**data)
            return ParametrosNegocioSchema(prazos_pagamento=self._load_legacy_prazos())

    def _load_legacy_prazos(self) -> Dict[str, int]:
        txt_path = _ROOT / "departments" / "financeiro" / "modules" / "xml" / "regras_prazo.txt"
        prazos = {"default": 30}
        if txt_path.exists():
            with open(txt_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        try:
                            val = int(v.strip())
                            prazos[k.strip()] = val
                        except ValueError:
                            continue
        return prazos

    # ─────────────────────────────────────────────────────────────
    # Escrita com Validação, Rollback e Auditoria
    # ─────────────────────────────────────────────────────────────
    def save_scheduler(self, data: dict, user: str = None, scheduler_instance=None) -> SaveResult:
        user = user or getpass.getuser()
        with self._get_lock("scheduler"):
            try:
                validated = SchedulerSchema(**data)
                clean_dict = validated.model_dump()
            except Exception as e:
                return SaveResult(success=False, errors=[str(e)])

            curr_data = {}
            target = _CONFIG_DIR / "scheduler.yaml"
            if target.exists():
                with open(target, "r", encoding="utf-8") as f:
                    curr_data = yaml.safe_load(f) or {}

            diffs = compute_diff(curr_data, clean_dict)
            backup_path = self._create_backup("scheduler")

            try:
                self._atomic_write("scheduler", clean_dict)
            except Exception as e:
                return SaveResult(success=False, errors=[f"Falha ao gravar arquivo: {e}"])

            if scheduler_instance is not None:
                try:
                    from core.scheduler.scheduler import reload_scheduler_jobs
                    reload_scheduler_jobs(scheduler_instance, clean_dict)
                except Exception as e:
                    if backup_path and backup_path.exists():
                        shutil.copy2(backup_path, target)
                    return SaveResult(
                        success=False,
                        errors=[f"Falha no hot-reload do Scheduler. Configuração revertida: {e}"]
                    )

            self._record_audit(user, "scheduler", diffs)
            return SaveResult(
                success=True,
                diff_entries=diffs,
                backup_file=str(backup_path) if backup_path else None
            )

    def save_notificacoes(self, data: dict, user: str = None) -> SaveResult:
        user = user or getpass.getuser()
        with self._get_lock("notificacoes"):
            try:
                validated = NotificacoesSchema(**data)
                clean_dict = validated.model_dump()
            except Exception as e:
                return SaveResult(success=False, errors=[str(e)])

            curr_data = {}
            target = _CONFIG_DIR / "notificacoes.yaml"
            if target.exists():
                with open(target, "r", encoding="utf-8") as f:
                    curr_data = yaml.safe_load(f) or {}

            diffs = compute_diff(curr_data, clean_dict)
            backup_path = self._create_backup("notificacoes")

            try:
                self._atomic_write("notificacoes", clean_dict)
            except Exception as e:
                return SaveResult(success=False, errors=[f"Falha ao gravar arquivo: {e}"])

            self._record_audit(user, "notificacoes", diffs)
            return SaveResult(success=True, diff_entries=diffs, backup_file=str(backup_path) if backup_path else None)

    def save_parametros(self, data: dict, user: str = None) -> SaveResult:
        user = user or getpass.getuser()
        with self._get_lock("parametros_negocio"):
            try:
                validated = ParametrosNegocioSchema(**data)
                clean_dict = validated.model_dump()
            except Exception as e:
                return SaveResult(success=False, errors=[str(e)])

            curr_data = {}
            target = _CONFIG_DIR / "parametros_negocio.yaml"
            if target.exists():
                with open(target, "r", encoding="utf-8") as f:
                    curr_data = yaml.safe_load(f) or {}

            diffs = compute_diff(curr_data, clean_dict)
            backup_path = self._create_backup("parametros_negocio")

            try:
                self._atomic_write("parametros_negocio", clean_dict)
            except Exception as e:
                return SaveResult(success=False, errors=[f"Falha ao gravar arquivo: {e}"])

            self._record_audit(user, "parametros_negocio", diffs)
            return SaveResult(success=True, diff_entries=diffs, backup_file=str(backup_path) if backup_path else None)

    # ─────────────────────────────────────────────────────────────
    # Métodos de Conveniência e Fallbacks para os Módulos
    # ─────────────────────────────────────────────────────────────
    def get_pdv_prazos(self) -> Dict[str, int]:
        try:
            cfg = self.get_parametros_config()
            return cfg.prazos_pagamento
        except Exception:
            return self._load_legacy_prazos()

    def get_notification_recipients(self, group: str) -> List[str]:
        slug = group.lower().replace(" ", "_")
        try:
            cfg = self.get_notificacoes_config()
            if slug in cfg.grupos:
                return [str(email) for email in cfg.grupos[slug].emails]
        except Exception:
            pass
        env_map = {
            "retaguarda": "SCHEDULER_NOTIFY_EMAILS_RETAGUARDA",
            "xml_retaguarda": "SCHEDULER_NOTIFY_EMAILS_XML",
            "extranet": "SCHEDULER_NOTIFY_EMAILS_EXTRANET",
        }
        var_name = env_map.get(slug, "SCHEDULER_NOTIFY_EMAILS")
        emails_str = os.getenv(var_name, "")
        if emails_str:
            return [e.strip() for e in emails_str.split(";") if e.strip()]
        return []

    def get_scheduler_jobs(self) -> List[dict]:
        try:
            cfg = self.get_scheduler_config()
            return [j.model_dump() for j in cfg.jobs if j.enabled]
        except Exception:
            return []
