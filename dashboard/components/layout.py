import streamlit as st
import datetime
from pathlib import Path

def load_css():
    """Carrega o arquivo CSS e injeta no Streamlit."""
    css_path = Path(__file__).resolve().parent.parent / "style.css"
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def render_topbar():
    """Renderiza a barra superior fixa (SAGE pattern) com alta fidelidade visual e links."""
    html = """
    <div class="sofi-header">
        <a href="/" target="_self" class="sofi-logo">
            <svg class="sofi-logo-svg" width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <!-- Escudo azul estilizado moderno com gradiente/S interno -->
                <path d="M12 2L3 5V11C3 16.55 6.84 21.74 12 23C17.16 21.74 21 16.55 21 11V5L12 2Z" fill="#0078C8" />
                <path d="M12 6C9.79 6 8 7.79 8 10C8 12.21 9.79 14 12 14C14.21 14 16 12.21 16 10H14C14 11.1 13.1 12 12 12C10.9 12 10 11.1 10 10C10 8.9 10.9 8 12 8C13.1 8 14 8.9 14 10H16C16 7.79 14.21 6 12 6Z" fill="#FFFFFF" />
                <path d="M12 10C14.21 10 16 11.79 16 14C16 16.21 14.21 18 12 18C9.79 18 8 16.21 8 14H10C10 15.1 10.9 16 12 16C13.1 16 14 15.1 14 14C14 12.9 13.1 12 12 12C9.79 12 8 10.21 8 8H10C10 9.1 10.9 10 12 10Z" fill="#FFFFFF" opacity="0.85" />
            </svg>
            <span class="sofi-logo-text">SOFI</span>
        </a>
        <a href="/financeiro" target="_self" class="sofi-center">
            <svg class="sofi-nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="7" rx="1.5"></rect>
                <rect x="14" y="3" width="7" height="7" rx="1.5"></rect>
                <rect x="14" y="14" width="7" height="7" rx="1.5"></rect>
                <rect x="3" y="14" width="7" height="7" rx="1.5"></rect>
            </svg>
            <span class="sofi-nav-text">Financeiro</span>
        </a>
        <div class="sofi-user">
            <div class="sofi-avatar">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
            </div>
            <span class="sofi-user-name">Usuário Financeiro de UDI</span>
            <svg class="sofi-user-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_footer():
    """Renderiza o rodapé fixo (SAGE pattern) com alta fidelidade e ícones SVG."""
    now = datetime.datetime.now()
    meses = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
    }
    data_formatada = f"{now.day} de {meses[now.month]} de {now.year}"
    hora_formatada = now.strftime("%H:%M")
    
    html = f"""
    <div class="sofi-footer">
        <div class="footer-item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            <span>SOFI v2.1.0</span>
        </div>
        <span class="footer-divider">|</span>
        <div class="footer-item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
            </svg>
            <span>{data_formatada}</span>
        </div>
        <span class="footer-divider">|</span>
        <div class="footer-item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            <span>{hora_formatada}</span>
        </div>
        <span class="footer-divider">|</span>
        <div class="footer-item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
                <line x1="9" y1="22" x2="9" y2="16"></line>
                <line x1="15" y1="22" x2="15" y2="16"></line>
                <line x1="9" y1="16" x2="15" y2="16"></line>
                <path d="M8 6h.01"></path>
                <path d="M16 6h.01"></path>
                <path d="M8 10h.01"></path>
                <path d="M16 10h.01"></path>
            </svg>
            <span>20844 - VD MARTINS UDI</span>
        </div>
        <span class="footer-divider">|</span>
        <div class="footer-item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
            <span style="font-weight: 600; color: var(--text-main);">Ambiente Produção</span>
            <span class="status-indicator"></span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_layout():
    """Aplica o design base à página atual."""
    # Ocultar sidebar
    st.set_page_config(page_title="SOFI Hub", page_icon="✦", layout="wide", initial_sidebar_state="collapsed")
    load_css()
    render_topbar()
    render_footer()

