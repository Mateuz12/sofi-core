import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from components.layout import render_layout

render_layout(nav_links=[("MÓDULOS", "/")])

st.markdown("""
<div class="sofi-title-container">
    <h1 class="sofi-main-title">Módulos Financeiros</h1>
    <p class="sofi-sub-title">Acesse os processos e rotinas operacionais do departamento financeiro.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sofi-card-grid-3">

    <!-- Card: XML (Ativo) -->
    <a href="/xml" target="_self" class="sofi-card-link">
    <div class="sofi-card">
        <div class="sofi-card-icon-container">
            <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <!-- Documento XML -->
                <rect x="12" y="4" width="34" height="44" rx="3" fill="#ffffff" stroke="#5b8fc9" stroke-width="2"/>
                <rect x="12" y="4" width="34" height="44" rx="3" fill="#f0f6ff"/>
                <polyline points="34,4 34,16 46,16" fill="#c8ddf5" stroke="#5b8fc9" stroke-width="1.5"/>
                <path d="M34 4 L46 16 L46 48 L12 48 L12 4 Z" fill="none" stroke="#5b8fc9" stroke-width="2"/>
                <!-- Tags XML -->
                <text x="17" y="28" font-size="8" fill="#337ab7" font-family="Courier New" font-weight="bold">&lt;xml&gt;</text>
                <text x="17" y="37" font-size="8" fill="#5b8fc9" font-family="Courier New">&lt;/xml&gt;</text>
                <!-- Ícone de download/seta -->
                <circle cx="46" cy="50" r="9" fill="#5cb85c"/>
                <polygon points="46,44 42,52 50,52" fill="#ffffff" transform="rotate(180,46,48)"/>
                <rect x="44.5" y="48" width="3" height="6" fill="#ffffff"/>
            </svg>
        </div>
        <h3 class="sofi-card-title">Módulo XML</h3>
    </div>
    </a>

    <!-- Card: Extranet (Ativo) -->
    <a href="/extranet" target="_self" class="sofi-card-link">
    <div class="sofi-card">
        <div class="sofi-card-icon-container">
            <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <!-- Globo -->
                <circle cx="32" cy="32" r="22" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
                <ellipse cx="32" cy="32" rx="10" ry="22" fill="none" stroke="#5b8fc9" stroke-width="1.5"/>
                <line x1="10" y1="32" x2="54" y2="32" stroke="#5b8fc9" stroke-width="1.5"/>
                <path d="M14 20 Q32 26 50 20" fill="none" stroke="#5b8fc9" stroke-width="1.5"/>
                <path d="M14 44 Q32 38 50 44" fill="none" stroke="#5b8fc9" stroke-width="1.5"/>
                <!-- Seta de sincronização -->
                <circle cx="50" cy="50" r="9" fill="#337ab7"/>
                <path d="M46 50 Q50 46 54 50 Q50 54 46 50Z" fill="none" stroke="#ffffff" stroke-width="1.5"/>
                <polygon points="54,49 57,52 51,52" fill="#ffffff"/>
            </svg>
        </div>
        <h3 class="sofi-card-title">Extranet</h3>
    </div>
    </a>

    <!-- Card: Retaguarda (Ativo) -->
    <a href="/retaguarda" target="_self" class="sofi-card-link">
    <div class="sofi-card">
        <div class="sofi-card-icon-container">
            <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <!-- Servidor -->
                <rect x="10" y="10" width="44" height="14" rx="3" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
                <circle cx="18" cy="17" r="3" fill="#5cb85c"/>
                <rect x="24" y="14" width="20" height="6" rx="1" fill="#c8ddf5"/>
                <rect x="10" y="28" width="44" height="14" rx="3" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
                <circle cx="18" cy="35" r="3" fill="#f0ad4e"/>
                <rect x="24" y="32" width="20" height="6" rx="1" fill="#c8ddf5"/>
                <!-- Fios -->
                <line x1="32" y1="42" x2="32" y2="50" stroke="#5b8fc9" stroke-width="1.5"/>
                <line x1="22" y1="50" x2="42" y2="50" stroke="#5b8fc9" stroke-width="1.5"/>
                <circle cx="22" cy="54" r="3" fill="#5b8fc9"/>
                <circle cx="32" cy="54" r="3" fill="#5b8fc9"/>
                <circle cx="42" cy="54" r="3" fill="#5b8fc9"/>
            </svg>
        </div>
        <h3 class="sofi-card-title">Retaguarda</h3>
    </div>
    </a>

    <!-- Card: Emails VD (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
        <div class="sofi-card-icon-container">
            <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <rect x="6" y="14" width="52" height="36" rx="4" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
                <polyline points="6,18 32,36 58,18" fill="none" stroke="#5b8fc9" stroke-width="2"/>
            </svg>
        </div>
        <h3 class="sofi-card-title">Emails VD</h3>
    </div>

    <!-- Card: Depósitos (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
        <div class="sofi-card-icon-container">
            <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <rect x="8" y="20" width="48" height="32" rx="3" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
                <rect x="20" y="14" width="24" height="10" rx="2" fill="#c8ddf5" stroke="#5b8fc9" stroke-width="1.5"/>
                <line x1="32" y1="28" x2="32" y2="44" stroke="#5b8fc9" stroke-width="2"/>
                <polyline points="24,36 32,44 40,36" fill="none" stroke="#5b8fc9" stroke-width="2"/>
            </svg>
        </div>
        <h3 class="sofi-card-title">Depósitos</h3>
    </div>

    <!-- Card: Conciliação Venda (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
        <div class="sofi-card-icon-container">
            <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <rect x="8" y="8" width="48" height="48" rx="4" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
                <line x1="8" y1="22" x2="56" y2="22" stroke="#5b8fc9" stroke-width="1.5"/>
                <line x1="32" y1="8" x2="32" y2="56" stroke="#5b8fc9" stroke-width="1.5"/>
                <polyline points="14,40 24,32 34,38 50,26" fill="none" stroke="#337ab7" stroke-width="2.5"/>
                <circle cx="50" cy="26" r="3" fill="#337ab7"/>
            </svg>
        </div>
        <h3 class="sofi-card-title">Conciliação Venda</h3>
    </div>

</div>

<div style="margin-top: 12px; margin-bottom: 30px;">
    <a href="/" target="_self" class="sofi-back-link">&#8592; Voltar para Módulos</a>
</div>
""", unsafe_allow_html=True)
