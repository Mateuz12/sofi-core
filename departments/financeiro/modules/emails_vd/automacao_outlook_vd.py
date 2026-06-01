import win32com.client
import os
import re
import tempfile
from datetime import datetime

# Configurações de Pastas e Caminhos
BASE_PATH = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI\2026"
SENDER_EMAIL = "assistentevd@udiboticario.com.br"
ARCHIVE_FOLDER_NAME = "Arquivados"
START_DATE_STR = "14/04/2026 00:00" # Filtra emails recebidos a partir desta data

# Mapeamento de Meses para as Pastas
MESES_PT = {
    1: "01 JANEIRO", 2: "02 FEVEREIRO", 3: "03 MARÇO", 4: "04 ABRIL",
    5: "05 MAIO", 6: "06 JUNHO", 7: "07 JULHO", 8: "08 AGOSTO",
    9: "09 SETEMBRO", 10: "10 OUTUBRO", 11: "11 NOVEMBRO", 12: "12 DEZEMBRO"
}

# Configuração das Unidades
UNIDADES = {
    "UDI": {
        "subject_keyword": "UDI",
        "attachment_prefix": "Controle de Título UDI",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 20844"
    },
    "ARI": {
        "subject_keyword": "ARI",
        "attachment_prefix": "Controle de Título ARI",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 23275"
    },
    "Jardim Patrícia": {
        "subject_keyword": "Jardim Patrícia",
        "attachment_prefix": "Controle de Título JP",
        "final_name_prefix": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 24417"
    }
}

def get_outlook_folder(namespace, folder_name):
    """Obtém ou cria uma pasta no Outlook."""
    inbox = namespace.GetDefaultFolder(6)
    try:
        return inbox.Folders[folder_name]
    except:
        return inbox.Folders.Add(folder_name)

def convert_to_xls(temp_path, final_path):
    """Converte um arquivo Excel para o formato 97-2003 (.xls) via COM."""
    excel = win32com.client.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    
    try:
        wb = excel.Workbooks.Open(temp_path)
        # 56 = xlExcel8 (Excel 97-2003 Workbook)
        wb.SaveAs(final_path, FileFormat=56)
        wb.Close(SaveChanges=False)
        return True
    except Exception as e:
        print(f"Erro na conversão Excel: {e}")
        return False
    finally:
        excel.Quit()

def process_emails():
    # Conexão com Outlook
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    inbox = outlook.GetDefaultFolder(6)
    archive_folder = get_outlook_folder(outlook, ARCHIVE_FOLDER_NAME)
    
    # Filtro de emails do remetente e data de recebimento
    # Formatando a data para o padrão do Outlook (MM/DD/YYYY HH:MM AM/PM)
    start_dt = datetime.strptime(START_DATE_STR, "%d/%m/%Y %H:%M")
    outlook_date_filter = start_dt.strftime("%m/%d/%Y %I:%M %p")
    
    filter_string = f"[SenderEmailAddress] = '{SENDER_EMAIL}' AND [ReceivedTime] >= '{outlook_date_filter}'"
    messages = inbox.Items.Restrict(filter_string)
    
    # Lista para armazenar emails a serem movidos (após processar)
    emails_to_move = []

    print(f"Encontrados {len(messages)} emails de {SENDER_EMAIL} na Caixa de Entrada.")

    for message in list(messages):
        subject = message.Subject
        print(f"\nProcessando Email: {subject}")
        
        # Identificar Unidade e Data
        matched_unidade = None
        extracted_date = None
        
        # Regex para extrair data DD-MM-AAAA ou DD-MM-AA
        date_match = re.search(r"(\d{2}-\d{2}-\d{2,4})", subject)
        if not date_match:
            print("Não foi possível encontrar a data no assunto.")
            continue
        
        extracted_date = date_match.group(1)
        
        # Gera variações de data: com ano 2 dígitos e 4 dígitos
        date_parts = extracted_date.split("-")
        if len(date_parts[2]) == 4:
            date_2dig = f"{date_parts[0]}-{date_parts[1]}-{date_parts[2][2:]}"
            date_4dig = extracted_date
        else:
            date_2dig = extracted_date
            date_4dig = f"{date_parts[0]}-{date_parts[1]}-20{date_parts[2]}"
        
        extracted_date_full = date_4dig  # Para uso no caminho de pasta e nome final
        
        for key, data in UNIDADES.items():
            if data["subject_keyword"] in subject:
                matched_unidade = data
                break
        
        if not matched_unidade:
            print("Unidade não identificada no assunto.")
            continue

        # Procurar Anexo específico
        attachment_processed = False
        print(f"Total de anexos no email: {message.Attachments.Count}")
        for attachment in message.Attachments:
            print(f"  Anexo encontrado: {attachment.FileName}")
            # Verifica se o anexo contém o prefixo da unidade e a data (em qualquer formato)
            nome = attachment.FileName
            prefixo_ok = matched_unidade["attachment_prefix"] in nome
            data_ok = date_2dig in nome or date_4dig in nome
            if prefixo_ok and data_ok:
                print(f"Anexo encontrado: {attachment.FileName}")
                
                # Definir caminhos
                date_dt = datetime.strptime(extracted_date_full, "%d-%m-%Y")
                mes_folder = MESES_PT[date_dt.month]
                dia_folder = f"{date_dt.day:02d}"
                
                final_dir = os.path.join(BASE_PATH, mes_folder, dia_folder)
                if not os.path.exists(final_dir):
                    os.makedirs(final_dir)
                    print(f"Diretório criado: {final_dir}")
                
                final_filename = f"{matched_unidade['final_name_prefix']}.{extracted_date_full}.xls"
                final_path = os.path.join(final_dir, final_filename)
                
                # Salvar temporariamente
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    temp_save_path = tmp.name
                
                attachment.SaveAsFile(temp_save_path)
                
                # Converter para XLS
                if convert_to_xls(temp_save_path, final_path):
                    print(f"Arquivo salvo com sucesso: {final_path}")
                    attachment_processed = True
                
                # Limpar temp
                if os.path.exists(temp_save_path):
                    os.remove(temp_save_path)
                
                break # Processa apenas o primeiro anexo que der match
        
        if attachment_processed:
            emails_to_move.append(message)
        else:
            print("Nenhum anexo correspondente foi processado para este email.")

    # Mover emails após o processamento
    for msg in emails_to_move:
        try:
            msg.Move(archive_folder)
            print(f"Email movido para '{ARCHIVE_FOLDER_NAME}': {msg.Subject}")
        except Exception as e:
            print(f"Erro ao mover email: {e}")

if __name__ == "__main__":
    process_emails()
