import os
import sys
import time
import argparse
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import xlwt

# 1. Configurar caminho do projeto e carregar ambiente dual-layer do core
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
from core.database.logger import log_execution
load_sofi_env(department="financeiro")

# Importar o utilitário de importação compartilhado
from departments.financeiro.modules.importar_financas import upload_para_financas

# 2. Configurações Globais
PORTAL_USER = os.getenv("PORTAL_USER")
PORTAL_PASS = os.getenv("PORTAL_PASS")
PORTAL_URL  = os.getenv("PORTAL_URL")

SELECTORS = {
    "login_user": '//*[@id="input-19"]',
    "login_pass": '//*[@id="input-20"]',
    "btn_login": '//*[@id="app"]/div[1]/section[2]/div/form/button',
    
    "menu_financeiro": '//*[@id="sidemenu-item-7"]/div',
    "menu_tesouraria": '//*[@id="sidemenu-item-200"]',
    "menu_exportar_receitas": '//*[@id="sidemenu-item-1627"]',
    
    "campo_loja_expand": '//div[@data-target="#collapseLojaFiltro"]', 
    "btn_add_mais": '//*[@id="jqgh_gridLoja_descricao"]/a', 
    "holding_container": '//*[@id="select2-filtroDaHolding-container"]',
    "holding_option_bh": '//li[contains(@class, "select2-results__option") and (contains(text(), "BH LOjas") or contains(text(), "BH LOJAS"))]',
    "btn_pesquisar_popup": '//*[@id="botaoPesquisarPopup"]',
    "check_todos_popup": '//*[@id="marcaTodosPopupPesquisa"]',
    "btn_confirmar_popup": '//*[@id="botaoConcluirSelecaoPopupPesquisa"]',
    
    "origem_container": '//*[@id="select2-origens-container"]',
    "origem_option_todos": '//li[contains(@class, "select2-results__option") and (text()="Todos" or text()="TODOS")]',
    "data_inicial_id": 'dataInicial', 
    "data_final_id": 'dataFinal',
    "checkbox_pdv": 'exportaRecebimentoPDV',
    "btn_pesquisar_principal": 'botaoPesquisar',
    "btn_exportar_xls": 'exportar'
}

def setup_driver(temp_download_dir):
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # Descomente para rodar em segundo plano
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    prefs = {
        "download.default_directory": str(temp_download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": str(temp_download_dir)
    })
    
    return driver

def wait_for_download(directory, timeout=60):
    seconds = 0
    while seconds < timeout:
        files = list(directory.glob("*.xls"))
        if files:
            return files[0]
        time.sleep(1)
        seconds += 1
    return None

def save_to_excel_97_2003(df, path):
    workbook = xlwt.Workbook(encoding='utf-8')
    sheet = workbook.add_sheet('Planilha1')
    
    # Escrever cabeçalhos
    for j, col in enumerate(df.columns):
        sheet.write(0, j, str(col))
        
    # Escrever dados
    for i, row in enumerate(df.values):
        for j, val in enumerate(row):
            try:
                if pd.api.types.is_number(val) and not pd.isna(val):
                    sheet.write(i + 1, j, float(val))
                else:
                    sheet.write(i + 1, j, str(val))
            except:
                sheet.write(i + 1, j, str(val))
                
    workbook.save(str(path))

@log_execution(modulo="Retaguarda BH")
def main():
    # 3. Parser de data CLI
    parser = argparse.ArgumentParser(description="Automação Relatório Retaguarda - BH")
    parser.add_argument("--data", type=str, help="Data no formato DD/MM/AAAA (padrão: D-1)")
    args = parser.parse_args()
    
    if args.data:
        try:
            data_referencia = datetime.strptime(args.data, "%d/%m/%Y")
            print(f"Data selecionada via argumento CLI: {data_referencia.strftime('%d/%m/%Y')}")
        except ValueError:
            print("ERRO: Formato de data inválido! Use DD/MM/AAAA. Abortando.")
            sys.exit(1)
    else:
        data_referencia = datetime.now() - timedelta(days=1)
        print(f"Usando data padrão D-1 (ontem): {data_referencia.strftime('%d/%m/%Y')}")
        
    dia = data_referencia.strftime("%d")
    mes_num = data_referencia.strftime("%m")
    ano = data_referencia.strftime("%Y")
    
    meses_pt = {
        "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARCO", "04": "ABRIL",
        "05": "MAIO", "06": "JUNHO", "07": "JULHO", "08": "AGOSTO",
        "09": "SETEMBRO", "10": "OUTUBRO", "11": "NOVEMBRO", "12": "DEZEMBRO"
    }
    nome_mes_pasta = f"{mes_num} {meses_pt[mes_num]}"
    
    # Caminhos de rede dinâmicos
    base_path = Path(r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\BH")
    target_folder = base_path / ano / nome_mes_pasta / dia
    temp_download_dir = Path(os.getcwd()) / "temp_downloads"
    temp_download_dir.mkdir(exist_ok=True)
    
    filename_final = f"05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.BH.1.1 PDV RETAGUARDA GB VENDAS LOJAS.{dia}-{mes_num}-{ano}.xls"
    output_path = target_folder / filename_final
    
    print(f"Iniciando Extração da Retaguarda para BH na data {dia}/{mes_num}/{ano}")
    driver = setup_driver(temp_download_dir)
    wait = WebDriverWait(driver, 30)
    
    try:
        # FASE 1: Extração no Portal Retaguarda
        print("Abrindo o portal...")
        driver.get(PORTAL_URL)
        
        try:
            user_field = wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["login_user"])))
            user_field.send_keys(PORTAL_USER)
            driver.find_element(By.XPATH, SELECTORS["login_pass"]).send_keys(PORTAL_PASS)
            print("Credenciais preenchidas. Aguardando 10 segundos antes do clique...")
            time.sleep(10)
            driver.find_element(By.XPATH, SELECTORS["btn_login"]).click()
        except Exception as e:
            print(f"Tela de login não encontrada ou já logado. Prosseguindo... ({e})")
            
        print("Aguardando login completo (menu financeiro)...")
        wait_login = WebDriverWait(driver, 300)
        wait_login.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["menu_financeiro"])))
        print("Login realizado com sucesso!")
        
        print("Navegando nos menus...")
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["menu_financeiro"]))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["menu_tesouraria"]))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["menu_exportar_receitas"]))).click()
        
        time.sleep(3)
        print("Entrando no iframe legadoFrame...")
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "legadoFrame")))
        
        print("Expandindo painel de Loja...")
        campo_loja = wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["campo_loja_expand"])))
        driver.execute_script("arguments[0].scrollIntoView(true);", campo_loja)
        time.sleep(1)
        try:
            campo_loja.click()
        except:
            driver.execute_script("arguments[0].click();", campo_loja)
            
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["btn_add_mais"]))).click()
        
        print("Buscando Holding BH...")
        time.sleep(2)
        holding_box = wait.until(EC.element_to_be_clickable((By.XPATH, '//span[@aria-labelledby="select2-filtroDaHolding-container"]')))
        driver.execute_script("arguments[0].scrollIntoView(true);", holding_box)
        time.sleep(1)
        try:
            holding_box.click()
        except:
            driver.execute_script("arguments[0].click();", holding_box)
            
        time.sleep(1)
        
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["holding_option_bh"]))).click()
        except:
            print("Aviso: Seleção direta de BH falhou. Tentando busca genérica por 'BH'...")
            opcoes_bh = driver.find_elements(By.XPATH, '//li[contains(@class, "select2-results__option") and contains(text(), "BH")]')
            if opcoes_bh:
                opcoes_bh[0].click()
            else:
                raise Exception("Não foi possível encontrar a opção BH LOjas.")
                
        driver.find_element(By.XPATH, SELECTORS["btn_pesquisar_popup"]).click()
        time.sleep(3)
        
        checkbox_todos = wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["check_todos_popup"])))
        if not checkbox_todos.is_selected():
            checkbox_todos.click()
        driver.find_element(By.XPATH, SELECTORS["btn_confirmar_popup"]).click()
        
        print("Aplicando filtros de Origem e Datas...")
        time.sleep(1)
        origem_box = wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["origem_container"])))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", origem_box)
        time.sleep(1)
        try:
            origem_box.click()
        except:
            driver.execute_script("arguments[0].click();", origem_box)
            
        time.sleep(1)
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["origem_option_todos"]))).click()
        time.sleep(1)
        
        print("Marcando checkbox PDV...")
        cb_pdv = driver.find_element(By.ID, SELECTORS["checkbox_pdv"])
        if not cb_pdv.is_selected():
            driver.execute_script("arguments[0].click();", cb_pdv)
        time.sleep(1)
        
        data_str = f"{dia}/{mes_num}/{ano}"
        print(f"Definindo datas via jQuery datepicker: {data_str}")
        driver.execute_script(f"""
            if (typeof $.fn.datepicker !== 'undefined') {{
                $('#dataInicial').datepicker('setDate', '{data_str}');
                $('#dataFinal').datepicker('setDate', '{data_str}');
            }} else {{
                document.getElementById('dataInicial').value = '{data_str}';
                document.getElementById('dataFinal').value = '{data_str}';
            }}
            var evChange = new Event('change', {{ bubbles: true }});
            document.getElementById('dataInicial').dispatchEvent(evChange);
            document.getElementById('dataFinal').dispatchEvent(evChange);
        """)
        time.sleep(2)
        
        val_ini = driver.execute_script("return document.getElementById('dataInicial').value;")
        val_fim = driver.execute_script("return document.getElementById('dataFinal').value;")
        print(f"Datas preenchidas → Inicial: '{val_ini}' | Final: '{val_fim}'")
        
        print("Pesquisando relatório...")
        driver.find_element(By.ID, SELECTORS["btn_pesquisar_principal"]).click()
        print("Aguardando 30 segundos para o processamento do portal...")
        time.sleep(30)
        
        print("Exportando arquivo XLS...")
        wait.until(EC.element_to_be_clickable((By.ID, SELECTORS["btn_exportar_xls"]))).click()
        
        baixado = wait_for_download(temp_download_dir, timeout=120)
        if baixado:
            print(f"Arquivo baixado com sucesso: {baixado.name}")
            df = pd.read_excel(baixado)
            
            target_folder.mkdir(parents=True, exist_ok=True)
            save_to_excel_97_2003(df, output_path)
            print(f"Relatório gravado com sucesso no formato .xls legado em: {output_path}")
            
            # Limpeza do arquivo temporário baixado
            os.remove(baixado)
            
            # Fechando o driver do Selenium antes do Upload
            driver.quit()
            driver = None
            
            # FASE 2: Upload para o Portal Finanças GB chamando o utilitário compartilhado
            print("\n--- FASE 2: Iniciando Importação para o Finanças GB via Playwright ---")
            success = upload_para_financas(arquivos=[output_path], unidade="BH")
            if success:
                print("Processo concluído com SUCESSO!")
            else:
                raise Exception("Erro durante o upload do relatório no Finanças GB.")
        else:
            raise Exception("O arquivo de relatório não apareceu na pasta de downloads temporários.")
            
    except Exception as e:
        print(f"OCORREU UM ERRO DURANTE A AUTOMAÇÃO: {e}")
        if driver:
            try:
                driver.save_screenshot("erro_automacao.png")
                print("Screenshot salva como 'erro_automacao.png'")
            except Exception as se:
                print(f"Não foi possível salvar screenshot: {se}")
            driver.quit()
        raise e

if __name__ == "__main__":
    main()
