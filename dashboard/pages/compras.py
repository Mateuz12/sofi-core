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
<h1 class="sofi-main-title">Módulos de Compras</h1>
<p class="sofi-sub-title">Ferramentas e rotinas do departamento de Compras.</p>
</div>
""", unsafe_allow_html=True)

# Grid de Cards
st.markdown("""
<div class="sofi-card-grid-3">
<!-- Card 1: Relatório MAR (Em breve) -->
<div class="sofi-card disabled">
<span class="sofi-card-badge">Em Breve</span>
<div class="sofi-card-icon-container">
<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="9" cy="21" r="1"></circle>
<circle cx="20" cy="21" r="1"></circle>
<path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
</svg>
</div>
<h3 class="sofi-card-title">Relatório MAR</h3>
<p class="sofi-card-desc">Extração e geração de relatórios de compras MAR via extranet.</p>
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
