"""
core/notifier/smtp_notifier.py — Notificações do Scheduler SOFI via Gmail SMTP.

Envia um e-mail HTML consolidado com o resultado de todos os jobs do dia.
Usa apenas bibliotecas nativas do Python (smtplib + email.mime), sem
dependências externas.

Variáveis de ambiente necessárias (no .env raiz):
    SMTP_SERVER              — servidor SMTP (default: smtp.gmail.com)
    SMTP_PORT                — porta SMTP  (default: 587)
    SMTP_USER                — e-mail remetente (ex: sofi.notifier@gmail.com)
    SMTP_PASSWORD            — Senha de App do Gmail (16 chars, sem espaços)
    SCHEDULER_NOTIFY_EMAILS  — destinatários separados por ; (sem espaços)
"""

from __future__ import annotations

import os
import smtplib
import socket
import getpass
import sqlite3
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ─────────────────────────────────────────────
# Resolução da raiz e carregamento do .env
# ─────────────────────────────────────────────

_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent

import sys
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
load_sofi_env()

_DB_PATH = _ROOT / os.getenv("LOG_DB_PATH", "core/database/sofi.db")


# ─────────────────────────────────────────────
# Helper: log no banco sem depender do decorator
# ─────────────────────────────────────────────

def _log_db(status: str, mensagem: str) -> None:
    try:
        usuario = getpass.getuser()
        with sqlite3.connect(str(_DB_PATH), timeout=10.0) as conn:
            conn.execute(
                "INSERT INTO execution_logs (modulo, status, mensagem, usuario) VALUES (?, ?, ?, ?)",
                ("Notifier", status, mensagem, usuario),
            )
    except Exception:
        pass  # Silencioso — o notifier não pode derrubar o scheduler


# ─────────────────────────────────────────────
# Template HTML do e-mail
# ─────────────────────────────────────────────

def _build_html(resultados: list[dict], data_execucao: str, tem_erro: bool, grupo_nome: str | None = None) -> str:
    """Monta o corpo HTML do e-mail consolidado."""

    # ── Linhas da tabela de resumo ──
    linhas_tabela = ""
    for r in resultados:
        status = r.get("status", "?")
        name   = r.get("name", "Job")
        tent   = r.get("tentativas", "—")
        dur    = r.get("duracao", "—")
        erro   = r.get("mensagem_erro", "")

        if status in ("SUCESSO", "COM FATURAMENTO"):
            icone      = "✅"
            badge_cor  = "#1a7a3f"
            badge_bg   = "#d4edda"
            badge_txt  = "COM FATURAMENTO" if status == "COM FATURAMENTO" else "SUCESSO"
        elif status == "SEM FATURAMENTO":
            icone      = "ℹ️"
            badge_cor  = "#0d47a1"
            badge_bg   = "#e3f2fd"
            badge_txt  = "SEM FATURAMENTO"
        elif status == "DESABILITADO":
            icone      = "⏸️"
            badge_cor  = "#666"
            badge_bg   = "#e9ecef"
            badge_txt  = "DESABILITADO"
        else:
            icone      = "❌"
            badge_cor  = "#8b1a1a"
            badge_bg   = "#f8d7da"
            badge_txt  = status  # "ERRO" ou "FALHA PERMANENTE"

        # Célula extra com trecho do erro (se houver)
        detalhe_html = ""
        if erro and status not in ("SUCESSO", "COM FATURAMENTO", "SEM FATURAMENTO", "DESABILITADO"):
            # Últimas 5 linhas, tratadas como texto simples
            trecho = "\n".join(erro.strip().splitlines()[-5:])
            detalhe_html = f"""
            <tr>
              <td colspan="4" style="padding:4px 16px 12px 40px; font-size:12px;
                  color:#6c2a2a; background:#fff5f5; border-bottom:1px solid #f5c6cb;
                  font-family:monospace; white-space:pre-wrap;">{trecho}</td>
            </tr>"""

        linhas_tabela += f"""
        <tr style="border-bottom:1px solid #e8e8e8;">
          <td style="padding:12px 16px; font-size:18px; text-align:center;">{icone}</td>
          <td style="padding:12px 8px; font-weight:600; color:#1a1a2e; font-size:14px;">{name}</td>
          <td style="padding:12px 16px; text-align:center;">
            <span style="background:{badge_bg}; color:{badge_cor}; padding:3px 10px;
                border-radius:12px; font-size:12px; font-weight:700;">{badge_txt}</span>
          </td>
          <td style="padding:12px 16px; color:#555; font-size:13px; text-align:center;">
            {f'{tent}x | {dur}' if status != 'DESABILITADO' else '—'}
          </td>
        </tr>
        {detalhe_html}"""

    # ── Cabeçalho dinâmico ──
    tem_sem_faturamento = any(r.get("status") == "SEM FATURAMENTO" for r in resultados)
    tem_com_faturamento = any(r.get("status") == "COM FATURAMENTO" for r in resultados)
    eh_grupo_xml = bool((grupo_nome and "xml" in grupo_nome.lower()) or any("xml" in r.get("name", "").lower() for r in resultados))

    if tem_erro:
        header_bg    = "linear-gradient(135deg, #c0392b 0%, #922b21 100%)"
        header_label = f"&#10060; &nbsp;Agendamentos dia {data_execucao.split()[0]} &mdash; Aten&ccedil;&atilde;o, h&aacute; erros!"
    elif eh_grupo_xml and tem_sem_faturamento:
        header_bg    = "linear-gradient(135deg, #1e88e5 0%, #1565c0 100%)"
        header_label = f"&#8505; &nbsp;Agendamentos dia {data_execucao.split()[0]} &mdash; Sem Faturamento"
    elif eh_grupo_xml and tem_com_faturamento:
        header_bg    = "linear-gradient(135deg, #1a7a3f 0%, #145a30 100%)"
        header_label = f"&#9989; &nbsp;Agendamentos dia {data_execucao.split()[0]} &mdash; Com Faturamento"
    else:
        header_bg    = "linear-gradient(135deg, #1a7a3f 0%, #145a30 100%)"
        header_label = f"&#9989; &nbsp;Agendamentos dia {data_execucao.split()[0]} &mdash; Tudo OK!"

    # ── Mensagem contextual (exibida APENAS para grupos de XML) ──
    mensagem_contexto = ""

    if eh_grupo_xml:
        if tem_sem_faturamento and not tem_erro:
            mensagem_contexto = """
        <tr>
          <td style="padding:16px 32px 8px;">
            <div style="background:#e3f2fd; border-left:4px solid #1e88e5; padding:14px 18px; border-radius:6px;">
              <p style="margin:0; color:#0d47a1; font-size:14px; font-weight:600;">
                &#8505; N&atilde;o houve faturamento neste per&iacute;odo
              </p>
              <p style="margin:6px 0 0; color:#1565c0; font-size:13px;">
                A automa&ccedil;&atilde;o foi executada com sucesso, por&eacute;m n&atilde;o foram encontradas novas notas fiscais faturadas no per&iacute;odo verificado.
              </p>
            </div>
          </td>
        </tr>"""
        elif not tem_erro:
            mensagem_contexto = """
        <tr>
          <td style="padding:16px 32px 8px;">
            <div style="background:#d4edda; border-left:4px solid #1a7a3f; padding:14px 18px; border-radius:6px;">
              <p style="margin:0; color:#1a7a3f; font-size:14px; font-weight:600;">
                &#9989; Houve faturamento no per&iacute;odo
              </p>
              <p style="margin:6px 0 0; color:#145a30; font-size:13px;">
                Novas notas fiscais foram detectadas e processadas com sucesso. Os relat&oacute;rios finais foram gerados.
              </p>
            </div>
          </td>
        </tr>"""

    hostname = socket.gethostname()
    usuario  = getpass.getuser()

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f4f6f9; font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9; padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff; border-radius:12px; overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,0.10);">

        <!-- HEADER -->
        <tr>
          <td style="background:{header_bg}; padding:28px 32px;">
            <p style="margin:0; color:#fff; font-size:22px; font-weight:700;">{header_label}</p>
            <p style="margin:6px 0 0; color:rgba(255,255,255,0.80); font-size:13px;">
              Execução: {data_execucao}
            </p>
          </td>
        </tr>

        <!-- MENSAGEM CONTEXTUAL -->
        {mensagem_contexto}

        <!-- TABELA DE JOBS -->
        <tr>
          <td style="padding:24px 0 8px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr style="background:#f0f2f5;">
                <th style="padding:10px 16px; font-size:12px; color:#888;
                    text-align:center; font-weight:600; width:40px;">STATUS</th>
                <th style="padding:10px 8px; font-size:12px; color:#888;
                    text-align:left; font-weight:600;">JOB</th>
                <th style="padding:10px 16px; font-size:12px; color:#888;
                    text-align:center; font-weight:600; width:140px;">RESULTADO</th>
                <th style="padding:10px 16px; font-size:12px; color:#888;
                    text-align:center; font-weight:600; width:120px;">TENTATIVAS / DURAÇÃO</th>
              </tr>
              {linhas_tabela}
            </table>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="padding:20px 32px; border-top:1px solid #eee;">
            <p style="margin:0; font-size:11px; color:#aaa;">
              🖥️ &nbsp;Servidor: <strong>{hostname}</strong> &nbsp;|&nbsp;
              👤 &nbsp;Usuário: <strong>{usuario}</strong> &nbsp;|&nbsp;
              🕐 &nbsp;{data_execucao}
            </p>
            <p style="margin:8px 0 0; font-size:11px; color:#ccc;">
              SOFI — Sistema Operacional Financeiro Integrado · Mensagem automática, não responder.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return html


# ─────────────────────────────────────────────
# Função pública principal
# ─────────────────────────────────────────────

def _resolver_destinatarios(destinatarios_input: list[str] | str | None, grupo_nome: str | None = None) -> list[str]:
    """Resolve lista de e-mails tratando nomes de variáveis de ambiente e separadores ; e ,"""
    if not destinatarios_input:
        if grupo_nome and "xml" in grupo_nome.lower():
            destinatarios_input = "SCHEDULER_NOTIFY_EMAILS_XML"
        elif grupo_nome and ("retaguarda" in grupo_nome.lower() or "dfc" in grupo_nome.lower()):
            destinatarios_input = "SCHEDULER_NOTIFY_EMAILS_RETAGUARDA"
        elif grupo_nome and "extranet" in grupo_nome.lower():
            destinatarios_input = "SCHEDULER_NOTIFY_EMAILS_EXTRANET"
        else:
            destinatarios_input = os.getenv("SCHEDULER_NOTIFY_EMAILS", "")

    entradas = []
    if isinstance(destinatarios_input, str):
        entradas = [destinatarios_input]
    elif isinstance(destinatarios_input, list):
        entradas = destinatarios_input

    resultado = []
    for item in entradas:
        if not item or not isinstance(item, str):
            continue
        item_str = item.strip()
        # Se for nome de variável de ambiente cadastrada no .env
        val_env = os.getenv(item_str)
        if val_env:
            item_str = val_env

        # Quebra por ';' ou ','
        partes = [p.strip() for p in item_str.replace(",", ";").split(";") if p.strip()]
        for p in partes:
            if "@" in p and p not in resultado:
                resultado.append(p)

    return resultado


def send_scheduler_notification(
    resultados: list[dict],
    destinatarios: list[str] | str | None = None,
    grupo_nome: str | None = None
) -> bool:
    """
    Envia um e-mail HTML consolidado com o resumo de todos os jobs.

    Args:
        resultados: lista de dicts com chaves:
            - name          (str)   — nome do job
            - status        (str)   — "SUCESSO" | "COM FATURAMENTO" | "SEM FATURAMENTO" | "ERRO" | "FALHA PERMANENTE" | "DESABILITADO"
            - tentativas    (int)   — número de tentativas realizadas
            - duracao       (str)   — duração formatada, ex: "2m 14s"
            - mensagem_erro (str)   — trecho do erro (vazio se SUCESSO/COM FATURAMENTO/SEM FATURAMENTO/DESABILITADO)
        destinatarios: lista ou string com e-mails ou nome de variável de ambiente (ex: "SCHEDULER_NOTIFY_EMAILS_XML")
        grupo_nome: (opcional) nome do grupo de notificação

    Returns:
        True se o e-mail foi enviado com sucesso, False caso contrário.
    """
    # ── Configuração via .env ──
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port   = int(os.getenv("SMTP_PORT", "587"))
    smtp_user   = os.getenv("SMTP_USER", "")
    smtp_pass   = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_pass:
        _log_db("AVISO", "send_scheduler_notification: SMTP_USER ou SMTP_PASSWORD nao configurados no .env. E-mail nao enviado.")
        print("[Notifier] AVISO: SMTP_USER ou SMTP_PASSWORD nao configurados. Notificacao pulada.")
        return False

    destinatarios_limpos = _resolver_destinatarios(destinatarios, grupo_nome=grupo_nome)
    if not destinatarios_limpos:
        _log_db("AVISO", f"send_scheduler_notification: Nenhum destinatario configurado para grupo '{grupo_nome or 'Geral'}'. E-mail nao enviado.")
        print(f"[Notifier] AVISO: Nenhum destinatario valido encontrado para o grupo '{grupo_nome or 'Geral'}'.")
        return False

    # ── Metadados ──
    data_execucao = datetime.now().strftime("%d/%m/%Y %H:%M")
    tem_erro = any(
        r.get("status") not in ("SUCESSO", "COM FATURAMENTO", "SEM FATURAMENTO", "DESABILITADO")
        for r in resultados
    )

    # ── Assunto — resume os jobs do grupo ──
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    nomes_jobs = ", ".join(r.get("name", "Job") for r in resultados)
    prefixo_grupo = f"[{grupo_nome}] " if grupo_nome else "[SOFI] "

    if tem_erro:
        assunto = f"{prefixo_grupo}{data_hoje} - com ERROS | {nomes_jobs}"
    elif any(r.get("status") == "SEM FATURAMENTO" for r in resultados):
        assunto = f"{prefixo_grupo}{data_hoje} - SEM FATURAMENTO | {nomes_jobs}"
    elif any(r.get("status") == "COM FATURAMENTO" for r in resultados):
        assunto = f"{prefixo_grupo}{data_hoje} - COM FATURAMENTO | {nomes_jobs}"
    else:
        assunto = f"{prefixo_grupo}{data_hoje} - OK | {nomes_jobs}"

    # ── Monta e-mail ──
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"]    = f"SOFI Notifier <{smtp_user}>"
    msg["To"]      = ", ".join(destinatarios_limpos)

    html_body = _build_html(resultados, data_execucao, tem_erro, grupo_nome=grupo_nome)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # ── Envia via SMTP ──
    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, destinatarios_limpos, msg.as_string())

        jobs_resumo = ", ".join(f"{r['name']}={r['status']}" for r in resultados)
        _log_db("SUCESSO", f"E-mail de notificacao do grupo '{grupo_nome or 'Geral'}' enviado para {destinatarios_limpos}. Jobs: {jobs_resumo}")
        print(f"[Notifier] E-mail do grupo '{grupo_nome or 'Geral'}' enviado com SUCESSO para: {', '.join(destinatarios_limpos)}")
        return True

    except Exception as exc:
        _log_db("ERRO", f"Falha ao enviar e-mail de notificacao para grupo '{grupo_nome or 'Geral'}': {exc}")
        print(f"[Notifier] FALHA ao enviar e-mail: {exc}")
        return False

