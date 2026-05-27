import streamlit as st
import sys
from pathlib import Path

# Configuração do caminho
sys.path.insert(0, str(Path(__file__).resolve().parent))
from components.layout import render_layout

# Renderiza Topbar, Footer e injeta CSS global
render_layout()

# Obter o departamento selecionado da URL
dept = st.query_params.get("dept", None)

if dept == "Financeiro":
    # Link de voltar para departamentos
    st.markdown("""
    <div style="margin-top: 100px; margin-bottom: -90px; width: 100%;">
        <a href="/" target="_self" class="sofi-back-link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px; vertical-align: middle;">
                <line x1="19" y1="12" x2="5" y2="12"></line>
                <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
            Voltar para Departamentos
        </a>
    </div>
    """, unsafe_allow_html=True)

    # Título e Subtítulo alinhados à esquerda (SAGE Design System)
    st.markdown("""
    <div class="sofi-title-container">
    <h1 class="sofi-main-title">Módulos Financeiros</h1>
    <p class="sofi-sub-title">Acesse rapidamente as ferramentas e rotinas operacionais do departamento financeiro.</p>
    </div>
    """, unsafe_allow_html=True)

    # Grid de Cards Premium original do Financeiro
    st.markdown("""
    <div class="sofi-card-grid">
    <!-- Card 1: Dashboard (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
    <div class="sofi-card-icon-container">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
    <line x1="8" y1="21" x2="16" y2="21"></line>
    <line x1="12" y1="17" x2="12" y2="21"></line>
    <path d="M17 12h.01"></path>
    <path d="M7 8h.01"></path>
    <path d="M12 10h.01"></path>
    </svg>
    </div>
    <h3 class="sofi-card-title">Dashboard Financeiro</h3>
    <p class="sofi-card-desc">Visão geral da saúde financeira com indicadores e análises.</p>
    <div class="sofi-card-arrow-container">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <line x1="5" y1="12" x2="19" y2="12"></line>
    <polyline points="12 5 19 12 12 19"></polyline>
    </svg>
    </div>
    </div>
    <!-- Card 2: Módulos Operacionais (Ativo) -->
    <a href="/modulos" target="_self" class="sofi-card-link">
    <div class="sofi-card">
    <div class="sofi-card-icon-container">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
    <line x1="9" y1="22" x2="9" y2="16"></line>
    <line x1="15" y1="22" x2="15" y2="16"></line>
    <line x1="9" y1="16" x2="15" y2="16"></line>
    <path d="M8 6h.01"></path>
    <path d="M16 6h.01"></path>
    <path d="M8 10h.01"></path>
    <path d="M16 10h.01"></path>
    </svg>
    </div>
    <h3 class="sofi-card-title">Módulos Operacionais</h3>
    <p class="sofi-card-desc">Acesse os processos e rotinas operacionais do sistema.</p>
    <div class="sofi-card-arrow-container">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <line x1="5" y1="12" x2="19" y2="12"></line>
    <polyline points="12 5 19 12 12 19"></polyline>
    </svg>
    </div>
    </div>
    </a>
    <!-- Card 3: Histórico e Logs (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
    <div class="sofi-card-icon-container">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
    <line x1="16" y1="13" x2="8" y2="13"></line>
    <line x1="16" y1="17" x2="8" y2="17"></line>
    <polyline points="10 9 9 9 8 9"></polyline>
    </svg>
    </div>
    <h3 class="sofi-card-title">Histórico e Logs</h3>
    <p class="sofi-card-desc">Consulte o histórico de atividades e registros do sistema.</p>
    <div class="sofi-card-arrow-container">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <line x1="5" y1="12" x2="19" y2="12"></line>
    <polyline points="12 5 19 12 12 19"></polyline>
    </svg>
    </div>
    </div>
    <!-- Card 4: Documentação (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
    <div class="sofi-card-icon-container">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
    </svg>
    </div>
    <h3 class="sofi-card-title">Documentação</h3>
    <p class="sofi-card-desc">Acesse manuais, guias e materiais de apoio do sistema.</p>
    <div class="sofi-card-arrow-container">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <line x1="5" y1="12" x2="19" y2="12"></line>
    <polyline points="12 5 19 12 12 19"></polyline>
    </svg>
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)

else:
    # Tela de Seleção de Departamento
    st.markdown("""
    <div class="sofi-title-container">
    <h1 class="sofi-main-title">Selecione o Departamento</h1>
    <p class="sofi-sub-title">Selecione a sua área de atuação para acessar as ferramentas dedicadas.</p>
    </div>
    """, unsafe_allow_html=True)

    # Grid de 3 Cards de Departamento
    st.markdown("""
    <div class="sofi-card-grid-3">
    <!-- Card 1: Financeiro (Ativo) -->
    <a href="/?dept=Financeiro" target="_self" class="sofi-card-link">
    <div class="sofi-card">
    <div class="sofi-card-icon-container">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <line x1="12" y1="1" x2="12" y2="23"></line>
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
    </svg>
    </div>
    <h3 class="sofi-card-title">Financeiro</h3>
    <p class="sofi-card-desc">Gestão de notas fiscais, conciliações, relatórios e fluxos operacionais.</p>
    <div class="sofi-card-arrow-container">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <line x1="5" y1="12" x2="19" y2="12"></line>
    <polyline points="12 5 19 12 12 19"></polyline>
    </svg>
    </div>
    </div>
    </a>

    <!-- Card 2: RH (Em breve) -->
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
    <h3 class="sofi-card-title">RH</h3>
    <p class="sofi-card-desc">Gestão de funcionários, admissões, férias e relatórios de departamento pessoal.</p>
    <div class="sofi-card-arrow-container">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <line x1="5" y1="12" x2="19" y2="12"></line>
    <polyline points="12 5 19 12 12 19"></polyline>
    </svg>
    </div>
    </div>

    <!-- Card 3: Compras (Em breve) -->
    <div class="sofi-card disabled">
    <span class="sofi-card-badge">Em Breve</span>
    <div class="sofi-card-icon-container">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="9" cy="21" r="1"></circle>
    <circle cx="20" cy="21" r="1"></circle>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
    </svg>
    </div>
    <h3 class="sofi-card-title">Compras</h3>
    <p class="sofi-card-desc">Controle de suprimentos, cotações de preços e pedidos de fornecedores.</p>
    <div class="sofi-card-arrow-container">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0078C8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <line x1="5" y1="12" x2="19" y2="12"></line>
    <polyline points="12 5 19 12 12 19"></polyline>
    </svg>
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)
