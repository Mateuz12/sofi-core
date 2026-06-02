import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from components.layout import render_layout

render_layout(nav_links=[("MÓDULOS", "/")])

st.markdown("""
<div class="sofi-title-container">
    <h1 class="sofi-main-title">Módulos de Compras</h1>
    <p class="sofi-sub-title">Ferramentas e rotinas do departamento de Compras.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sofi-card-grid-3">

    <!-- Card: Relatório MAR (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
        <div class="sofi-card-icon-container">
            <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <rect x="8" y="10" width="48" height="44" rx="4" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
                <rect x="8" y="10" width="48" height="12" rx="4" fill="#5b8fc9"/>
                <line x1="16" y1="34" x2="48" y2="34" stroke="#5b8fc9" stroke-width="1.5"/>
                <line x1="16" y1="42" x2="40" y2="42" stroke="#5b8fc9" stroke-width="1.5"/>
                <line x1="16" y1="26" x2="48" y2="26" stroke="#c8ddf5" stroke-width="1.5"/>
            </svg>
        </div>
        <h3 class="sofi-card-title">Relatório MAR</h3>
    </div>

</div>

<div style="margin-top: 12px; margin-bottom: 30px;">
    <a href="/" target="_self" class="sofi-back-link">&#8592; Voltar para Módulos</a>
</div>
""", unsafe_allow_html=True)
