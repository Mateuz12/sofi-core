"""
core/notifier/__init__.py

Módulo de notificações do SOFI.
Exporta send_scheduler_notification para uso no scheduler.
"""

from core.notifier.smtp_notifier import send_scheduler_notification

__all__ = ["send_scheduler_notification"]
