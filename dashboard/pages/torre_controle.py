import streamlit as st
import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Resolução de caminhos
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.sofi_env import load_sofi_env
load_sofi_env()

from components.layout import render_layout
from core.config import ConfigManager
from core.scheduler.scheduler import (
    get_scheduler_status,
    resume_scheduler,
    pause_scheduler
)

# Render Layout Sage
render_layout(nav_links=[
    ("Módulos", "/financeiro"),
    ("Torre de Controle", "/torre_controle"),
])

cm = ConfigManager()
DB_PATH = ROOT_DIR / os.getenv("LOG_DB_PATH", "core/database/sofi.db")

# ─────────────────────────────────────────────────────────────
# Funções Auxiliares de Métricas NOC
# ─────────────────────────────────────────────────────────────
def get_noc_metrics():
    now = datetime.now()
    since = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    sucessos, falhas, total = 0, 0, 0
    
    try:
        with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
            df = pd.read_sql(
                "SELECT status FROM execution_logs WHERE timestamp >= ?",
                conn,
                params=(since,)
            )
            if not df.empty:
                total = len(df)
                sucessos = len(df[df["status"].str.upper().str.contains("SUCESSO|CONCLUIDO", na=False)])
                falhas = len(df[df["status"].str.upper().str.contains("ERRO|FALHA", na=False)])
    except Exception as e:
        print(f"[NOC] Erro ao buscar logs: {e}")

    sched_status = get_scheduler_status()
    taxa = round((sucessos / total * 100), 1) if total > 0 else 100.0

    return {
        "sched_running": sched_status.get("running", False),
        "next_job": sched_status.get("next_job", "--"),
        "sucessos": sucessos,
        "falhas": falhas,
        "total": total,
        "taxa": taxa,
    }

# ─────────────────────────────────────────────────────────────
# Cabeçalho Sage
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="sofi-title-container">
    <p class="sage-section-title">ADMINISTRAÇÃO</p>
    <h1 class="sage-page-title">TORRE DE CONTROLE</h1>
    <p class="sofi-sub-title">Gestão de variáveis dinâmicas, agendamentos, notificações e integridade operacional.</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Header Executivo NOC (Cards de Saúde)
# ─────────────────────────────────────────────────────────────
metrics = get_noc_metrics()
sched_class = "noc-ok" if metrics["sched_running"] else "noc-error"
sched_label = "Ativo" if metrics["sched_running"] else "Pausado"

exec_class = "noc-ok" if metrics["falhas"] == 0 else "noc-error"

st.markdown(f"""
<div class="sofi-noc-grid">
    <div class="sofi-noc-card {sched_class}">
        <span class="sofi-noc-card-label">Agendador Central</span>
        <span class="sofi-noc-card-value">{sched_label}</span>
        <span class="sofi-noc-card-detail">Próximo: {metrics["next_job"]}</span>
    </div>
    <div class="sofi-noc-card {exec_class}">
        <span class="sofi-noc-card-label">Execuções 24h</span>
        <span class="sofi-noc-card-value">{metrics["sucessos"]} ✓ / {metrics["falhas"]} ✗</span>
        <span class="sofi-noc-card-detail">Taxa: {metrics["taxa"]}% de sucesso ({metrics["total"]} jobs)</span>
    </div>
    <div class="sofi-noc-card noc-info">
        <span class="sofi-noc-card-label">Próximo Disparo</span>
        <span class="sofi-noc-card-value">{metrics["next_job"].split()[-1] if metrics["next_job"] != "--" else "--:--"}</span>
        <span class="sofi-noc-card-detail">{" ".join(metrics["next_job"].split()[:-1]) if metrics["next_job"] != "--" else "Sem execuções pendentes"}</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Abas de Controle
# ─────────────────────────────────────────────────────────────
tab_sched, tab_notif, tab_param, tab_audit = st.tabs([
    "⏰ Agendamentos & Jobs",
    "📧 Notificações & Alertas",
    "🏷️ Prazos PDV",
    "📜 Auditoria & Histórico"
])

# ─────────────────────────────────────────────────────────────
# Aba 1: Agendamentos & Jobs
# ─────────────────────────────────────────────────────────────
with tab_sched:
    c_title, c_ctrl = st.columns([3, 2])
    c_title.markdown("**Gerenciamento de Jobs e Horários (APScheduler)**")
    c_title.caption("Alterações de horários ou ativação de jobs aplicam hot-reload imediato ao agendador.")

    if not metrics["sched_running"]:
        if c_ctrl.button("▶ Iniciar / Despausar Agendador", type="primary", use_container_width=True):
            resume_scheduler()
            st.success("Agendador central iniciado e despausado!")
            st.rerun()
    else:
        if c_ctrl.button("⏸ Pausar Agendador", type="secondary", use_container_width=True):
            pause_scheduler()
            st.warning("Agendador central pausado.")
            st.rerun()

    st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)

    sched_cfg = cm.get_scheduler_config()
    jobs_list = [j.model_dump() for j in sched_cfg.jobs]

    updated_jobs = []
    
    col1, col2 = st.columns([1, 1])
    for idx, j in enumerate(jobs_list):
        col = col1 if idx % 2 == 0 else col2
        with col:
            with st.container(border=True):
                c_head1, c_head2 = st.columns([3, 1])
                j_name = j.get("name", "Job")
                enabled = c_head2.checkbox("Ativo", value=j.get("enabled", True), key=f"job_en_{idx}")
                c_head1.markdown(f"**{j_name}**")
                
                s_info = j.get("schedule", {})
                curr_hour = int(s_info.get("hour", 7))
                curr_min = int(s_info.get("minute", 0))
                
                t_col1, t_col2, t_col3 = st.columns([2, 1, 1])
                
                import datetime as dt_module
                new_time = t_col1.time_input(
                    "Horário",
                    value=dt_module.time(curr_hour, curr_min),
                    key=f"job_time_{idx}"
                )
                
                dias = t_col2.number_input(
                    "Dias Retroativos",
                    value=int(j.get("dias", 0)),
                    min_value=0,
                    max_value=30,
                    help="Quantidade de dias passados a consultar no portal (ex: 0 = hoje D-0, 1 = ontem D-1, 5 = últimos 5 dias)",
                    key=f"job_dias_{idx}"
                )
                
                retry_attempts = t_col3.number_input(
                    "Retries",
                    value=int(j.get("retry", {}).get("max_attempts", 3)),
                    min_value=1,
                    max_value=10,
                    key=f"job_retry_{idx}"
                )
                
                j_copy = dict(j)
                j_copy["enabled"] = enabled
                j_copy["dias"] = int(dias)
                j_copy["schedule"]["hour"] = new_time.hour
                j_copy["schedule"]["minute"] = new_time.minute
                j_copy["retry"]["max_attempts"] = int(retry_attempts)
                updated_jobs.append(j_copy)

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.session_state.get("_saving_scheduler"):
        st.button("⏳ Aplicando e reagendando...", type="secondary", disabled=True)
    else:
        if st.button("✔ Salvar Horários & Aplicar Hot-Reload", type="primary"):
            st.session_state["_saving_scheduler"] = True
            
            new_payload = {
                "enabled": sched_cfg.enabled,
                "timezone": sched_cfg.timezone,
                "jobs": updated_jobs
            }
            
            # Obtém instância do scheduler ativo em memória se existir
            sched_instance = None
            try:
                from core.scheduler.scheduler import _scheduler_instance
                sched_instance = _scheduler_instance
            except Exception:
                pass

            res = cm.save_scheduler(new_payload, scheduler_instance=sched_instance)
            st.session_state["_saving_scheduler"] = False
            
            if res.success:
                st.success(f"Configuração do Scheduler salva e reagendada com sucesso! ({len(res.diff_entries)} alteração(ões))")
                st.rerun()
            else:
                st.error(f"Erro ao salvar: {', '.join(res.errors)}")

# ─────────────────────────────────────────────────────────────
# Aba 2: Notificações & Alertas
# ─────────────────────────────────────────────────────────────
with tab_notif:
    st.markdown("**Destinatários de E-mails por Grupo de Notificação**")
    st.caption("E-mails adicionados são validados pelo padrão RFC e recebem resumos automáticos pós-execução.")

    notif_cfg = cm.get_notificacoes_config()
    grupos = notif_cfg.grupos

    updated_grupos = {}
    
    for grp_key, grp_obj in grupos.items():
        with st.expander(f"📁 Grupo: {grp_key.upper().replace('_', ' ')}", expanded=True):
            st.markdown(f"*Jobs vinculados:* {', '.join(grp_obj.jobs_vinculados) if grp_obj.jobs_vinculados else 'Todos'}")
            
            emails_list = [str(e) for e in grp_obj.emails]
            emails_text = st.text_area(
                "Destinatários (um e-mail por linha)",
                value="\n".join(emails_list),
                key=f"grp_emails_{grp_key}",
                height=100
            )
            
            parsed_emails = [e.strip() for e in emails_text.splitlines() if e.strip()]
            updated_grupos[grp_key] = {
                "jobs_vinculados": grp_obj.jobs_vinculados,
                "emails": parsed_emails
            }

    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state.get("_saving_notif"):
        st.button("⏳ Salvando notificações...", type="secondary", disabled=True)
    else:
        if st.button("✔ Salvar Destinatários", type="primary"):
            st.session_state["_saving_notif"] = True
            payload = {
                "smtp": notif_cfg.smtp.model_dump(),
                "grupos": updated_grupos,
                "enviar_em_sucesso": notif_cfg.enviar_em_sucesso,
                "enviar_em_erro": notif_cfg.enviar_em_erro
            }
            res = cm.save_notificacoes(payload)
            st.session_state["_saving_notif"] = False
            if res.success:
                st.success(f"Destinatários salvos com sucesso! ({len(res.diff_entries)} alteração(ões))")
                st.rerun()
            else:
                st.error(f"Erro ao salvar: {', '.join(res.errors)}")

# ─────────────────────────────────────────────────────────────
# Aba 3: Prazos PDV
# ─────────────────────────────────────────────────────────────
with tab_param:
    st.markdown("**Regras de Prazo de Pagamento por PDV (Módulo XML / Cálamo)**")
    st.caption("Prazos base (dias) aplicados na conferência de notas fiscais de entrada.")

    param_cfg = cm.get_parametros_config()
    prazos = dict(param_cfg.prazos_pagamento)
    
    default_prazo = prazos.pop("default", 30)

    p_col1, p_col2 = st.columns([1, 2])
    with p_col1:
        new_default = st.number_input("Prazo Padrão Geral (DEFAULT)", value=int(default_prazo), min_value=0)

    df_prazos = pd.DataFrame([
        {"PDV": str(k), "Prazo (dias)": int(v)} for k, v in prazos.items()
    ])

    st.markdown("**Lojas Específicas (UDI / BH)**")
    edited_df = st.data_editor(
        df_prazos,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_prazos"
    )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state.get("_saving_param"):
        st.button("⏳ Salvando prazos...", type="secondary", disabled=True)
    else:
        if st.button("✔ Salvar Prazos de Pagamento", type="primary"):
            st.session_state["_saving_param"] = True
            
            new_prazos_dict = {"default": int(new_default)}
            for _, row in edited_df.iterrows():
                pdv_clean = str(row["PDV"]).strip()
                if pdv_clean and pdv_clean.lower() != "nan":
                    try:
                        new_prazos_dict[pdv_clean] = int(row["Prazo (dias)"])
                    except (ValueError, TypeError):
                        pass

            payload = {"prazos_pagamento": new_prazos_dict}
            res = cm.save_parametros(payload)
            st.session_state["_saving_param"] = False
            if res.success:
                st.success(f"Prazos atualizados com sucesso! ({len(res.diff_entries)} alteração(ões))")
                st.rerun()
            else:
                st.error(f"Erro ao salvar: {', '.join(res.errors)}")

# ─────────────────────────────────────────────────────────────
# Aba 4: Auditoria & Histórico
# ─────────────────────────────────────────────────────────────
with tab_audit:
    st.markdown("**Trilha de Auditoria Granular de Configurações**")
    st.caption("Registro de todas as alterações realizadas, com usuário, chave modificada e valores antes/depois.")

    try:
        with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
            df_audit = pd.read_sql("""
                SELECT timestamp, usuario, dominio, chave, valor_anterior, valor_novo
                FROM configuration_audit_logs
                ORDER BY id DESC LIMIT 50
            """, conn)
            
        if not df_audit.empty:
            st.dataframe(df_audit, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro de alteração de configuração encontrado.")
    except Exception as e:
        st.warning(f"Não foi possível carregar auditoria: {e}")

    st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)
    st.markdown("**Últimas Execuções dos Robôs (Logs Operacionais)**")
    st.caption("Registro das últimas tentativas e disparos de automações disparadas pelo agendador ou manualmente.")

    try:
        with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
            df_exec = pd.read_sql("""
                SELECT id, timestamp, modulo, status, mensagem
                FROM execution_logs
                ORDER BY id DESC LIMIT 20
            """, conn)
        if not df_exec.empty:
            st.dataframe(df_exec, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum log de execução encontrado.")
    except Exception as e:
        st.warning(f"Não foi possível carregar logs de execução: {e}")

    st.markdown("<hr class='sage-divider'>", unsafe_allow_html=True)
    st.markdown("**Visualizador de Configurações Ativas (YAML Raw)**")
    
    sel_domain = st.selectbox(
        "Selecione o arquivo de configuração para inspecionar:",
        ["scheduler", "notificacoes", "parametros_negocio"]
    )
    
    file_to_view = ROOT_DIR / "config" / f"{sel_domain}.yaml"
    if file_to_view.exists():
        with open(file_to_view, "r", encoding="utf-8") as f:
            raw_text = f.read()
        st.code(raw_text, language="yaml")
    else:
        st.warning(f"Arquivo config/{sel_domain}.yaml não encontrado.")

# ─────────────────────────────────────────────────────────────
# Rodapé Sage com Link Voltar
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:30px; margin-bottom:30px;">
    <a href="/" target="_self" class="sofi-back-link">&#8592; Voltar para Módulos</a>
</div>
""", unsafe_allow_html=True)
