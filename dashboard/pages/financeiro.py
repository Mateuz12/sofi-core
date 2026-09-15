import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from components.layout import render_layout, render_scheduler_status

render_layout(nav_links=[
    ("MÓDULOS", "/"),
    ("TORRE DE CONTROLE", "/torre_controle"),
])

st.markdown("""<div class="sofi-title-container">
<h1 class="sofi-main-title">Módulos Financeiros</h1>
<p class="sofi-sub-title">Acesse os processos e rotinas operacionais do departamento financeiro.</p>
</div>""", unsafe_allow_html=True)

# SVGs sem recuo ou linhas em branco que quebram o Streamlit
st.markdown("""<div class="sofi-card-grid-3">
<a href="/xml" target="_self" class="sofi-card-link">
<div class="sofi-card">
<div class="sofi-card-icon-container">
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
<path d="M34 4 L46 16 L46 56 L12 56 L12 4 Z" fill="#f0f6ff" stroke="#5b8fc9" stroke-width="2"/>
<polyline points="34,4 34,16 46,16" fill="#c8ddf5" stroke="#5b8fc9" stroke-width="1.5"/>
<line x1="18" y1="28" x2="40" y2="28" stroke="#337ab7" stroke-width="2"/>
<line x1="18" y1="36" x2="40" y2="36" stroke="#5b8fc9" stroke-width="1.5"/>
<line x1="18" y1="44" x2="32" y2="44" stroke="#5b8fc9" stroke-width="1.5"/>
<circle cx="46" cy="50" r="10" fill="#5cb85c"/>
<line x1="42" y1="50" x2="50" y2="50" stroke="#ffffff" stroke-width="2.5"/>
<line x1="46" y1="46" x2="46" y2="54" stroke="#ffffff" stroke-width="2.5"/>
</svg>
</div>
<h3 class="sofi-card-title">Módulo XML</h3>
</div>
</a>
<a href="/extranet" target="_self" class="sofi-card-link">
<div class="sofi-card">
<div class="sofi-card-icon-container">
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
<circle cx="32" cy="32" r="22" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
<ellipse cx="32" cy="32" rx="10" ry="22" fill="none" stroke="#5b8fc9" stroke-width="1.5"/>
<line x1="10" y1="32" x2="54" y2="32" stroke="#5b8fc9" stroke-width="1.5"/>
<path d="M14 20 Q32 26 50 20" fill="none" stroke="#5b8fc9" stroke-width="1.5"/>
<path d="M14 44 Q32 38 50 44" fill="none" stroke="#5b8fc9" stroke-width="1.5"/>
<circle cx="50" cy="50" r="9" fill="#337ab7"/>
<polyline points="46,50 50,54 56,46" fill="none" stroke="#ffffff" stroke-width="2"/>
</svg>
</div>
<h3 class="sofi-card-title">Extranet</h3>
</div>
</a>
<a href="/retaguarda" target="_self" class="sofi-card-link">
<div class="sofi-card">
<div class="sofi-card-icon-container">
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
<rect x="8" y="8" width="48" height="14" rx="3" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
<circle cx="16" cy="15" r="3" fill="#5cb85c"/>
<rect x="22" y="12" width="22" height="6" rx="1" fill="#c8ddf5"/>
<rect x="8" y="26" width="48" height="14" rx="3" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
<circle cx="16" cy="33" r="3" fill="#f0ad4e"/>
<rect x="22" y="30" width="22" height="6" rx="1" fill="#c8ddf5"/>
<line x1="32" y1="40" x2="32" y2="50" stroke="#5b8fc9" stroke-width="1.5"/>
<line x1="20" y1="50" x2="44" y2="50" stroke="#5b8fc9" stroke-width="1.5"/>
<circle cx="20" cy="54" r="3" fill="#5b8fc9"/>
<circle cx="32" cy="54" r="3" fill="#5b8fc9"/>
<circle cx="44" cy="54" r="3" fill="#5b8fc9"/>
</svg>
</div>
<h3 class="sofi-card-title">Retaguarda</h3>
</div>
</a>
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
<div class="sofi-card disabled">
<span class="sofi-card-badge">Em Breve</span>
<div class="sofi-card-icon-container">
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
<rect x="8" y="20" width="48" height="32" rx="3" fill="#ddeeff" stroke="#5b8fc9" stroke-width="2"/>
<rect x="20" y="12" width="24" height="12" rx="2" fill="#c8ddf5" stroke="#5b8fc9" stroke-width="1.5"/>
<line x1="32" y1="26" x2="32" y2="42" stroke="#5b8fc9" stroke-width="2"/>
<polyline points="24,36 32,44 40,36" fill="none" stroke="#5b8fc9" stroke-width="2"/>
</svg>
</div>
<h3 class="sofi-card-title">Depósitos</h3>
</div>
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
</div>""", unsafe_allow_html=True)

# ─── Agendados ────────────────────────────────────────────────────────────────
st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)
st.markdown("**Agendados**")
render_scheduler_status()
