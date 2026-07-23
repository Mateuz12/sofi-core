"""
Monitor de Emails VD - Segundo Plano
=====================================
Fica escutando o Outlook via eventos COM.
Quando um email do remetente configurado chegar, processa automaticamente.

Para rodar em segundo plano (sem janela):
    pythonw.exe monitor_emails_vd.py
"""

import win32com.client
import pythoncom
import os
import re
import sys
import tempfile
import logging
import threading
import time
from datetime import datetime, date
from pathlib import Path

# ─────────────────────────────────────────────
# Integração com o Core SOFI
# ─────────────────────────────────────────────
_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

from departments.financeiro.modules.importar_financas import upload_para_financas

# ─────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────
BASE_PATH = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI\2026"
SENDER_EMAIL = "assistentevd@udiboticario.com.br"
ARCHIVE_FOLDER_NAME = "Arquivados"
START_DATE_SCAN = "21/07/2026" # Somente processa emails recebidos a partir desta data

# Configurações do Watcher de Pasta
WATCHER_START_DATE = "21/07/2026"  # Só faz upload de dias a partir desta data
WATCHER_INTERVAL = 300  # Intervalo de verificação em segundos (5 minutos)

MESES_PT = {
    1: "01 JANEIRO", 2: "02 FEVEREIRO", 3: "03 MARÇO", 4: "04 ABRIL",
    5: "05 MAIO", 6: "06 JUNHO", 7: "07 JULHO", 8: "08 AGOSTO",
    9: "09 SETEMBRO", 10: "10 OUTUBRO", 11: "11 NOVEMBRO", 12: "12 DEZEMBRO"
}

UNIDADES = {
    "UDI": {
        "subject_keyword": "UDI",
        "attachment_prefix": "Controle de Titulo", # Puxa tanto Titulo quanto Titulos
        "unit_id": "UDI",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 20844"
    },
    "ARI": {
        "subject_keyword": "ARI",
        "attachment_prefix": "Controle de Titulo",
        "unit_id": "ARI",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 23275"
    },
    "Jardim Patrícia": {
        "subject_keyword": "JP",           # Email chega com "JP" no assunto (ex: "Fechamento de Caixa JP - 17-07-2026")
        "attachment_prefix": "Controle de Titulo",  # Cobre "Controle de Titulo", "Controle de Títulos", "Controle de Titulos"
        "unit_id": "JP",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 24417"
    }
}

# ─────────────────────────────────────────────
# LOG (salvo em arquivo, pois roda sem console)
# ─────────────────────────────────────────────
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_vd.log")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    encoding="utf-8"
)

def log(msg, nivel="info"):
    try:
        print(msg)  # visível se rodar com python.exe normal
    except Exception:
        pass
    getattr(logging, nivel)(msg)

# ─────────────────────────────────────────────
# FUNÇÕES AUXILIARES
# ─────────────────────────────────────────────
def get_archive_folder(namespace):
    inbox = namespace.GetDefaultFolder(6)
    try:
        return inbox.Folders[ARCHIVE_FOLDER_NAME]
    except:
        return inbox.Folders.Add(ARCHIVE_FOLDER_NAME)

def convert_to_xls(temp_path, final_path):
    excel = win32com.client.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(temp_path)
        wb.SaveAs(final_path, FileFormat=56)  # 56 = xlExcel8
        wb.Close(SaveChanges=False)
        return True
    except Exception as e:
        log(f"Erro na conversão Excel: {e}", "error")
        return False
    finally:
        excel.Quit()

def get_sender_email(message):
    """Tenta obter o endereço SMTP real do remetente."""
    try:
        if message.SenderEmailType == "SMTP":
            return message.SenderEmailAddress
        # Para contas Exchange, tenta obter via PropertyAccessor
        return message.Sender.PropertyAccessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x39FE001E")
    except:
        return getattr(message, "SenderEmailAddress", "")

def process_message(message, namespace):
    """Processa um único email recebido."""
    try:
        sender = get_sender_email(message)
        if not sender or sender.lower() != SENDER_EMAIL.lower():
            return  # Não é do remetente esperado

        subject = message.Subject
        log(f"📧 Analisando email de {sender}: {subject}")

        # Extrair data do assunto (DD-MM-AA, DD-MM-AAAA, DD/MM/AA ou DD/MM/AAAA)
        date_match = re.search(r"(\d{2}[-/]\d{2}[-/]\d{2,4})", subject)
        if not date_match:
            log("  ⚠️  Data não encontrada no assunto (esperado DD-MM-AAAA ou DD/MM/AAAA).")
            return

        extracted_date = date_match.group(1).replace("/", "-") # Normaliza para hifen
        date_parts = extracted_date.split("-")
        
        if len(date_parts[2]) == 4:
            date_2dig = f"{date_parts[0]}-{date_parts[1]}-{date_parts[2][2:]}"
            date_4dig = extracted_date
        else:
            date_2dig = extracted_date
            date_4dig = f"{date_parts[0]}-{date_parts[1]}-20{date_parts[2]}"

        extracted_date_full = date_4dig

        # Identificar unidade (case insensitive)
        matched_unidade = None
        for key, data in UNIDADES.items():
            if data["subject_keyword"].upper() in subject.upper():
                matched_unidade = data
                break

        if not matched_unidade:
            log(f"  ⚠️  Unidade não identificada no assunto. Palavras-chave esperadas: {list(UNIDADES.keys())}")
            return

        # Procurar e processar anexo
        log(f"  Total de anexos: {message.Attachments.Count}")
        attachment_processed = False

        for attachment in message.Attachments:
            nome = attachment.FileName
            log(f"  Verificando anexo: {nome}")
            
            # Normalizar para comparação sem acentos (básico) e minúsculas
            nome_clean = nome.lower().replace("í", "i").replace("á", "a")
            prefixo_ref = matched_unidade["attachment_prefix"].lower()
            unidade_ref = matched_unidade["unit_id"].lower()
            
            prefixo_ok = prefixo_ref in nome_clean and unidade_ref in nome_clean
            
            # Normalizar data — testa tanto com "-" quanto com "/"
            date_2dig_slash = date_2dig.replace("-", "/")
            date_4dig_slash = date_4dig.replace("-", "/")
            data_ok = (date_2dig in nome or date_4dig in nome or
                       date_2dig_slash in nome or date_4dig_slash in nome)

            if prefixo_ok and data_ok:
                log(f"  ✅ Anexo correspondente encontrado!")

                date_dt = datetime.strptime(extracted_date_full, "%d-%m-%Y")
                mes_folder = MESES_PT[date_dt.month]
                dia_folder = f"{date_dt.day:02d}"

                final_dir = os.path.join(BASE_PATH, mes_folder, dia_folder)
                if not os.path.exists(final_dir):
                    os.makedirs(final_dir)
                    log(f"  📁 Diretório criado: {final_dir}")

                final_filename = f"{matched_unidade['final_name_prefix']}.{extracted_date_full}.xls"
                final_path = os.path.join(final_dir, final_filename)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    temp_save_path = tmp.name

                attachment.SaveAsFile(temp_save_path)

                if convert_to_xls(temp_save_path, final_path):
                    log(f"  💾 Arquivo salvo: {final_path}")
                    attachment_processed = True

                if os.path.exists(temp_save_path):
                    os.remove(temp_save_path)

                break

        if attachment_processed:
            archive_folder = get_archive_folder(namespace)
            message.Move(archive_folder)
            log(f"  📂 Email processado e movido para '{ARCHIVE_FOLDER_NAME}'.")
            
            # Verificação para disparo do upload automático
            check_and_upload(final_dir, extracted_date_full)
        else:
            log("  ❌ Nenhum anexo correspondente encontrado para os critérios.")

    except Exception as e:
        log(f"Erro ao processar email: {e}", "error")

def check_and_upload(final_dir, date_str):
    """Verifica se os 3 arquivos do dia existem e dispara o upload."""
    try:
        # Verificar se já foi feito upload deste dia
        upload_done_path = os.path.join(final_dir, ".upload_done")
        if os.path.exists(upload_done_path):
            log(f"  ⏭️  [PORTAL] Upload de {date_str} já realizado anteriormente. Pulando.")
            return

        expected_paths = []
        missing = []
        for uni_name, data in UNIDADES.items():
            filename = f"{data['final_name_prefix']}.{date_str}.xls"
            path = Path(os.path.join(final_dir, filename))
            if path.exists():
                expected_paths.append(path)
            else:
                missing.append(uni_name)
        
        if not missing:
            log(f"  🚀 [PORTAL] Todos os 3 relatórios de {date_str} encontrados. Iniciando upload...")
            portal_user = os.getenv("PORTAL_USER")
            portal_pass = os.getenv("PORTAL_PASS")
            try:
                upload_para_financas(
                    arquivos=expected_paths,
                    unidade="UDI",
                    email=portal_user,
                    senha=portal_pass,
                )
                log(f"  ✅ [PORTAL] Upload dos relatórios de {date_str} realizado com sucesso!")
                # Marcar dia como concluído
                with open(upload_done_path, "w") as f:
                    f.write(f"Upload realizado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                log(f"  📌 [PORTAL] Dia {date_str} marcado como concluído (.upload_done criado).")
            except Exception as e:
                log(f"  ❌ [PORTAL] Falha no upload automático de {date_str}: {e}", "error")
        else:
            log(f"  ⏳ [PORTAL] Aguardando relatórios de: {', '.join(missing)} para iniciar upload.")
            
    except Exception as e:
        log(f"Erro na verificação de upload: {e}", "error")

def folder_watcher_loop():
    """Monitora a pasta do servidor em busca de dias com os 3 relatórios completos."""
    watcher_start = datetime.strptime(WATCHER_START_DATE, "%d/%m/%Y").date()
    log(f"👁️  [WATCHER] Iniciado. Monitorando pasta a cada {WATCHER_INTERVAL // 60} minutos (dias >= {WATCHER_START_DATE}).")
    
    while True:
        try:
            hoje = date.today()
            mes_folder = MESES_PT.get(hoje.month)
            if not mes_folder:
                log(f"  ⚠️  [WATCHER] Mês {hoje.month} não encontrado em MESES_PT.", "warning")
                time.sleep(WATCHER_INTERVAL)
                continue
            
            pasta_mes = os.path.join(BASE_PATH, mes_folder)
            
            if not os.path.exists(pasta_mes):
                log(f"  ℹ️  [WATCHER] Pasta do mês não existe ainda: {pasta_mes}")
                time.sleep(WATCHER_INTERVAL)
                continue
            
            # Percorrer subpastas (dias) dentro da pasta do mês
            for dia_nome in os.listdir(pasta_mes):
                dia_path = os.path.join(pasta_mes, dia_nome)
                if not os.path.isdir(dia_path):
                    continue
                
                # Tentar interpretar o nome da pasta como dia
                try:
                    dia_num = int(dia_nome)
                except ValueError:
                    continue
                
                # Montar a data deste dia
                try:
                    data_dia = date(hoje.year, hoje.month, dia_num)
                except ValueError:
                    continue
                
                # Filtrar: só processar dias >= WATCHER_START_DATE
                if data_dia < watcher_start:
                    continue
                
                # Verificar se já foi feito upload
                upload_done_path = os.path.join(dia_path, ".upload_done")
                if os.path.exists(upload_done_path):
                    continue
                
                # Montar date_str no formato DD-MM-AAAA
                date_str = data_dia.strftime("%d-%m-%Y")
                
                # Verificar se os 3 arquivos existem
                arquivos_encontrados = []
                faltando = []
                for uni_name, data in UNIDADES.items():
                    filename = f"{data['final_name_prefix']}.{date_str}.xls"
                    path = os.path.join(dia_path, filename)
                    if os.path.exists(path):
                        arquivos_encontrados.append(path)
                    else:
                        faltando.append(uni_name)
                
                if not faltando:
                    log(f"  👁️  [WATCHER] Dia {date_str}: 3 relatórios encontrados! Disparando upload...")
                    check_and_upload(dia_path, date_str)
                    
        except Exception as e:
            log(f"Erro no watcher de pasta: {e}", "error")
        
        time.sleep(WATCHER_INTERVAL)

# ─────────────────────────────────────────────
# HANDLER DE EVENTOS DO OUTLOOK
# ─────────────────────────────────────────────
class OutlookEventHandler:
    """Recebe eventos do Outlook. OnNewMailEx é chamado para cada email novo."""

    def __init__(self):
        self.namespace = None

    def OnNewMailEx(self, entryIDCollection):
        """
        Disparado pelo Outlook quando um novo email chega.
        entryIDCollection é uma string com IDs separados por vírgula.
        """
        ids = entryIDCollection.split(",")
        for entry_id in ids:
            entry_id = entry_id.strip()
            try:
                message = self.namespace.GetItemFromID(entry_id)
                process_message(message, self.namespace)
            except Exception as e:
                log(f"Erro ao obter email pelo ID: {e}", "error")

# ─────────────────────────────────────────────
# VARREDURA E PONTO DE ENTRADA
# ─────────────────────────────────────────────
def scan_inbox(namespace):
    """Verifica emails existentes na Caixa de Entrada a partir da data configurada."""
    log(f"🔍 Iniciando varredura de emails existentes (a partir de {START_DATE_SCAN})...")
    try:
        inbox = namespace.GetDefaultFolder(6)
        start_dt = datetime.strptime(START_DATE_SCAN, "%d/%m/%Y").date()
        
        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)
        
        count = 0
        analisados = 0
        # Percorremos os emails enquanto forem recentes
        for i in range(1, len(messages) + 1):
            if analisados >= 100: # Limite de segurança para não varrer o histórico infinito
                break
                
            try:
                msg = messages.Item(i)
                if msg.Class == 43:
                    analisados += 1
                    # Compara a data de recebimento (timezone aware) com a data inicial
                    received_date = msg.ReceivedTime.date()
                    
                    if received_date >= start_dt:
                        process_message(msg, namespace)
                        count += 1
                    else:
                        # Como está ordenado por data descendente, se chegamos em um mais antigo, podemos parar
                        break
            except Exception as e:
                continue
        log(f"✨ Varredura inicial concluída. {count} e-mails processados.")
    except Exception as e:
        log(f"Erro na varredura inicial: {e}", "error")

def main():
    pythoncom.CoInitialize()

    log("=" * 50)
    log("🚀 Monitor de Emails VD iniciado.")
    log(f"   Aguardando emails de: {SENDER_EMAIL}")
    log(f"   Log salvo em: {LOG_PATH}")
    log("=" * 50)

    try:
        # 1. Dispatch com Eventos
        outlook_app = win32com.client.DispatchWithEvents(
            "Outlook.Application",
            OutlookEventHandler
        )
        
        # 2. Configurar Namespace
        namespace = outlook_app.GetNamespace("MAPI")
        outlook_app.namespace = namespace # Isso injeta o namespace no handler (mesma instância)
        
        # 3. Varredura Inicial (Emails que já estão lá)
        scan_inbox(namespace)

        # 4. Iniciar Watcher de Pasta em thread separada
        watcher_thread = threading.Thread(target=folder_watcher_loop, daemon=True)
        watcher_thread.start()

        log("🎧 Aguardando novos emails em tempo real + monitoramento de pasta...")
        # 5. Loop de eventos do Windows
        pythoncom.PumpMessages()

    except KeyboardInterrupt:
        log("🛑 Monitor encerrado pelo usuário.")
    except Exception as e:
        log(f"Erro fatal no monitor: {e}", "error")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    main()
