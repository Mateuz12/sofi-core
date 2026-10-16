import os
import sys
import time
import sqlite3
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# Configuração do caminho
DASHBOARD_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = DASHBOARD_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from core.sofi_env import load_sofi_env
load_sofi_env()

from components.layout import render_layout

render_layout(nav_links=[
    ("Módulos", "/financeiro"),
    ("Depósitos", "/depositos"),
])

# Referências para o script e banco
MODULO_DIR = ROOT_DIR / "departments" / "financeiro" / "modules" / "depositos"
SCRIPT_DEPOSITOS = MODULO_DIR / "script_depositos.py"
RELATORIOS_DIR = MODULO_DIR / "output" / "relatorios"
DB_PATH = ROOT_DIR / os.getenv("LOG_DB_PATH", "core/database/sofi.db")

# Estado na sessão
if "depositos_process_running" not in st.session_state:
    st.session_state.depositos_process_running = False


def run_depositos_process(data_str: str, is_dry_run: bool, forcar_reenvio: bool):
    try:
        cmd_args = f'"{sys.executable}" "{SCRIPT_DEPOSITOS}" --data {data_str}'
        if is_dry_run:
            cmd_args += " --dry-run"
        if forcar_reenvio:
            cmd_args += " --forcar-reenvio"

        full_cmd = f'cmd.exe /c "{cmd_args}"'
        subprocess.run(full_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as e:
        print(f"Erro inesperado ao lançar subprocesso de Depósitos: {e}")


# ─── Cabeçalho estilo Sage ───────────────────────────────────────────────────
st.markdown("""<div class="sofi-title-container">
<p class="sage-section-title">ATIVIDADES</p>
<h1 class="sage-page-title">MÓDULO DEPÓSITOS</h1>
<p class="sofi-sub-title">Lançamento automatizado em lote de depósitos bancários na API do FinançasGB com controle de duplicidade.</p>
</div>""", unsafe_allow_html=True)

col_form, col_space = st.columns([2, 1])

with col_form:
    st.markdown("**UNIDADE:**")
    unidade = st.radio("", ["UDI (22 Lojas)"], horizontal=True, label_visibility="collapsed")

    st.write("")

    st.markdown("**PERÍODO (ABA DA PLANILHA):**")
    tipo_data = st.radio(
        "",
        ["D-1 (Ontem)", "Hoje (D-0)", "Data Específica"],
        horizontal=True,
        label_visibility="collapsed",
    )

    data_selecionada = None
    if tipo_data == "Data Específica":
        st.markdown("**DATA DO DEPÓSITO:**")
        data_selecionada = st.date_input("", datetime.now() - timedelta(days=1), label_visibility="collapsed")

    st.write("")

    st.markdown("**MODO DE EXECUÇÃO:**")
    modo_exec = st.radio(
        "",
        ["Simulação (Dry-Run)", "Lançamento Real (API FinançasGB)"],
        horizontal=True,
        label_visibility="collapsed",
    )
    is_dry_run = modo_exec.startswith("Simulação")

    forcar_reenvio = False
    if not is_dry_run:
        forcar_reenvio = st.checkbox(
            "Ignorar trava de duplicidade (forçar reenvio de lojas já lançadas no dia)",
            value=False,
        )

    st.write("")

    btn_label = "🔍 Executar Simulação (Dry-Run)" if is_dry_run else "✔ Executar Lançamento de Depósitos"
    if not st.session_state.depositos_process_running:
        if st.button(btn_label, type="primary", use_container_width=False):
            st.session_state.depositos_process_running = True

            if tipo_data == "D-1 (Ontem)":
                data_ref = datetime.now() - timedelta(days=1)
            elif tipo_data == "Hoje (D-0)":
                data_ref = datetime.now()
            else:
                data_ref = data_selecionada if data_selecionada else (datetime.now() - timedelta(days=1))

            data_str = data_ref.strftime("%d.%m.%Y")

            thread = threading.Thread(
                target=run_depositos_process,
                args=(data_str, is_dry_run, forcar_reenvio),
            )
            thread.daemon = True
            thread.start()
            st.session_state.depositos_thread = thread
            st.rerun()
    else:
        st.button("⏳ Processo em execução...", type="secondary", disabled=True)


def get_recent_logs():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df_history = pd.read_sql(
                "SELECT id, modulo, status, timestamp, usuario FROM execution_logs WHERE modulo LIKE 'Depósitos%' ORDER BY id DESC LIMIT 5",
                conn,
            )
            df_console = pd.read_sql(
                "SELECT status, mensagem, modulo FROM execution_logs WHERE modulo LIKE 'Depósitos%' ORDER BY id DESC LIMIT 1",
                conn,
            )
            return df_history, df_console
    except Exception:
        return None, None


def get_latest_report():
    try:
        if not RELATORIOS_DIR.exists():
            return None, None
        arquivos = sorted(RELATORIOS_DIR.glob("relatorio_depositos_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not arquivos:
            return None, None
        ultimo = arquivos[0]
        df_rep = pd.read_excel(ultimo)
        return ultimo, df_rep
    except Exception:
        return None, None


st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)
st.markdown("**Console em Tempo Real**")

with st.container(height=320):
    log_container = st.empty()

report_container = st.empty()
history_container = st.empty()

thread = st.session_state.get("depositos_thread")
is_running = thread is not None and thread.is_alive()


def render_logs():
    df_history, df_console = get_recent_logs()

    if df_console is not None and not df_console.empty:
        status = df_console.iloc[0]["status"]
        modulo = df_console.iloc[0]["modulo"]
        msg = df_console.iloc[0]["mensagem"]
        log_container.code(f"[{modulo}] STATUS: {status}\n\n{msg}", language="shell")
    else:
        log_container.info("Nenhum log do Módulo Depósitos encontrado.")

    ultimo_arq, df_rep = get_latest_report()
    if ultimo_arq is not None and df_rep is not None and not df_rep.empty:
        with report_container.container():
            st.markdown(f"#### Último Relatório Gerado (`{ultimo_arq.name}`)")
            st.dataframe(df_rep, use_container_width=True, hide_index=True)

    if df_history is not None and not df_history.empty:
        with history_container.container():
            st.markdown("#### Últimas Execuções do Módulo")
            st.dataframe(df_history, use_container_width=True, hide_index=True)


if is_running:
    while thread.is_alive():
        render_logs()
        time.sleep(1.5)
    st.session_state.depositos_process_running = False
    st.rerun()
else:
    render_logs()
    col_b1, col_b2 = st.columns([1, 4])
    with col_b1:
        if st.button("↻ Atualizar Logs"):
            st.rerun()
    ultimo_arq, _ = get_latest_report()
    if ultimo_arq and ultimo_arq.exists():
        with col_b2:
            with open(ultimo_arq, "rb") as f:
                st.download_button(
                    label=f"⬇ Baixar Relatório ({ultimo_arq.name})",
                    data=f.read(),
                    file_name=ultimo_arq.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

st.markdown("""<div style="margin-top:20px; margin-bottom:30px;">
<a href="/financeiro" target="_self" class="sofi-back-link">&#8592; Voltar para Módulos Financeiros</a>
</div>""", unsafe_allow_html=True)
