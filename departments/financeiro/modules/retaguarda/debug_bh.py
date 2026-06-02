import os
import time
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
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

# --- 1. Carregar configurações (Lendo .env da pasta BH) ---
load_dotenv(Path(__file__).parent / "BH" / ".env", override=True)
PORTAL_USER = os.getenv("PORTAL_USER")
PORTAL_PASS = os.getenv("PORTAL_PASS")
PORTAL_URL  = os.getenv("PORTAL_URL")

FINANCAS_EMAIL = os.getenv("FINANCAS_EMAIL")
FINANCAS_PASS  = os.getenv("FINANCAS_PASS")
FINANCAS_URL   = os.getenv("FINANCAS_URL", "https://financasgb.grupoboticario.com.br/")

# --- 2. Configurações de Data (D-1) ---
data_referencia = datetime.now() - timedelta(days=1)
dia = data_referencia.strftime("%d")
mes_num = data_referencia.strftime("%m")
ano = data_referencia.strftime("%Y")

meses_pt = {
    "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARCO", "04": "ABRIL",
    "05": "MAIO", "06": "JUNHO", "07": "JULHO", "08": "AGOSTO",
    "09": "SETEMBRO", "10": "OUTUBRO", "11": "NOVEMBRO", "12": "DEZEMBRO"
}
nome_mes_pasta = f"{mes_num} {meses_pt[mes_num]}"

# --- 3. Caminhos de Rede (BH) ---
base_path = Path(r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\BH")
target_folder = base_path / ano / nome_mes_pasta / dia
temp_download_dir = Path(os.getcwd()) / "temp_downloads_debug"
temp_download_dir.mkdir(exist_ok=True)

filename_final = f"05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.BH.1.1 PDV RETAGUARDA GB VENDAS LOJAS.{dia}-{mes_num}-{ano}.xls"

# --- 4. Seletores (BH LOjas) ---
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
    # !!! MUDANÇA PARA BH (Busca por texto flexível) !!!
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

def setup_driver_debug():
    chrome_options = Options()
    # MODO VISÍVEL PARA DEBUG
    chrome_options.add_argument("--start-maximized")
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

def save_to_excel_97_2003(df, path):
    workbook = xlwt.Workbook(encoding='utf-8')
    sheet = workbook.add_sheet('Planilha1')
    for j, col in enumerate(df.columns):
        sheet.write(0, j, str(col))
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

def upload_financas_gb_debug(driver, caminho_arquivo):
    print("\n--- DEBUG: Fase 2 - Upload ---")
    wait = WebDriverWait(driver, 30)
    
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[-1])
    driver.get(FINANCAS_URL)
    time.sleep(3)
    
    print(f"Login Finanças GB: {FINANCAS_EMAIL}")
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="email"]'))).send_keys(FINANCAS_EMAIL)
    driver.find_element(By.XPATH, '//*[@id="input-button-icon-right"]').send_keys(FINANCAS_PASS)
    
    print("Aguardando 10 segundos antes do login (inspecione se quiser)...")
    time.sleep(10)
    driver.find_element(By.XPATH, '//*[@id="login-root"]/div/div/div[2]/div/div/form/button').click()
    
    time.sleep(5)
    
    # Upload
    print("Navegando para Upload...")
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, '//*[@id="app"]/div[1]/section/div[1]/div[2]/aside/ul/li/ul/li[12]/a/span')
    )).click()
    time.sleep(3)
    
    # Fechar possíveis modais via JS
    driver.execute_script("""
        var closeBtns = document.querySelectorAll('button[aria-label="close"], .v-btn--icon .v-icon');
        closeBtns.forEach(function(btn) { btn.click(); });
    """)
    
    print(f"Enviando arquivo: {caminho_arquivo}")
    input_file = wait.until(EC.presence_of_element_located((By.ID, "Anexos")))
    input_file.send_keys(caminho_arquivo)
    
    print("\n✅ UPLOAD CONCLUÍDO NO DEBUG. Confira o portal.")
    time.sleep(5)

def main():
    print(f"--- DEBUG BH: Iniciando Processo (Data: {dia}/{mes_num}/{ano}) ---")
    driver = setup_driver_debug()
    wait = WebDriverWait(driver, 30)
    
    try:
        # --- EXTRAÇÃO ---
        print("Abrindo o portal Boticário...")
        driver.get(PORTAL_URL)
        
        # Login
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, SELECTORS["login_user"]))).send_keys(PORTAL_USER)
            driver.find_element(By.XPATH, SELECTORS["login_pass"]).send_keys(PORTAL_PASS)
            time.sleep(2)
            driver.find_element(By.XPATH, SELECTORS["btn_login"]).click()
        except:
            print("Login não necessário ou erro ao preencher.")

        print("--- RESOLVA O CAPTCHA SE APARECER ---")
        wait_login = WebDriverWait(driver, 300)
        wait_login.until(EC.presence_of_element_located((By.XPATH, SELECTORS["menu_financeiro"])))
        print("Login OK!")
        
        # Menus
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["menu_financeiro"]))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["menu_tesouraria"]))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["menu_exportar_receitas"]))).click()
        time.sleep(3)
        
        # Iframe
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "legadoFrame")))
        
        # Filtros BH
        print("Configurando filtros para BH LOjas...")
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["campo_loja_expand"]))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["btn_add_mais"]))).click()
        
        time.sleep(2)
        holding_box = wait.until(EC.element_to_be_clickable((By.XPATH, '//span[@aria-labelledby="select2-filtroDaHolding-container"]')))
        holding_box.click()
        time.sleep(1)
        
        # !!! SELEÇÃO BH LOjas (Mais robusta) !!!
        print("Procurando 'BH LOjas' na lista...")
        try:
            # Tenta o XPath flexível primeiro
            opcao = wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["holding_option_bh"])))
            opcao.click()
        except:
            print("Aviso: Seleção direta falhou. Tentando buscar qualquer opção que contenha 'BH'...")
            # Fallback: busca qualquer LI que contenha 'BH' e clica
            opcoes_bh = driver.find_elements(By.XPATH, '//li[contains(@class, "select2-results__option") and contains(text(), "BH")]')
            if opcoes_bh:
                opcoes_bh[0].click()
            else:
                raise Exception("Não foi possível encontrar a opção BH LOjas na lista.")
        
        driver.find_element(By.XPATH, SELECTORS["btn_pesquisar_popup"]).click()
        time.sleep(3)
        
        checkbox_todos = wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS["check_todos_popup"])))
        if not checkbox_todos.is_selected(): checkbox_todos.click()
        driver.find_element(By.XPATH, SELECTORS["btn_confirmar_popup"]).click()
        
        # Datas e etc
        print("Aplicando datas...")
        data_str = f"{dia}/{mes_num}/{ano}"
        driver.execute_script(f"""
            $('#dataInicial').datepicker('setDate', '{data_str}');
            $('#dataFinal').datepicker('setDate', '{data_str}');
            document.getElementById('dataInicial').dispatchEvent(new Event('change', {{ bubbles: true }}));
            document.getElementById('dataFinal').dispatchEvent(new Event('change', {{ bubbles: true }}));
        """)
        
        cb_pdv = driver.find_element(By.ID, SELECTORS["checkbox_pdv"])
        if not cb_pdv.is_selected(): driver.execute_script("arguments[0].click();", cb_pdv)
        
        # Exportar
        driver.find_element(By.ID, SELECTORS["btn_pesquisar_principal"]).click()
        print("Aguardando 30s de processamento...")
        time.sleep(30)
        
        print("Exportando...")
        driver.find_element(By.ID, SELECTORS["btn_exportar_xls"]).click()
        
        # Wait for download
        print("Aguardando download...")
        timeout = 120
        baixado = None
        for _ in range(timeout):
            files = list(temp_download_dir.glob("*.xls"))
            if files:
                baixado = files[0]
                break
            time.sleep(1)
            
        if baixado:
            print(f"Baixado: {baixado.name}")
            df = pd.read_excel(baixado)
            target_folder.mkdir(parents=True, exist_ok=True)
            output_path = target_folder / filename_final
            save_to_excel_97_2003(df, output_path)
            print(f"Salvo em: {output_path}")
            
            # PHASE 2 UPLOAD
            upload_financas_gb_debug(driver, str(output_path))
            
            print("\n✅ PROCESSO DE DEBUG BH FINALIZADO COM SUCESSO!")
        else:
            print("❌ Erro: Arquivo não baixado.")

    except Exception as e:
        print(f"❌ ERRO NO DEBUG: {e}")
        driver.save_screenshot("debug_bh_erro.png")
    
    print("\nFim do script. Pressione ENTER para fechar o navegador.")
    input()
    driver.quit()

if __name__ == "__main__":
    main()
