import streamlit as st
import sys
from pathlib import Path

# Configuração do caminho
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from components.layout import render_layout

# Renderiza Topbar, Footer e injeta CSS global
render_layout()

# Título e Subtítulo da página de módulos
st.markdown("""
<div class="sofi-title-container">
<h1 class="sofi-main-title">Módulos Operacionais</h1>
<p class="sofi-sub-title">Acesse os processos e rotinas operacionais do sistema.</p>
</div>
""", unsafe_allow_html=True)

# Grid de Módulos (3 colunas, seguindo a estética SAGE Light Theme)
# Sem indentação para não ativar blocos de código do Markdown no Streamlit
st.markdown("""
<div class="sofi-card-grid-3">
<!-- Card 1: XML (Ativo) -->
<a href="/xml" target="_self" class="sofi-card-link">
<div class="sofi-card">
<div class="sofi-card-icon-container">
<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
<polyline points="14 2 14 8 20 8"></polyline>
<line x1="16" y1="13" x2="8" y2="13"></line>
<line x1="16" y1="17" x2="8" y2="17"></line>
<polyline points="10 9 9 9 8 9"></polyline>
</svg>
</div>
<h3 class="sofi-card-title">Módulo XML</h3>
<p class="sofi-card-desc">Baixa XMLs via API e gera relatórios de conferência Cálamo.</p>
<div class="sofi-card-arrow-container">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"></line>
<polyline points="12 5 19 12 12 19"></polyline>
</svg>
</div>
</div>
</a>
<!-- Card 2: Extranet (Em breve) -->
<div class="sofi-card disabled">
<span class="sofi-card-badge">Em Breve</span>
<div class="sofi-card-icon-container">
<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="12" cy="12" r="10"></circle>
<line x1="2" y1="12" x2="22" y2="12"></line>
<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
</svg>
</div>
<h3 class="sofi-card-title">Extranet</h3>
<p class="sofi-card-desc">Integração automática com portais e extranets de parceiros.</p>
<div class="sofi-card-arrow-container">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"></line>
<polyline points="12 5 19 12 12 19"></polyline>
</svg>
</div>
</div>
<!-- Card 3: Retaguarda (Em breve) -->
<div class="sofi-card disabled">
<span class="sofi-card-badge">Em Breve</span>
<div class="sofi-card-icon-container">
<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
<rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
<line x1="6" y1="6" x2="6" y2="6"></line>
<line x1="6" y1="18" x2="6" y2="18"></line>
</svg>
</div>
<h3 class="sofi-card-title">Retaguarda</h3>
<p class="sofi-card-desc">Sincronização e auditoria de dados do sistema de retaguarda.</p>
<div class="sofi-card-arrow-container">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"></line>
<polyline points="12 5 19 12 12 19"></polyline>
</svg>
</div>
</div>
<!-- Card 4: Emails VD (Em breve) -->
<div class="sofi-card disabled">
<span class="sofi-card-badge">Em Breve</span>
<div class="sofi-card-icon-container">
<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
<polyline points="22,6 12,13 2,6"></polyline>
</svg>
</div>
<h3 class="sofi-card-title">Emails VD</h3>
<p class="sofi-card-desc">Processamento inteligente e automação de e-mails de Venda Direta.</p>
<div class="sofi-card-arrow-container">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"></line>
<polyline points="12 5 19 12 12 19"></polyline>
</svg>
</div>
</div>
<!-- Card 5: Depósitos (Em breve) -->
<div class="sofi-card disabled">
<span class="sofi-card-badge">Em Breve</span>
<div class="sofi-card-icon-container">
<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<line x1="12" y1="1" x2="12" y2="23"></line>
<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
</svg>
</div>
<h3 class="sofi-card-title">Depósitos</h3>
<p class="sofi-card-desc">Controle e conciliação de depósitos identificados e borderôs.</p>
<div class="sofi-card-arrow-container">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"></line>
<polyline points="12 5 19 12 12 19"></polyline>
</svg>
</div>
</div>
<!-- Card 6: Conciliação Venda (Em breve) -->
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
<h3 class="sofi-card-title">Conciliação Venda</h3>
<p class="sofi-card-desc">Validação cruzada de cartões, taxas e recebíveis operacionais.</p>
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
Voltar para o Início
</a>
</div>
""", unsafe_allow_html=True)
