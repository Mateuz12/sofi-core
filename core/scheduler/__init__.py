"""
core/scheduler/__init__.py

Exporta as funções públicas do scheduler para uso no dashboard Streamlit.

Uso recomendado (singleton via st.cache_resource):

    import streamlit as st
    from core.scheduler import start_scheduler, get_scheduler_status

    @st.cache_resource
    def _get_scheduler():
        return start_scheduler()

    scheduler = _get_scheduler()
"""

from core.scheduler.scheduler import (
    start_scheduler,
    stop_scheduler,
    get_scheduler_status,
    load_config,
    run_job,
    run_single_job,
    run_all_jobs,
    send_alert,
)

__all__ = [
    "start_scheduler",
    "stop_scheduler",
    "get_scheduler_status",
    "load_config",
    "run_job",
    "run_single_job",
    "run_all_jobs",
    "send_alert",
]
