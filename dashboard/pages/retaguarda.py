import streamlit as st
import sys
import threading
import subprocess
import time
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
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
    ("Retaguarda", "/retaguarda"),
])

# Referencias para os scripts
<<<<<<< Updated upstream
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPT_RETAGUARDA = ROOT_DIR / "departments" / "financeiro" / "modules" / "retaguarda" / "extrator_retaguarda.py"
DB_PATH = ROOT_DIR / "core" / "database" / "sofi.db"
=======
SCRIPT_RETAGUARDA = ROOT_DIR / "departments" / "financeiro" / "modules" / "retaguarda" / "extrator_retaguarda.py"
DB_PATH = ROOT_DIR / os.getenv("LOG_DB_PATH", "core/database/sofi.db")

>>>>>>> Stashed changes

# Inicia variáveis na sessão
if "retaguarda_process_running" not in st.session_state:
    st.session_state.retaguarda_process_running = False

# Função que roda o processo
def run_retaguarda_process(unidade, data_str=None):
    try:
        # Monta o comando
        cmd_args = f'"{sys.executable}" "{SCRIPT_RETAGUARDA}" --unidade {unidade}'
        if data_str:
            cmd_args += f' --data {data_str}'
            
        full_cmd = f'cmd.exe /c "{cmd_args}"'
        
        # Abre console visível no Windows
        subprocess.run(full_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as e:
        print(f"Erro inesperado ao lançar subprocesso do Retaguarda: {e}")

# Cabeçalho estilo Sage (Foto 2)
st.markdown("""<div class="sofi-title-container">
<p class="sage-section-title">ATIVIDADES</p>
<h1 class="sage-page-title">MÓDULO RETAGUARDA</h1>
<p class="sofi-sub-title">Extração automática de receitas de vendas e upload direto no FinançasGB.</p>
</div>""", unsafe_allow_html=True)

col_form, col_space = st.columns([2, 1])

with col_form:
    # Seleção da Unidade
    st.markdown("**UNIDADE:**")
    unidade = st.radio("", ["BH", "UDI"], horizontal=True, label_visibility="collapsed")
    
    st.write("")
    
    # Seleção da Data
    st.markdown("**PERÍODO:**")
    tipo_data = st.radio("", ["D-1 (Ontem)", "Data Específica"], horizontal=True, label_visibility="collapsed")
    
    data_selecionada = None
    if tipo_data == "Data Específica":
        st.markdown("**DATA BASE:**")
        data_selecionada = st.date_input("", datetime.now() - timedelta(days=1), label_visibility="collapsed")
    
    st.write("")
    
    # Botão de Ação estilo Sage
    if not st.session_state.retaguarda_process_running:
        if st.button("✔ Executar Relatório e Importação", type="primary", use_container_width=False):
            st.session_state.retaguarda_process_running = True
            
            if tipo_data == "D-1 (Ontem)":
                data_ontem = datetime.now() - timedelta(days=1)
                data_str = data_ontem.strftime("%d/%m/%Y")
            else:
                data_str = data_selecionada.strftime("%d/%m/%Y") if data_selecionada else (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
            
            thread = threading.Thread(target=run_retaguarda_process, args=(unidade, data_str))
            thread.daemon = True 
            thread.start()
            st.session_state.retaguarda_thread = thread
            st.rerun()
    else:
        st.button("⏳ Processo em execução...", type="secondary", disabled=True)

# Função para ler os últimos logs
def get_recent_logs():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Pega as últimas 5 execuções gerais para a tabela
            df_history = pd.read_sql(
                "SELECT id, modulo, status, timestamp, usuario FROM execution_logs WHERE modulo LIKE 'Retaguarda%' ORDER BY id DESC LIMIT 5", 
                conn
            )
            
            # Pega a última execução detalhada para exibir o console
            df_console = pd.read_sql(
                "SELECT status, mensagem, modulo FROM execution_logs WHERE modulo LIKE 'Retaguarda%' ORDER BY id DESC LIMIT 1", 
                conn
            )
            
            return df_history, df_console
    except Exception as e:
        return None, None

st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)
st.markdown("**Console em Tempo Real**")

with st.container(height=350):
    log_container = st.empty()
    
history_container = st.empty()

# Lógica de atualização em tempo real
thread = st.session_state.get("retaguarda_thread")
is_running = thread is not None and thread.is_alive()

def render_logs():
    df_history, df_console = get_recent_logs()
    
    if df_console is not None and not df_console.empty:
        status = df_console.iloc[0]['status']
        modulo = df_console.iloc[0]['modulo']
        msg = df_console.iloc[0]['mensagem']
        
        console_text = f"[{modulo}] STATUS: {status}\n\n{msg}"
        log_container.code(console_text, language="shell")
    else:
        log_container.info("Nenhum log do Módulo Retaguarda encontrado.")
        
    if df_history is not None and not df_history.empty:
        history_container.markdown("#### Últimas Execuções do Módulo")
        history_container.dataframe(df_history, use_container_width=True, hide_index=True)

if is_running:
    # Loop que atualiza a tela enquanto a thread estiver viva
    while thread.is_alive():
        render_logs()
        time.sleep(1.5)
    
    # Quando terminar, volta o estado para False
    st.session_state.retaguarda_process_running = False
    st.rerun()
else:
    # Se não está rodando, apenas renderiza uma vez
    render_logs()
    
    if st.button("↻ Atualizar Logs"):
        st.rerun()

st.markdown("""<div style="margin-top:20px; margin-bottom:30px;">
<a href="/financeiro" target="_self" class="sofi-back-link">&#8592; Voltar para Módulos Financeiros</a>
</div>""", unsafe_allow_html=True)
