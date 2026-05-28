import streamlit as st
import sys
from pathlib import Path

# Configuração do caminho
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from components.layout import render_layout

# Renderiza Topbar, Footer e injeta CSS global
render_layout()

# Título e Subtítulo
st.markdown("""
<div class="sofi-title-container">
<h1 class="sofi-main-title">Módulos de RH</h1>
<p class="sofi-sub-title">Ferramentas e rotinas do departamento de Recursos Humanos.</p>
</div>
""", unsafe_allow_html=True)

# Grid de Cards placeholder
st.markdown("""
<div class="sofi-card-grid-3">
<!-- Card 1: Triagem (Em breve) -->
<div class="sofi-card disabled">
<span class="sofi-card-badge">Em Breve</span>
<div class="sofi-card-icon-container">
<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
<circle cx="9" cy="7" r="4"></circle>
<path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
<path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
</svg>
</div>
<h3 class="sofi-card-title">Triagem</h3>
<p class="sofi-card-desc">Automação do processo de triagem de candidatos e seleção.</p>
<div class="sofi-card-arrow-container">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"></line>
<polyline points="12 5 19 12 12 19"></polyline>
</svg>
</div>
</div>
</div>

<!-- Link elegante de voltar ao início -->
<div style="text-align: left; margin-top: 20px; margin-bottom: 40px;">
<a href="/" target="_self" class="sofi-back-link">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<line x1="19" y1="12" x2="5" y2="12"></line>
<polyline points="12 19 5 12 12 5"></polyline>
</svg>
Voltar para Departamentos
</a>
</div>
""", unsafe_allow_html=True)
