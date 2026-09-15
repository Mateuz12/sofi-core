import streamlit as st
import datetime
from pathlib import Path

def render_scheduler_status():
    """Renderiza o painel de status do scheduler. Pode ser chamado em qualquer página."""
    try:
        from core.scheduler.scheduler import get_scheduler_status
        status = get_scheduler_status()
        if status["running"]:
            html = (
                f'<div class="sofi-scheduler-panel sofi-scheduler-ok">'
                f'<span class="sofi-scheduler-indicator">&#9679;</span>'
                f'<span class="sofi-scheduler-label">Agendados: ativo</span>'
                f'<span class="sofi-scheduler-next">| Próxima execução: {status["next_job"]}</span>'
                f'</div>'
            )
        else:
            html = (
                '<div class="sofi-scheduler-panel sofi-scheduler-off">'
                '<span class="sofi-scheduler-indicator">&#9679;</span>'
                '<span class="sofi-scheduler-label">Agendados: pausado</span>'
                '</div>'
            )
        st.markdown(html, unsafe_allow_html=True)
    except Exception:
        pass  # silencioso se scheduler não estiver disponível

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

    html = f"""
    <div class="sofi-header">
        <a href="/" target="_self" class="sofi-logo">
            <span class="sofi-logo-text">SAGE.COM.BR</span>
        </a>
        <div class="sofi-nav-center">
            {nav_html}
        </div>
        <div class="sofi-user">
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


@st.cache_resource
def ensure_scheduler_started():
    try:
        from core.scheduler.scheduler import start_scheduler
        return start_scheduler()
    except Exception as e:
        print(f"[Scheduler] Erro ao iniciar singleton: {e}")
        return None


def render_layout(nav_links: list[tuple[str, str]] | None = None):
    """Aplica o design base Sage à página atual.

    Args:
        nav_links: Links de navegação para a topbar. Se None, sem links centrais.
    """
    st.set_page_config(
        page_title="SOFI1.0",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    load_css()
    ensure_scheduler_started()
    render_topbar(nav_links=nav_links)
    render_footer()

