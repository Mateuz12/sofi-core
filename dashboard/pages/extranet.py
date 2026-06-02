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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from components.layout import render_layout

render_layout()

# Referencias para os scripts
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPT_BH = ROOT_DIR / "departments" / "financeiro" / "modules" / "extranet" / "BH" / "extranet_reports_bh.py"
SCRIPT_UDI = ROOT_DIR / "departments" / "financeiro" / "modules" / "extranet" / "UDI" / "extranet_reports_udi.py"
DB_PATH = ROOT_DIR / "core" / "database" / "sofi.db"

# Inicia variáveis na sessão
if "extranet_process_running" not in st.session_state:
    st.session_state.extranet_process_running = False

# Função que roda o processo
def run_extranet_process(unidade, data_str=None, dias=None):
    try:
        script_path = SCRIPT_BH if unidade == "BH" else SCRIPT_UDI
        
        # Monta o comando
        cmd_args = f'"{sys.executable}" "{script_path}"'
        if data_str:
            cmd_args += f' --data {data_str}'
        if dias:
            cmd_args += f' --dias {dias}'
            
        full_cmd = f'cmd.exe /c "{cmd_args} || pause"'
        
        # Abre console visível no Windows
        subprocess.run(full_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as e:
        print(f"Erro inesperado ao lançar subprocesso do Extranet: {e}")

# Cabeçalho da página (Design SAGE alinhado à esquerda)
st.markdown("""
<div class="sofi-title-container">
    <h1 class="sofi-main-title">Módulo Extranet</h1>
    <p class="sofi-sub-title">Extração automática de relatórios da Extranet do Grupo Boticário e importação automática para o FinançasGB.</p>
</div>
""", unsafe_allow_html=True)

col_center = st.columns([1, 2, 1])[1]

with col_center:
    # Seleção da Unidade
    unidade = st.radio("Escolha a Unidade:", ["BH", "UDI"], horizontal=True)
    
    # Seleção da Data
    tipo_data = st.radio("Período do Relatório:", ["D-1 (Ontem)", "Data Específica"], horizontal=True)
    
    data_selecionada = None
    if tipo_data == "Data Específica":
        data_selecionada = st.date_input("Selecione a Data:", datetime.now() - timedelta(days=1))
    
    st.write("") # Espaçador
    
    # Botão de Ação
    if not st.session_state.extranet_process_running:
        if st.button("▶ Executar Relatório e Importação", type="primary", use_container_width=True):
            st.session_state.extranet_process_running = True
            
            # Formata data (sempre fornecida para evitar prompt no terminal)
            dias = None
            if tipo_data == "D-1 (Ontem)":
                data_ontem = datetime.now() - timedelta(days=1)
                data_str = data_ontem.strftime("%d/%m/%Y")
            else:
                data_str = data_selecionada.strftime("%d/%m/%Y") if data_selecionada else (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
                dias = 1
            
            # Dispara a thread em background
            thread = threading.Thread(target=run_extranet_process, args=(unidade, data_str, dias))
            thread.daemon = True 
            thread.start()
            
            st.session_state.extranet_thread = thread
            st.rerun()
    else:
        st.button("⏳ Processo em execução...", type="secondary", disabled=True, use_container_width=True)

# Função para ler os últimos logs
def get_recent_logs():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Pega as últimas 5 execuções gerais para a tabela
            df_history = pd.read_sql(
                "SELECT id, modulo, status, timestamp, usuario FROM execution_logs WHERE modulo LIKE 'Extranet%' ORDER BY id DESC LIMIT 5", 
                conn
            )
            
            # Pega a última execução detalhada para exibir o console
            df_console = pd.read_sql(
                "SELECT status, mensagem, modulo FROM execution_logs WHERE modulo LIKE 'Extranet%' ORDER BY id DESC LIMIT 1", 
                conn
            )
            
            return df_history, df_console
    except Exception as e:
        return None, None

st.divider()
st.markdown("### 🖥️ Console em Tempo Real")

with st.container(height=350):
    log_container = st.empty()
    
history_container = st.empty()

# Lógica de atualização em tempo real
thread = st.session_state.get("extranet_thread")
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
        log_container.info("Nenhum log do Módulo Extranet encontrado.")
        
    if df_history is not None and not df_history.empty:
        history_container.markdown("#### Últimas Execuções do Módulo")
        history_container.dataframe(df_history, use_container_width=True, hide_index=True)

if is_running:
    # Loop que atualiza a tela enquanto a thread estiver viva
    while thread.is_alive():
        render_logs()
        time.sleep(1.5)
    
    # Quando terminar, volta o estado para False
    st.session_state.extranet_process_running = False
    st.rerun()
else:
    # Se não está rodando, apenas renderiza uma vez
    render_logs()
    
    if st.button("↻ Atualizar Logs"):
        st.rerun()

st.markdown("""
<div style="text-align: left; margin-top: 20px; margin-bottom: 40px;">
    <a href="/financeiro" target="_self" class="sofi-back-link">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
        Voltar para Módulos Financeiros
    </a>
</div>
""", unsafe_allow_html=True)
