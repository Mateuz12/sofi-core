import streamlit as st
import sys
from pathlib import Path

# Configuração do caminho
sys.path.insert(0, str(Path(__file__).resolve().parent))
from components.layout import render_layout

# Renderiza Topbar, Footer e injeta CSS global
render_layout(nav_links=[("MÓDULOS", "/")])

# ─────────────────────────────────────────────
# Tela de Seleção de Departamento (raiz)
# ─────────────────────────────────────────────
st.markdown("""<div class="sofi-title-container">
<h1 class="sofi-main-title">Selecione um módulo</h1>
<p class="sofi-sub-title">Acesse rapidamente as áreas do sistema.</p>
</div>""", unsafe_allow_html=True)

# Grid de 2 cards de departamento - sem linhas em branco que quebram o parser
st.markdown("""<div class="sofi-card-grid-2">
<a href="/financeiro" target="_self" class="sofi-card-link">
<div class="sofi-card">
<div class="sofi-card-icon-container">
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="32" cy="52" rx="18" ry="6" fill="#d4a520" stroke="#a07800" stroke-width="1.5"/>
<rect x="14" y="38" width="36" height="14" fill="#f0c030" stroke="#a07800" stroke-width="1.5" rx="1"/>
<ellipse cx="32" cy="38" rx="18" ry="6" fill="#f5d060" stroke="#a07800" stroke-width="1.5"/>
<ellipse cx="32" cy="32" rx="18" ry="6" fill="#d4a520" stroke="#a07800" stroke-width="1.5"/>
<rect x="14" y="18" width="36" height="14" fill="#f0c030" stroke="#a07800" stroke-width="1.5" rx="1"/>
<ellipse cx="32" cy="18" rx="18" ry="6" fill="#f5d060" stroke="#a07800" stroke-width="1.5"/>
<polygon points="48,10 52,4 56,10" fill="#cc2200"/>
<rect x="51" y="10" width="2" height="8" fill="#cc2200"/>
<polygon points="8,4 12,10 16,4" fill="#228800"/>
<rect x="11" y="4" width="2" height="8" fill="#228800"/>
</svg>
</div>
<h3 class="sofi-card-title">Financeiro</h3>
</div>
</a>
<div class="sofi-card disabled">
<span class="sofi-card-badge">Em Breve</span>
<div class="sofi-card-icon-container">
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
<circle cx="32" cy="16" r="10" fill="#5b8fc9" stroke="#3a6ea5" stroke-width="1.5"/>
<path d="M14 52 Q14 36 32 36 Q50 36 50 52 Z" fill="#5b8fc9" stroke="#3a6ea5" stroke-width="1.5"/>
<rect x="25" y="36" width="14" height="10" rx="2" fill="#ffffff" stroke="#3a6ea5" stroke-width="1"/>
<line x1="28" y1="40" x2="36" y2="40" stroke="#5b8fc9" stroke-width="1.5"/>
<line x1="28" y1="43" x2="36" y2="43" stroke="#5b8fc9" stroke-width="1.5"/>
<circle cx="47" cy="20" r="7" fill="#89b4dc" stroke="#3a6ea5" stroke-width="1"/>
<path d="M34 52 Q36 44 47 44 Q55 44 56 52 Z" fill="#89b4dc" stroke="#3a6ea5" stroke-width="1"/>
</svg>
</div>
<h3 class="sofi-card-title">Recursos Humanos</h3>
</div>
</div>""", unsafe_allow_html=True)
