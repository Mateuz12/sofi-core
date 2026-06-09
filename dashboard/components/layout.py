import streamlit as st
import datetime
from pathlib import Path

def _get_scheduler_badge_html() -> str:
    """Retorna o HTML do badge de status do scheduler para a topbar."""
    try:
        from core.scheduler import get_scheduler_status
        status = get_scheduler_status()
        if status["running"]:
            return (
                f'<span class="sofi-scheduler-badge sofi-scheduler-ok">'
                f'🟢 Scheduler: OK'
                f'<span class="sofi-scheduler-next"> | Próx: {status["next_job"]}</span>'
                f'</span>'
            )
        else:
            return '<span class="sofi-scheduler-badge sofi-scheduler-off">🔴 Scheduler: PAUSADO</span>'
    except Exception:
        return ''  # silencioso se scheduler não estiver disponível

def load_css():
    """Carrega o arquivo CSS e injeta no Streamlit."""
    css_path = Path(__file__).resolve().parent.parent / "style.css"
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def render_topbar(nav_links: list[tuple[str, str]] | None = None):
    """Renderiza a barra superior fixa estilo Sage com gradiente azul-escuro.

    Args:
        nav_links: Lista de tuplas (label, url) para a navegação central.
                   Ex: [("Módulos", "/financeiro"), ("Atividades", "#")]
    """
    # Links de navegação
    if nav_links is None:
        nav_links = []

    nav_html = ""
    for label, url in nav_links:
        nav_html += f'<a href="{url}" target="_self" class="sofi-nav-link">{label}</a>'

    scheduler_badge = _get_scheduler_badge_html()

    html = f"""
    <div class="sofi-header">
        <a href="/" target="_self" class="sofi-logo">
            <span class="sofi-logo-text">SAGE.COM.BR</span>
        </a>
        <div class="sofi-nav-center">
            {nav_html}
        </div>
        <div class="sofi-user">
            {scheduler_badge}
            <span class="sofi-user-name">USUARIO FINANCEIRO DE UDI ▾</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_footer():
    """Renderiza o rodapé fixo estilo Sage com gradiente azul-escuro."""
    now = datetime.datetime.now()
    ano = now.year

    html = f"""
    <div class="sofi-footer">
        <span class="sofi-footer-left">20844 - VD MARTINS UDI</span>
        <span class="sofi-footer-right">© {ano} - SOFI v2.1.0</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_layout(nav_links: list[tuple[str, str]] | None = None):
    """Aplica o design base Sage à página atual.

    Args:
        nav_links: Links de navegação para a topbar. Se None, sem links centrais.
    """
    st.set_page_config(
        page_title="SOFI",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    load_css()
    render_topbar(nav_links=nav_links)
    render_footer()
