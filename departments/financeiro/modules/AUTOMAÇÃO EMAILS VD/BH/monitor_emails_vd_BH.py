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
import pywintypes
import os
import re
import sys
import tempfile
import shutil
import logging
import unicodedata
from datetime import datetime
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
BASE_PATH = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\BH\2026"
# Remetentes aceitos (cada unidade pode enviar de um email diferente)
SENDER_EMAILS = [
    "faturamento.vd@attboticario.com.br",    # VD Itapoã
    "lojavd@attboticario.com.br",             # Venda Nova
    "caixaerneves@attboticario.com.br",         # ER Neves
    "financeiro@attboticario.com.br",         # Genérico (qualquer unidade)
    "fechamentodecaixa@attboticario.com.br",  # Genérico (qualquer unidade)
    "viviane.reis@attboticario.com.br",
    "lojavd1@attboticario.com.br",
    "estoque.erneves@attboticario.com.br"       # Venda Nova
]
ARCHIVE_FOLDER_NAME = "Arquivados BH"
START_DATE_SCAN = "21/07/2026" # Somente processa emails recebidos a partir desta data

MESES_PT = {
    1: "01 JANEIRO", 2: "02 FEVEREIRO", 3: "03 MARÇO", 4: "04 ABRIL",
    5: "05 MAIO", 6: "06 JUNHO", 7: "07 JULHO", 8: "08 AGOSTO",
    9: "09 SETEMBRO", 10: "10 OUTUBRO", 11: "11 NOVEMBRO", 12: "12 DEZEMBRO"
}

UNIDADES = {
    "ITAPÕA": {
        "subject_keyword": ["ITAPÕA", "ITAPOÃ", "13793"],  # Variações de acentuação e código da loja
        "attachment_prefix": [
            "Controle de titulos VD Itapoã 13793",
            "Controle de títulos VD Itapoã",
            "Controle de titulos VD Itapõa 13793",
            "Controle de títulos VD Itapõa",
            "Controle de  títulos VD Itapoã",
            "Controle de  titulos VD Itapoã",
            "Controle de titulo VD Itapoã 13793",
            "Controle de título VD Itapoã",
            "Controle de titulo VD Itapõa 13793",
            "Controle de título VD Itapõa",
            "Controle de  título VD Itapoã",
            "Controle de  titulo VD Itapoã",
        ],  # Puxa tanto Titulo quanto Titulos, Itapoã e Itapõa
        "unit_id": "ITAPÕA",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.BH. 2.1 FECHAMENTO DE CAIXA VD 13793"
    },
    "VENDA NOVA":{
        "subject_keyword": ["VENDA NOVA"],
        "attachment_prefix": [
            "Controle de titulos Venda Nova 22372",
            "Controle de títulos Venda Nova 22372",
            "F360 - Controle de titulos Venda Nova 22372",
            "F360° Controle de titulos Venda Nova 22372",
            "F360 Controle de titulos Venda Nova 22372",
            "Controle de titulo Venda Nova 22372",
            "Controle de título Venda Nova 22372",
            "F360 - Controle de titulo Venda Nova 22372",
            "F360° Controle de titulo Venda Nova 22372",
            "F360 Controle de titulo Venda Nova 22372",
        ],
        "unit_id": "VENDA NOVA",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.BH. 2.1 FECHAMENTO DE CAIXA VD 22372"
    },
    "ER NEVES": {
        "subject_keyword": ["ER NEVES", "21433"],
        "attachment_prefix": [
            "Contole de Titulo",
            "Controle de Titulo",
            "Controle de Titulos",
            "Controle de Títulos",
            "Controle de titulos ER Neves 21433",
            "Controle de títulos ER Neves 21433",
            "Controle de titulo ER Neves",
            "Controle de título ER Neves"
        ],
        "unit_id": "ER NEVES",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.BH. 2.1 FECHAMENTO DE CAIXA VD 21433"
    }
}

# ─────────────────────────────────────────────
# LOG (salvo em arquivo próprio para BH)
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
        print(msg)
    except Exception:
        pass
    getattr(logging, nivel)(msg)

# ─────────────────────────────────────────────
# FUNÇÕES AUXILIARES
# ─────────────────────────────────────────────
def remove_accents(input_str):
    """Remove acentos de uma string para comparação case/accent-insensitive."""
    nfkd = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def normalizar_texto(input_str):
    """Remove acentos e converte para maiúsculo para comparações flexíveis."""
    if not input_str:
        return ""
    return remove_accents(str(input_str)).upper()

def get_archive_folder(namespace):
    inbox = namespace.GetDefaultFolder(6)
    try:
        return inbox.Folders[ARCHIVE_FOLDER_NAME]
    except:
        return inbox.Folders.Add(ARCHIVE_FOLDER_NAME)

def get_excel_app():
    try:
        return win32com.client.Dispatch("Excel.Application")
    except Exception:
        clsid = pywintypes.IID('{00024500-0000-0000-C000-000000000046}')
        obj = pythoncom.CoCreateInstance(clsid, None, pythoncom.CLSCTX_LOCAL_SERVER, pythoncom.IID_IDispatch)
        return win32com.client.Dispatch(obj)

def convert_to_xls(temp_path, final_path):
    try:
        excel = get_excel_app()
    except Exception as e:
        log(f"Erro ao iniciar Excel: {e}", "error")
        return False
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
        try:
            excel.Quit()
        except Exception:
            pass

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
        if not sender or sender.lower() not in [e.lower() for e in SENDER_EMAILS]:
            return  # Não é de nenhum remetente esperado

        subject = message.Subject
        log(f"📧 Analisando email de {sender}: {subject}")

        # Extrair data do assunto (DD-MM-AA, DD-MM-AAAA, DD/MM/AA ou DD/MM/AAAA)
        # Usa lookbehind negativo para evitar capturar dígitos do código da loja (ex: "21433-05/05")
        date_match = re.search(r"(?<!\d)(\d{2}[-/]\d{2}[-/]\d{2,4})", subject)
        date_from_subject = date_match is not None
        
        if not date_from_subject:
            log("  ℹ️  Data não encontrada no assunto, tentará extrair dos anexos...")

        # Função auxiliar para processar a data extraída
        def parse_date_string(raw_date):
            extracted = raw_date.replace("/", "-")
            parts = extracted.split("-")
            if len(parts[2]) == 4:
                d2 = f"{parts[0]}-{parts[1]}-{parts[2][2:]}"
                d4 = extracted
            else:
                d2 = extracted
                d4 = f"{parts[0]}-{parts[1]}-20{parts[2]}"
            return d2, d4

        if date_from_subject:
            date_2dig, date_4dig = parse_date_string(date_match.group(1))
            extracted_date_full = date_4dig

        # Identificar unidade (case insensitive + sem acentos)
        matched_unidade = None
        subject_norm = normalizar_texto(subject)
        for key, data in UNIDADES.items():
            keywords = data["subject_keyword"]
            if isinstance(keywords, str):
                keywords = [keywords]
            for kw in keywords:
                if normalizar_texto(kw) in subject_norm:
                    matched_unidade = data
                    break
            if matched_unidade:
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
            
            # Normalização robusta para comparação
            nome_clean = normalizar_texto(nome)
            unidade_ref = normalizar_texto(matched_unidade["unit_id"])
            
            prefixos_config = matched_unidade["attachment_prefix"]
            if isinstance(prefixos_config, str):
                prefixos_config = [prefixos_config]
            
            # Verifica se algum prefixo configurado bate com o nome do anexo (case + acento insensitive)
            prefixo_ok = any(normalizar_texto(p) in nome_clean for p in prefixos_config)
            
            if not prefixo_ok:
                continue

            # Se a data não veio do assunto, tenta extrair do nome do anexo
            if not date_from_subject:
                date_match_anexo = re.search(r"(?<!\d)(\d{2}[-/]\d{2}[-/]\d{2,4})", nome)
                if date_match_anexo:
                    date_2dig, date_4dig = parse_date_string(date_match_anexo.group(1))
                    extracted_date_full = date_4dig
                    log(f"  📅 Data extraída do anexo: {extracted_date_full}")
                    data_ok = True
                else:
                    data_ok = False
            else:
                # Normalizar data — testa tanto com "-" quanto com "/"
                date_2dig_slash = date_2dig.replace("-", "/")
                date_4dig_slash = date_4dig.replace("-", "/")
                data_ok = (date_2dig in nome or date_4dig in nome or
                           date_2dig_slash in nome or date_4dig_slash in nome)

            if data_ok:
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

                # Usa a extensão original do anexo para evitar conflito de formato
                original_ext = os.path.splitext(nome)[1]  # .xls, .xlsx, .xlsm, etc.
                with tempfile.NamedTemporaryFile(delete=False, suffix=original_ext) as tmp:
                    temp_save_path = tmp.name

                attachment.SaveAsFile(temp_save_path)

                if original_ext.lower() == ".xls":
                    # Já é .xls, copia direto sem converter
                    shutil.copy2(temp_save_path, final_path)
                    log(f"  💾 Arquivo salvo (sem conversão): {final_path}")
                    attachment_processed = True
                elif convert_to_xls(temp_save_path, final_path):
                    log(f"  💾 Arquivo salvo: {final_path}")
                    attachment_processed = True

                if os.path.exists(temp_save_path):
                    os.remove(temp_save_path)

                break

        if attachment_processed:
            archive_folder = get_archive_folder(namespace)
            message.Move(archive_folder)
            log(f"  📂 Email processado e movido para '{ARCHIVE_FOLDER_NAME}'.")
            
            # Disparo do upload automático individual
            upload_individual(final_path, extracted_date_full, matched_unidade["unit_id"])
        else:
            log("  ❌ Nenhum anexo correspondente encontrado para os critérios.")

    except Exception as e:
        log(f"Erro ao processar email: {e}", "error")

def upload_individual(file_path, date_str, uni_name):
    """Dispara o upload individual do arquivo recebido."""
    try:
        log(f"  🚀 [PORTAL] Relatório de {uni_name} ({date_str}) recebido. Iniciando upload individual...")
        upload_para_financas(
            arquivos=[Path(file_path)],
            unidade="BH",
        )
        log(f"  ✅ [PORTAL] Upload do relatório de {uni_name} ({date_str}) realizado com sucesso!")
    except Exception as e:
        log(f"  ❌ [PORTAL] Falha no upload individual de {uni_name} ({date_str}): {e}", "error")

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
    log(f"   Aguardando emails de: {', '.join(SENDER_EMAILS)}")
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

        log("🎧 Aguardando novos emails em tempo real...")
        # 4. Loop de eventos do Windows
        pythoncom.PumpMessages()

    except KeyboardInterrupt:
        log("🛑 Monitor encerrado pelo usuário.")
    except Exception as e:
        log(f"Erro fatal no monitor: {e}", "error")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    main()
