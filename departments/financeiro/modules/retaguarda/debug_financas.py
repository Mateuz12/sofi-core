"""
DEBUG: Teste isolado da Fase 2 — Upload para o Portal Finanças GB.
Execute com: python debug_financas.py
"""

import os
import time
from pathlib import Path
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv(override=True)

FINANCAS_EMAIL = os.getenv("FINANCAS_EMAIL")
FINANCAS_PASS  = os.getenv("FINANCAS_PASS")
FINANCAS_URL   = os.getenv("FINANCAS_URL", "https://financasgb.grupoboticario.com.br/")

# ---- DIAGNÓSTICO: confirma o que foi carregado ----
print("=" * 50)
print(f"[DEBUG] URL carregada : {FINANCAS_URL}")
print(f"[DEBUG] Email carregado: {FINANCAS_EMAIL}")
senha_preview = (FINANCAS_PASS[:3] + "***") if FINANCAS_PASS else "VAZIO / NÃO CARREGADO"
print(f"[DEBUG] Senha carregada: {senha_preview}")
if not FINANCAS_PASS or FINANCAS_PASS == "SUA_SENHA_AQUI":
    print("\n⚠️  ATENÇÃO: Senha do Finanças GB não preenchida no .env!")
    print("    Edite o arquivo .env e substitua SUA_SENHA_AQUI pela senha real.")
    input("Pressione ENTER para sair...")
    exit(1)
print("=" * 50 + "\n")

# ============================================================
# CONFIGURE AQUI O CAMINHO DO XLSX QUE QUER TESTAR O UPLOAD
# Pode ser qualquer .xlsx existente na sua máquina para testar
# ============================================================
ARQUIVO_TESTE = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI\2026\04 ABRIL\09\05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.1.1 PDV RETAGUARDA GB VENDAS LOJAS.09-04-2026.xlsx"

# Se o arquivo de rede não existir ainda, cria um XLSX fictício local para testar o fluxo
if not Path(ARQUIVO_TESTE).exists():
    import pandas as pd
    ARQUIVO_TESTE = str(Path(__file__).parent / "teste_upload.xlsx")
    pd.DataFrame({"Teste": ["dado1", "dado2"]}).to_excel(ARQUIVO_TESTE, index=False)
    print(f"[DEBUG] Arquivo de rede não encontrado. Usando arquivo fictício: {ARQUIVO_TESTE}")
else:
    print(f"[DEBUG] Usando arquivo real: {ARQUIVO_TESTE}")

# --- Setup do Chrome (visível para debug) ---
chrome_options = Options()
# Modo visível (sem headless) — essencial para depuração
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
wait = WebDriverWait(driver, 30)

try:
    print(f"\n--- DEBUG: Abrindo Finanças GB ---")
    print(f"Email: {FINANCAS_EMAIL}")
    driver.get(FINANCAS_URL)
    time.sleep(3)

    # --- LOGIN ---
    print("Preenchendo login...")
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="email"]'))).send_keys(FINANCAS_EMAIL)
    
    campo_senha = driver.find_element(By.XPATH, '//*[@id="input-button-icon-right"]')
    campo_senha.send_keys(FINANCAS_PASS)
    
    print("Aguardando 10 segundos antes de clicar em Entrar...")
    time.sleep(10)
    
    driver.find_element(By.XPATH, '//*[@id="login-root"]/div/div/div[2]/div/div/form/button').click()
    print("Botão Entrar clicado.")
    time.sleep(4)

    # --- PÁGINA "ACESSO EM ANDAMENTO" (opcional) ---
    try:
        btn_continuar = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="login-root"]/div/div/div[2]/div/div/div/div/div/button[1]'))
        )
        print(">> Detectado 'Acesso em andamento'. Clicando em Continuar...")
        btn_continuar.click()
        time.sleep(3)
    except:
        print(">> Sem página de 'Acesso em andamento'.")

    # --- FECHAR POP-UPS DO DASHBOARD ---
    print("Fechando pop-ups do dashboard...")
    for i in range(6):
        try:
            backdrop = driver.find_element(By.CSS_SELECTOR,
                ".modal-backdrop, .v-overlay__scrim, [class*='overlay'], [class*='backdrop']")
            ActionChains(driver).move_to_element_with_offset(backdrop, 5, 5).click().perform()
            print(f"  Pop-up {i+1} fechado via backdrop.")
            time.sleep(1)
        except:
            # Tenta fechar por ESCAPE  
            try:
                from selenium.webdriver.common.keys import Keys
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                print(f"  Pop-up {i+1} fechado via ESCAPE.")
                time.sleep(1)
            except:
                print(f"  Nenhum pop-up encontrado na tentativa {i+1}.")
                break

    time.sleep(2)

    # --- NAVEGAR PARA UPLOAD DE ARQUIVOS ---
    print("Clicando em 'Upload De Arquivos' no menu...")
    upload_link = wait.until(EC.element_to_be_clickable(
        (By.XPATH, '//*[@id="app"]/div[1]/section/div[1]/div[2]/aside/ul/li/ul/li[12]/a/span')
    ))
    upload_link.click()
    print(">> Clicou em Upload De Arquivos.")
    time.sleep(3)

    # --- FECHAR POP-UPS DA TELA DE UPLOAD via JS ---
    print("Fechando pop-ups da tela de Upload via JavaScript...")
    driver.execute_script("""
        var closeBtns = document.querySelectorAll(
            'button[aria-label="close"], button[aria-label="Close"], .v-btn--icon .v-icon, [class*="close"]'
        );
        closeBtns.forEach(function(btn) { btn.click(); });
        var overlays = document.querySelectorAll('.v-overlay, .modal-backdrop, [class*="overlay__scrim"]');
        overlays.forEach(function(el) { el.remove(); });
    """)
    time.sleep(2)

    # --- UPLOAD DO ARQUIVO ---
    print(f"Selecionando arquivo: {ARQUIVO_TESTE}")
    input_file = wait.until(EC.presence_of_element_located((By.ID, "Anexos")))
    input_file.send_keys(ARQUIVO_TESTE)
    time.sleep(3)

    print("\n✅ DEBUG CONCLUÍDO — Verifique o portal. Pressione ENTER para fechar.")
    input()  # Pausa para inspecionar o portal antes de fechar

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    driver.save_screenshot("debug_financas_erro.png")
    print("Screenshot salva em 'debug_financas_erro.png'")
    input("Pressione ENTER para fechar o navegador...")

finally:
    driver.quit()
    print("Navegador fechado.")
