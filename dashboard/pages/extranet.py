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
DASHBOARD_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = DASHBOARD_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from core.sofi_env import load_sofi_env
load_sofi_env()

import os
from components.layout import render_layout

render_layout(nav_links=[
    ("Módulos", "/financeiro"),
    ("Extranet", "/extranet"),
])

# Referencias para os scripts
SCRIPT_BH  = ROOT_DIR / "departments" / "financeiro" / "modules" / "extranet" / "BH"  / "extranet_reports_bh.py"
SCRIPT_UDI = ROOT_DIR / "departments" / "financeiro" / "modules" / "extranet" / "UDI" / "extranet_reports_udi.py"
DB_PATH    = ROOT_DIR / os.getenv("LOG_DB_PATH", "core/database/sofi.db")


# Estado de sessão
if "extranet_process_running" not in st.session_state:
    st.session_state.extranet_process_running = False

def run_extranet_process(unidade, data_str=None, dias=None):
    try:
        script_path = SCRIPT_BH if unidade == "BH" else SCRIPT_UDI
        cmd_args = f'"{sys.executable}" "{script_path}"'
        if data_str:
            cmd_args += f' --data {data_str}'
        if dias:
            cmd_args += f' --dias {dias}'
        full_cmd = f'cmd.exe /c "{cmd_args}"'
        subprocess.run(full_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as e:
        print(f"Erro inesperado ao lançar subprocesso do Extranet: {e}")

# ─── Cabeçalho estilo Sage (Foto 2) ───────────────────────────────────────────
st.markdown("""
<div class="sofi-title-container">
    <p class="sage-section-title">ATIVIDADES</p>
    <h1 class="sage-page-title">MÓDULO EXTRANET</h1>
    <p class="sofi-sub-title">Extração automática de relatórios da Extranet do Grupo Boticário e importação para o FinançasGB.</p>
</div>
""", unsafe_allow_html=True)

# ─── Formulário estilo Sage ────────────────────────────────────────────────────
col_form, col_space = st.columns([2, 1])

with col_form:
    # Unidade
    st.markdown("**UNIDADE:**")
    unidade = st.radio("", ["BH", "UDI"], horizontal=True, label_visibility="collapsed")

    st.write("")

    # Período
    st.markdown("**PERÍODO:**")
    tipo_data = st.radio("", ["D-1 (Ontem)", "Data Específica"], horizontal=True, label_visibility="collapsed")

    data_selecionada = None
    if tipo_data == "Data Específica":
        st.markdown("**DATA BASE:**")
        data_selecionada = st.date_input("", datetime.now() - timedelta(days=1), label_visibility="collapsed")

    st.write("")

    # ─── Botões de ação estilo Sage Bootstrap ─────────────────────────────────
    if not st.session_state.extranet_process_running:
        st.markdown("""
        <div class="sage-btn-group">
            <span style="font-size:12px; color:#555; align-self:center;">Clique para executar:</span>
        </div>
        """, unsafe_allow_html=True)

        if st.button("✔ Executar Relatório e Importação", type="primary", use_container_width=False):
            st.session_state.extranet_process_running = True

            dias = None
            if tipo_data == "D-1 (Ontem)":
                data_ontem = datetime.now() - timedelta(days=1)
                data_str = data_ontem.strftime("%d/%m/%Y")
            else:
                data_str = data_selecionada.strftime("%d/%m/%Y") if data_selecionada else (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
                dias = 1

            thread = threading.Thread(target=run_extranet_process, args=(unidade, data_str, dias))
            thread.daemon = True
            thread.start()
            st.session_state.extranet_thread = thread
            st.rerun()
    else:
        st.button("⏳ Processo em execução...", type="secondary", disabled=True)

# ─── Divisor ─────────────────────────────────────────────────────────────────
st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)

# ─── Console e Histórico ─────────────────────────────────────────────────────
st.markdown("**Console em Tempo Real**")

def get_recent_logs():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df_history = pd.read_sql(
                "SELECT id, modulo, status, timestamp, usuario FROM execution_logs WHERE modulo LIKE 'Extranet%' ORDER BY id DESC LIMIT 5",
                conn,
            )
            df_console = pd.read_sql(
                "SELECT status, mensagem, modulo FROM execution_logs WHERE modulo LIKE 'Extranet%' ORDER BY id DESC LIMIT 1",
                conn,
            )
            return df_history, df_console
    except Exception:
        return None, None

with st.container(height=320):
    log_container = st.empty()

history_container = st.empty()

thread = st.session_state.get("extranet_thread")
is_running = thread is not None and thread.is_alive()

def render_logs():
    df_history, df_console = get_recent_logs()
    if df_console is not None and not df_console.empty:
        status = df_console.iloc[0]["status"]
        modulo = df_console.iloc[0]["modulo"]
        msg    = df_console.iloc[0]["mensagem"]
        log_container.code(f"[{modulo}] STATUS: {status}\n\n{msg}", language="shell")
    else:
        log_container.info("Nenhum log do Módulo Extranet encontrado.")

    if df_history is not None and not df_history.empty:
        history_container.markdown("**Últimas Execuções do Módulo**")
        history_container.dataframe(df_history, use_container_width=True, hide_index=True)

if is_running:
    while thread.is_alive():
        render_logs()
        time.sleep(1.5)
    st.session_state.extranet_process_running = False
    st.rerun()
else:
    render_logs()
    if st.button("↻ Atualizar Logs"):
        st.rerun()

# ─── Voltar ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:20px; margin-bottom:30px;">
    <a href="/financeiro" target="_self" class="sofi-back-link">&#8592; Voltar para Módulos Financeiros</a>
</div>
""", unsafe_allow_html=True)
