import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from components.layout import render_layout

render_layout(nav_links=[("MÓDULOS", "/")])

st.markdown("""
<div class="sofi-title-container">
    <h1 class="sofi-main-title">Módulos de RH</h1>
    <p class="sofi-sub-title">Ferramentas e rotinas do departamento de Recursos Humanos.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sofi-card-grid-3">

    <!-- Card: Relatório RH (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
        <div class="sofi-card-icon-container">
            <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <circle cx="32" cy="20" r="12" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
                <path d="M10 56 Q10 40 32 40 Q54 40 54 56 Z" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
            </svg>
        </div>
        <h3 class="sofi-card-title">Gestão de RH</h3>
    </div>

</div>

<div style="margin-top: 12px; margin-bottom: 30px;">
    <a href="/" target="_self" class="sofi-back-link">&#8592; Voltar para Módulos</a>
</div>
""", unsafe_allow_html=True)
