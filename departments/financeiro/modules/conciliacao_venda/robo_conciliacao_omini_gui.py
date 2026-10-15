import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
import tkinter.messagebox
import customtkinter as ctk
from PIL import Image
import threading
import sys

# Cores da Empresa (O Boticário / Primárias e Secundárias informadas)
COLOR_PRIMARY = "#002308"
COLOR_PRIMARY_LIGHT = "#45B57B"
COLOR_PRIMARY_LIGHTER = "#7CD884"

COLOR_SECONDARY = "#AF1755"
COLOR_SECONDARY_LIGHT = "#D689B2"
COLOR_TEXT = "#E6E6E1"

def desmarcar_caixa_laranja(driver, caixa_laranja):
    if not caixa_laranja:
        return

    try:
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_laranja)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", caixa_laranja)
        time.sleep(0.5)
        print("    -> Caixa Laranja desmarcada antes de seguir para o proximo pedido.")
    except Exception as e:
        print(f"    [!] Clique para desmarcar a Caixa Laranja falhou: {str(e)[:50]}...")
        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
            print("    -> Tentativa extra de limpar selecao enviada com ESC.")
        except Exception as esc_error:
            print(f"    [!] Nao foi possivel limpar a selecao automaticamente: {str(esc_error)[:50]}...")

# Redirecionador do print() para a caixa de texto da GUI
class TextRedirector:
    def __init__(self, widget):
        self.widget = widget
        
    def write(self, str):
        self.widget.insert("end", str)
        self.widget.see("end")
        
    def flush(self):
        pass

def obter_caminho_relatorio(ui_ask_date_callback, ui_ask_file_callback):
    base_dir = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI"
    
    print("\n[BUSCA DE ARQUIVO]")
    data_input = ui_ask_date_callback()
    
    if data_input:
        try:
            data_alvo = datetime.strptime(data_input, "%d/%m/%Y")
        except Exception as e:
            print("Formato de data inválido. Tentando buscar usando a data de hoje...")
            data_alvo = datetime.now()
    else:
        print("Buscando relatório para a data de HOJE...")
        data_alvo = datetime.now()
        
    ano = data_alvo.strftime("%Y")
    mes_num = data_alvo.strftime("%m")
    dia = data_alvo.strftime("%d")
    
    meses_pt = {
        "01": "01 JANEIRO", "02": "02 FEVEREIRO", "03": "03 MARÇO",
        "04": "04 ABRIL", "05": "05 MAIO", "06": "06 JUNHO",
        "07": "07 JULHO", "08": "08 AGOSTO", "09": "09 SETEMBRO",
        "10": "10 OUTUBRO", "11": "11 NOVEMBRO", "12": "12 DEZEMBRO"
    }
    
    mes_pasta = meses_pt.get(mes_num, "")
    nome_arquivo = f"05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 20844.{data_alvo.strftime('%d-%m-%Y')}.xls"
    
    caminho_automatico = os.path.join(base_dir, ano, mes_pasta, dia, nome_arquivo)
    
    if os.path.exists(caminho_automatico):
        print(f"[+] Sucesso! Relatório encontrado automaticamente:\n    -> {caminho_automatico}\n")
        return caminho_automatico
    else:
        print(f"[-] O relatório não foi encontrado no caminho esperado:\n    -> {caminho_automatico}")
        print("[!] Abrindo janela para você selecionar o arquivo manualmente...")
        
        caminho_manual = ui_ask_file_callback()
        
        if not caminho_manual:
            print("[X] Nenhum arquivo selecionado. Finalizando o robô.")
            return None
            
        print(f"[+] Arquivo selecionado manualmente:\n    -> {caminho_manual}\n")
        return caminho_manual

def run_robot_logic(ui_ask_date_callback, ui_ask_file_callback, ui_messagebox_callback, ui_enable_button_callback):
    try:
        # FASE 1: O CÉREBRO (PANDAS ETL)
        print("1. Lendo o relatório de cartões...")
        caminho_relatorio = obter_caminho_relatorio(ui_ask_date_callback, ui_ask_file_callback)
        
        if not caminho_relatorio:
            ui_enable_button_callback()
            return
            
        df = pd.read_excel(caminho_relatorio, usecols=[
            'NumeroPedido', 'NumeroAutorizacao', 'ValorTitulo', 
            'BandeiraCartao', 'QuantidadeParcelas', 'EntidadeConciliacaoEmissao', 'Titulo', 'PlanoPagamento', 'DataPedido'
        ])

        print("2. Aplicando Filtro de Ruído (Removendo Boletos/Pix)...")
        df_cartoes = df[~df['EntidadeConciliacaoEmissao'].astype(str).str.contains('Boleto|Pix', na=False, case=False)].copy()

        print("3. Preparando dados para fusão (Matemática Pura)...")
        df_cartoes['NumeroAutorizacao'] = df_cartoes['NumeroAutorizacao'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_cartoes['BandeiraCartao'] = df_cartoes['BandeiraCartao'].astype(str).str.strip()
        df_cartoes['Titulo'] = df_cartoes['Titulo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        def converter_para_float(valor):
            if pd.isna(valor): return 0.0
            if isinstance(valor, (int, float)): return float(valor)
            v_str = str(valor).strip().replace('.', '').replace(',', '.')
            try: return float(v_str)
            except ValueError: return 0.0

        df_cartoes['ValorMatematico'] = df_cartoes['ValorTitulo'].apply(converter_para_float)
        df_cartoes['QuantidadeParcelas'] = pd.to_numeric(df_cartoes['QuantidadeParcelas'], errors='coerce').fillna(1)

        print("4. Consolidando Parcelamentos e Filtrando Somente OMINI...")
        df_consolidado = df_cartoes.groupby(
            ['NumeroPedido', 'NumeroAutorizacao', 'BandeiraCartao'], as_index=False
        ).agg({
            'ValorMatematico': 'sum',
            'QuantidadeParcelas': 'max',
            'Titulo': 'first',
            'PlanoPagamento': 'first',
            'DataPedido': 'first'
        })

        def formatar_para_tela(valor):
            try:
                texto = f"R$ {float(valor):,.2f}"
                return texto.replace(',', 'X').replace('.', ',').replace('X', '.')
            except:
                return str(valor)

        df_consolidado['ValorTela'] = df_consolidado['ValorMatematico'].apply(formatar_para_tela)

        is_omini = df_consolidado['PlanoPagamento'].astype(str).str.strip().str.upper() == 'OMNICHANNEL - CONSUMIDOR FINAL'
        pedidos_omini = df_consolidado[is_omini].copy()

        print("5. Montando a Fila de Trabalho OMINI...")
        fila_total_omini = pedidos_omini.groupby('NumeroPedido').apply(
            lambda x: {
                'transacoes': x[['NumeroAutorizacao', 'ValorTela', 'BandeiraCartao', 'QuantidadeParcelas', 'ValorMatematico', 'Titulo']].to_dict('records'),
                'DataPedido': x['DataPedido'].iloc[0]
            }
        ).to_dict()

        fila_de_trabalho_omini = fila_total_omini.copy()
        quantidade_pedidos_omini = len(fila_de_trabalho_omini)

        print(f"\n[SUCESSO] Encontrados {quantidade_pedidos_omini} pedidos OMINI para conciliar.")

        if quantidade_pedidos_omini > 0:
            print("\n6. Iniciando Motor do Selenium...")
            
            driver = webdriver.Chrome()
            driver.maximize_window()
            driver.get("https://financasgb.grupoboticario.com.br/") 
            
            # Substituição do input: a interface vai paralisar a thread com o messagebox
            ui_messagebox_callback("Ação Manual Necessária", "1. Faça o login no navegador.\n2. Carregue a tela com as caixas Laranjas e Azuis.\n\nQuando estiver na tela, clique em OK para o robô continuar.")

            print("\n7. Iniciando Conciliação Visual OMINI...")
            
            pedidos_omini_por_data = {}
            for p, dados in fila_de_trabalho_omini.items():
                data_raw = pd.to_datetime(dados['DataPedido'], dayfirst=True, errors='coerce')
                data_str = data_raw.strftime('%d/%m/%Y') if pd.notna(data_raw) else 'Sem Data'
                data_sort_key = data_raw if pd.notna(data_raw) else pd.Timestamp.max 
                
                if data_str not in pedidos_omini_por_data:
                    pedidos_omini_por_data[data_str] = {'pedidos': {}, 'sort_key': data_sort_key}
                
                if isinstance(pedidos_omini_por_data[data_str], dict) and 'pedidos' in pedidos_omini_por_data[data_str]:
                    pedidos_dict: dict = pedidos_omini_por_data[data_str]['pedidos']
                    pedidos_dict[p] = dados
                    
            datas_ordenadas = sorted(
                list(pedidos_omini_por_data.keys()), 
                key=lambda d: pedidos_omini_por_data[d].get('sort_key', pd.Timestamp.max) if isinstance(pedidos_omini_por_data[d], dict) else pd.Timestamp.max
            )
            
            for data_atual in datas_ordenadas:
                if isinstance(pedidos_omini_por_data[data_atual], dict) and 'pedidos' in pedidos_omini_por_data[data_atual]:
                    pedidos_da_data: dict = pedidos_omini_por_data[data_atual]['pedidos']
                    print("\n==========================================")
                    print(f"[DATA] INICIANDO PAGAMENTOS OMINI DO DIA: {data_atual}")
                    print(f"       Total de pedidos para esta data: {len(pedidos_da_data)}")
                    print("==========================================")
                    
                    ui_messagebox_callback("Checagem de Data", f"Atenção!\n\nVá no Finanças GB e filtre os pagamentos (lado direito) e pedidos (lado esquerdo) para a data {data_atual}.\n\nQuando a tela estiver 100% carregada para esta data, aperte OK aqui na tela preta para continuar...")
                    
                    for pedido, dados_pedido in pedidos_da_data.items():
                        transacoes = dados_pedido['transacoes'] if isinstance(dados_pedido, dict) and 'transacoes' in dados_pedido else dados_pedido
                        try:
                            print(f"\n[+] Iniciando Pedido OMINI: {pedido}")
                            soma_total = sum([t['ValorMatematico'] for t in transacoes])
                            valor_total_str = f"R$ {soma_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            caixa_laranja = None
                            
                            for t in transacoes:
                                titulo_teste = t['Titulo']
                                xpath_laranja = f"//*[contains(., '{valor_total_str}') and contains(., '{titulo_teste}') and contains(., 'PDV') and not(.//*[contains(., '{valor_total_str}') and contains(., '{titulo_teste}') and contains(., 'PDV')])]"
                                try:
                                    elementos = driver.find_elements(By.XPATH, xpath_laranja)
                                    if len(elementos) > 0:
                                        caixa_laranja = elementos[0] 
                                        print(f"    -> Alvo Travado na Esquerda: {valor_total_str} (Documento: {titulo_teste})")
                                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_laranja)
                                        time.sleep(1)
                                        driver.execute_script("arguments[0].click();", caixa_laranja)
                                        print("    -> Caixa Laranja selecionada via JS.")
                                        time.sleep(1)
                                        break 
                                except:
                                    continue
                                
                            # PASSO C: Caçar as Azuis (Direita) - NOVO FORMATO MODAL
                            caixa_azul_para_arrastar = None 
                            for transacao in transacoes:
                                aut_azul = str(transacao['NumeroAutorizacao']).strip()
                                valor_azul = str(transacao['ValorTela']).strip()
                                # Variável alternativa: remove zeros à esquerda para flexibilizar a busca
                                # (ex: "042954" vira "42954") pois o portal pode exibir com ou sem o zero
                                aut_azul_sem_zero = aut_azul.lstrip('0') or '0'
                                
                                try:
                                    # Nova busca: utiliza a modal ID estável + div draggable para garantir seleção correta
                                    # Flex para Código de Autorização: busca TANTO com zeros à esquerda QUANTO sem
                                    xpath_infalivel = f"//*[@id='conciliacaoModal']//div[@class='draggable' and .//td[contains(., '{valor_azul}')] and (.//td[contains(., '{aut_azul}')] or .//td[contains(., '{aut_azul_sem_zero}')])]"
                                    
                                    caixa_azul = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath_infalivel)))
                                    print(f"    -> Alvo Travado na Direita: {valor_azul} (Aut: {aut_azul})")
                                    
                                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_azul)
                                    time.sleep(0.5)
                                    driver.execute_script("arguments[0].click();", caixa_azul)
                                    caixa_azul_para_arrastar = caixa_azul
                                    time.sleep(0.5)
                                except Exception as e:
                                    print(f"    [!] Caixa Azul não encontrada: Valor={valor_azul} Aut={aut_azul}.")
                                    caixa_azul_para_arrastar = None
                                    break
                                    
                            if not caixa_laranja:
                                print(f"    [!] Caixa Laranja não encontrada para o pedido {pedido}. Pulando.")
                                continue 
                                
                            caixa_azul_para_arrastar = None 
                            for transacao in transacoes:
                                aut_azul = str(transacao['NumeroAutorizacao']).strip()
                                valor_azul = str(transacao['ValorTela']).strip()
                                try:
                                    xpath_infalivel = f"//tr[.//td[contains(@data-bind, 'exibirNSU')] and .//td[contains(., '{valor_azul}')] and .//td[contains(., '{aut_azul}')]]"
                                    caixa_azul = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath_infalivel)))
                                    print(f"    -> Alvo Travado na Direita: {valor_azul} (Aut: {aut_azul})")
                                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_azul)
                                    time.sleep(0.5)
                                    driver.execute_script("arguments[0].click();", caixa_azul)
                                    caixa_azul_para_arrastar = caixa_azul
                                    time.sleep(0.5)
                                except Exception as e:
                                    print(f"    [!] Caixa Azul não encontrada: Valor={valor_azul} Aut={aut_azul}.")
                                    caixa_azul_para_arrastar = None
                                    break
                                
                            if caixa_azul_para_arrastar:
                                print(f"    -> Realizando o arraste...")
                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_laranja)
                                time.sleep(1)
                                
                                garra = ActionChains(driver)
                                garra.click_and_hold(caixa_azul_para_arrastar).pause(0.5).move_to_element_with_offset(caixa_laranja, 5, 5).pause(1.5).release().perform()
                                     
                                try:
                                    print("    -> Aguardando modal de justificativa de data (OMINI)...")
                                    textarea = WebDriverWait(driver, 10).until(
                                        EC.element_to_be_clickable((By.XPATH, "//textarea[contains(@placeholder, 'justificativa') or contains(@placeholder, 'Justificativa') or contains(@class, 'justificativa')]"))
                                    )
                                    textarea.send_keys("OMINICHANEL CARTAO")
                                    time.sleep(0.5)
                                    
                                    btn_conciliar = driver.find_element(By.XPATH, "//button[contains(text(), 'Conciliar') or contains(., 'Conciliar')]")
                                    driver.execute_script("arguments[0].click();", btn_conciliar)
                                    print("    -> Justificativa preenchida e confirmada.")
                                except Exception as e:
                                    print("    [!] Modal de justificativa não apareceu ou ocorreu um erro extra.")
                                
                                print("    -> Aguardando Finanças GB processar... (Até 120s)")
                                try:
                                    WebDriverWait(driver, 120).until(EC.staleness_of(caixa_laranja))
                                    time.sleep(1)
                                except:
                                    print("    [!] A caixa Laranja não foi destruída pela tela no prazo máximo ou houve travamento de UI. Seguindo...")
                                    time.sleep(3)
                                    
                                print(f"    [SUCESSO] Pedido OMINI {pedido} finalizado!")
                            else:
                                print(f"    [!] Faltou alguma caixa azul para o pedido {pedido}. Drag & drop cancelado.")
                                desmarcar_caixa_laranja(driver, caixa_laranja)
                        except Exception as e:
                            print(f"    [!] ERRO: {str(e)[:50]}...")
                            continue

            print("\n🚀 FIM DA FILA OMINI!")
            ui_messagebox_callback("Concluído", "Todos os pedidos Omini foram processados com sucesso!")
            driver.quit()
        else:
            print("\nNenhum pedido OMINI encontrado no relatório. Execução terminada.")
            
    except Exception as e:
        print(f"\n[ERRO FATAL] Ocorreu um erro na execução: {e}")
        ui_messagebox_callback("Erro Execução", f"Ocorreu um erro:\n\n{e}")
        
    finally:
        ui_enable_button_callback()


# ==========================================
# INTERFACE GRÁFICA (APP MAIN)
# ==========================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Conciliação Automática - O Boticário")
        self.geometry("800x600")
        self.configure(fg_color=COLOR_PRIMARY)
        
        # Grid settings
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header (Top bar)
        self.header_frame = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY_LIGHT, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        # Logo integration
        try:
            logo_path = os.getenv("SOFI_LOGO_PATH", str(Path(__file__).resolve().parent / "logo.png"))
            logo_img = Image.open(logo_path)
            self.logo_image = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(60, 60))
            self.logo_label = ctk.CTkLabel(self.header_frame, image=self.logo_image, text="")
            self.logo_label.grid(row=0, column=0, padx=20, pady=10)
        except Exception as e:
            self.logo_label = ctk.CTkLabel(self.header_frame, text="LOGOTIPO", text_color=COLOR_TEXT)
            self.logo_label.grid(row=0, column=0, padx=20, pady=10)
            
        self.title_label = ctk.CTkLabel(self.header_frame, text="Automação OMINI", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_PRIMARY)
        self.title_label.grid(row=0, column=1, padx=20, pady=10, sticky="w")
        
        # Console Log Textbox
        self.textbox = ctk.CTkTextbox(self, fg_color="#121212", text_color=COLOR_PRIMARY_LIGHTER, font=("Consolas", 14))
        self.textbox.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")
        
        # Redirect standard output (print) to the custom textbox
        sys.stdout = TextRedirector(self.textbox)
        sys.stderr = TextRedirector(self.textbox)
        
        # Info label
        self.info_label = ctk.CTkLabel(self, text="Selecione INICIAR CONCILIAÇÃO abaixo para começar.", text_color=COLOR_TEXT, font=ctk.CTkFont(size=14))
        self.info_label.grid(row=2, column=0, padx=20, pady=5)
        
        # Footer Frame with Button
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.footer_frame.grid_columnconfigure(0, weight=1)
        
        self.btn_run = ctk.CTkButton(
            self.footer_frame, 
            text="▶ INICIAR CONCILIAÇÃO OMINI", 
            font=ctk.CTkFont(size=18, weight="bold"), 
            fg_color=COLOR_PRIMARY_LIGHTER, 
            hover_color=COLOR_PRIMARY_LIGHT, 
            text_color=COLOR_PRIMARY,
            height=60, 
            command=self.start_robot
        )
        self.btn_run.grid(row=0, column=0, sticky="ew")
        
        print(f"Bem-vindo à automação OMINI. Sistema pronto.\nInterface configurada com cores Primárias e Secundárias selecionadas.")
        print("Clique no botão abaixo para iniciar o processo.")
        
    def ask_date_ui(self):
        # Janela de Prompt elegante via CTkInputDialog
        dialog = ctk.CTkInputDialog(text="Digite a data desejada (ex: 18/03/2026).\nDeixe em branco e clique Ok para buscar o relatório de HOJE:", title="Data do Relatório")
        # CustomTkinter usa cores padrão para os dialogs, mas mantém uma estética moderna
        result = dialog.get_input()
        return result

    def ask_file_ui(self):
        # Mantendo o bom e velho tkinter filedialog para selecionar o arquivo
        return filedialog.askopenfilename(title="Selecione o relatório do Fechamento de Caixa", filetypes=[("Arquivos Excel", "*.xls *.xlsx")])
        
    def show_message_ui(self, title, msg):
        # A simple tkinter messagebox prevents code flowing forward until closed
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        tkinter.messagebox.showinfo(title, msg)
        root.destroy()
        
    def enable_button(self):
        # Reativar botão caso haja falha ou fim do processo
        self.btn_run.configure(state="normal", text="▶ INICIAR CONCILIAÇÃO OMINI", fg_color=COLOR_PRIMARY_LIGHTER, text_color=COLOR_PRIMARY)
        self.info_label.configure(text="Execução finalizada ou interrompida.")
        
    def start_robot(self):
        # Desabilitar UI principal enquanto roda a lógica
        self.btn_run.configure(state="disabled", text="[ Executando... Acompanhe os logs acima ]", fg_color=COLOR_SECONDARY, text_color=COLOR_TEXT)
        self.info_label.configure(text="O robô está rodando. Por favor, acompanhe a caixa preta.")
        self.textbox.delete("0.0", "end")
        
        print(f"Iniciando ciclo: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}...\n")
        
        # Executar a lógica de automação em uma thread separada para não travar a interface
        t = threading.Thread(target=run_robot_logic, args=(self.ask_date_ui, self.ask_file_ui, self.show_message_ui, self.enable_button))
        t.daemon = True
        t.start()

# Forçando o tema escuro como base do CustomTkinter 
ctk.set_appearance_mode("dark")

if __name__ == "__main__":
    app = App()
    
    # Adicionando o icone da janela (usa o mesmo .png ou .ico se houver)
    try:
        app.iconbitmap(default='')  # Optional clearing
    except:
        pass
    
    app.mainloop()
