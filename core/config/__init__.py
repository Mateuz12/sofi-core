"""
core/config — Pacote unificado de gestão de configurações do SOFI.
"""
from core.config.config_manager import ConfigManager, SaveResult
from core.config.schemas import (
    SchedulerSchema,
    NotificacoesSchema,
    ParametrosNegocioSchema,
    JobConfig,
    ScheduleConfig,
    RetryConfig,
    NotificationGroup
)

__all__ = [
    "ConfigManager",
    "SaveResult",
    "SchedulerSchema",
    "NotificacoesSchema",
    "ParametrosNegocioSchema",
    "JobConfig",
    "ScheduleConfig",
    "RetryConfig",
    "NotificationGroup",
]
