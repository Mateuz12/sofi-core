import streamlit as st
import sys
import threading
import subprocess
import time
import sqlite3
import pandas as pd
from pathlib import Path

# Configuração do caminho
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.sofi_env import load_sofi_env
load_sofi_env()

import os
from components.layout import render_layout

render_layout(nav_links=[
    ("Módulos", "/financeiro"),
    ("XML", "/xml"),
])

# Referencias para os scripts
SCRIPT_DEBUG = ROOT_DIR / "departments" / "financeiro" / "modules" / "xml" / "debug_meudanfe.py"
SCRIPT_GERADOR = ROOT_DIR / "departments" / "financeiro" / "modules" / "xml" / "gerador_relatorio.py"
DB_PATH = ROOT_DIR / os.getenv("LOG_DB_PATH", "core/database/sofi.db")


# Função que roda o processo completo
def run_xml_processes():
    try:
        # Comando CMD em uma única string para evitar que o subprocess escape as aspas no Windows (\")
        # O cmd.exe /c tira as primeiras e as últimas aspas, então envolvemos tudo num bloco de aspas duplas.
        full_cmd = f'cmd.exe /c ""{sys.executable}" "{SCRIPT_DEBUG}" && "{sys.executable}" "{SCRIPT_GERADOR}""'
        
        # creationflags=subprocess.CREATE_NEW_CONSOLE força a abertura de uma nova janela visível no Windows
        subprocess.run(full_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as e:
        print(f"Erro inesperado ao lançar subprocessos: {e}")

# Função que roda apenas a geração de relatório
def run_only_gerador():
    try:
        full_cmd = f'cmd.exe /c ""{sys.executable}" "{SCRIPT_GERADOR}""'
        subprocess.run(full_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as e:
        print(f"Erro inesperado ao lançar subprocessos: {e}")

# Inicia variáveis na sessão
if "xml_process_running" not in st.session_state:
    st.session_state.xml_process_running = False

# Cabeçalho estilo Sage (Foto 2)
st.markdown("""
<div class="sofi-title-container">
    <p class="sage-section-title">ATIVIDADES</p>
    <h1 class="sage-page-title">MÓDULO XML</h1>
    <p class="sofi-sub-title">Baixa XMLs via API e gera relatórios de conferência Cálamo.</p>
</div>
""", unsafe_allow_html=True)

col_form, col_space = st.columns([2, 1])

with col_form:
    # Botões de Ação estilo Sage Bootstrap
    if not st.session_state.xml_process_running:
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            if st.button("✔ Executar todo o processo", type="primary", use_container_width=False):
                st.session_state.xml_process_running = True
                thread = threading.Thread(target=run_xml_processes)
                thread.daemon = True 
                thread.start()
                st.session_state.xml_thread = thread
                st.rerun()
                
        with btn_col2:
            if st.button("📊 Apenas Gerar Relatório", type="secondary", use_container_width=False):
                st.session_state.xml_process_running = True
                thread = threading.Thread(target=run_only_gerador)
                thread.daemon = True 
                thread.start()
                st.session_state.xml_thread = thread
                st.rerun()
    else:
        st.button("⏳ Processo em execução...", type="secondary", disabled=True)

# Função para ler os últimos logs
def get_recent_logs():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Pega as últimas 5 execuções gerais para a tabela
            df_history = pd.read_sql("SELECT id, modulo, status, timestamp, usuario FROM execution_logs ORDER BY id DESC LIMIT 5", conn)
            
            # Pega a última execução detalhada para exibir o console
            df_console = pd.read_sql("SELECT status, mensagem, modulo FROM execution_logs WHERE modulo LIKE 'XML%' ORDER BY id DESC LIMIT 1", conn)
            
            return df_history, df_console
    except Exception as e:
        return None, None

st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)
st.markdown("**Console em Tempo Real**")

with st.container(height=400):
    log_container = st.empty()
    
history_container = st.empty()

# Lógica de atualização em tempo real
thread = st.session_state.get("xml_thread")
is_running = thread is not None and thread.is_alive()

def render_logs():
    df_history, df_console = get_recent_logs()
    
    if df_console is not None and not df_console.empty:
        status = df_console.iloc[0]['status']
        modulo = df_console.iloc[0]['modulo']
        msg = df_console.iloc[0]['mensagem']
        
        # Corrigir quebra de linha visualmente
        console_text = f"[{modulo}] STATUS: {status}\n\n{msg}"
        log_container.code(console_text, language="shell")
    else:
        log_container.info("Nenhum log do Módulo XML encontrado.")
        
    if df_history is not None and not df_history.empty:
        history_container.markdown("#### Últimas Execuções Gerais")
        history_container.dataframe(df_history, use_container_width=True, hide_index=True)

if is_running:
    # Loop que atualiza a tela enquanto a thread estiver viva
    while thread.is_alive():
        render_logs()
        time.sleep(1.5)
    
    # Quando terminar, volta o estado para False
    st.session_state.xml_process_running = False
    st.rerun()
else:
    # Se não está rodando, apenas renderiza uma vez
    render_logs()
    
    if st.button("↻ Atualizar Logs"):
        st.rerun()

st.markdown("""
<div style="margin-top:20px; margin-bottom:30px;">
    <a href="/financeiro" target="_self" class="sofi-back-link">&#8592; Voltar para Módulos Financeiros</a>
</div>
""", unsafe_allow_html=True)
