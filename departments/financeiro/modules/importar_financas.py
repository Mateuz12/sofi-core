"""
importar_financas.py — Utilitário compartilhado de importação para o portal FinançasGB.

Chamado ao final da execução dos módulos Retaguarda e Extranet para fazer
o upload automático dos relatórios gerados no portal FinançasGB.

Uso como função (recomendado — chamado pelo próprio script do módulo):
    from departments.financeiro.modules.importar_financas import upload_para_financas
    upload_para_financas(arquivos=[Path("/caminho/relatorio.xls")], unidade="UDI")

Uso como script standalone (fallback interativo):
    python importar_financas.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Carrega o .env global do SOFI + .env.local do departamento
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sofi_env import load_sofi_env

load_sofi_env(department="financeiro")


# ─────────────────────────────────────────────
# Credenciais por unidade (lidas do .env global)
# ─────────────────────────────────────────────

FINANCAS_URL = os.getenv("FINANCAS_URL", "https://financasgb.grupoboticario.com.br/")

CREDENCIAIS = {
    "BH": {
        "email": os.getenv("FINANCAS_BH_USER"),
        "senha": os.getenv("FINANCAS_BH_PASS"),
    },
    "UDI": {
        "email": os.getenv("FINANCAS_UDI_USER"),
        "senha": os.getenv("FINANCAS_UDI_PASS"),
    },
}


# ─────────────────────────────────────────────
# Driver Selenium
# ─────────────────────────────────────────────

def _setup_driver() -> webdriver.Chrome:
    """Inicializa o Chrome com opções padrão."""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


# ─────────────────────────────────────────────
# Login e Navegação
# ─────────────────────────────────────────────

def _fazer_login(driver: webdriver.Chrome, email: str, senha: str) -> None:
    """Faz login no portal FinançasGB."""
    wait = WebDriverWait(driver, 30)

    print(f"  Fazendo login no FinançasGB com: {email}")
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="email"]'))).send_keys(email)
    driver.find_element(By.XPATH, '//*[@id="input-button-icon-right"]').send_keys(senha)

    print("  Aguardando 10 segundos antes de clicar em Entrar...")
    time.sleep(10)
    driver.find_element(By.XPATH, '//*[@id="login-root"]/div/div/div[2]/div/div/form/button').click()
    print("  Botão Entrar clicado.")
    time.sleep(4)

    # Tela "Acesso em andamento" — continua se aparecer
    try:
        btn_continuar = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="login-root"]/div/div/div[2]/div/div/div/div/div/button[1]')
            )
        )
        print("  >> Detectado 'Acesso em andamento'. Clicando em Continuar...")
        btn_continuar.click()
        time.sleep(3)
    except Exception:
        print("  >> Sem página de 'Acesso em andamento'. Continuando...")

    # Fecha pop-ups do dashboard
    print("  Fechando pop-ups do dashboard...")
    for i in range(6):
        try:
            backdrop = driver.find_element(
                By.CSS_SELECTOR,
                ".modal-backdrop, .v-overlay__scrim, [class*='overlay'], [class*='backdrop']",
            )
            ActionChains(driver).move_to_element_with_offset(backdrop, 5, 5).click().perform()
            print(f"    Pop-up {i + 1} fechado via backdrop.")
            time.sleep(1)
        except Exception:
            try:
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                print(f"    Pop-up {i + 1} fechado via ESCAPE.")
                time.sleep(1)
            except Exception:
                print(f"    Nenhum pop-up encontrado na tentativa {i + 1}.")
                break


def _navegar_para_upload(driver: webdriver.Chrome) -> None:
    """Navega até a tela de Upload de Arquivos e fecha pop-ups."""
    wait = WebDriverWait(driver, 30)
    time.sleep(2)

    print("  Clicando em 'Upload De Arquivos' no menu...")
    wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, '//*[@id="mfe-sidebar-react"]/div/nav/div[2]/div[12]/a')
        )
    ).click()
    print("  >> Clicou em Upload De Arquivos.")
    time.sleep(3)

    # Fecha pop-ups da tela de upload via JavaScript
    print("  Fechando pop-ups da tela de Upload via JavaScript...")
    driver.execute_script(
        """
        var closeBtns = document.querySelectorAll(
            'button[aria-label="close"], button[aria-label="Close"],
             .v-btn--icon .v-icon, [class*="close"]'
        );
        closeBtns.forEach(function(btn) { btn.click(); });
        var overlays = document.querySelectorAll(
            '.v-overlay, .modal-backdrop, [class*="overlay__scrim"]'
        );
        overlays.forEach(function(el) { el.remove(); });
    """
    )
    time.sleep(2)


def _fazer_upload_arquivo(driver: webdriver.Chrome, caminho_arquivo: str) -> None:
    """Envia um arquivo para o input de upload da página."""
    wait = WebDriverWait(driver, 30)
    print(f"  Selecionando arquivo para upload: {caminho_arquivo}")
    input_file = wait.until(EC.presence_of_element_located((By.ID, "Anexos")))
    input_file.send_keys(caminho_arquivo)
    time.sleep(3)
    print(f"  >> Upload do arquivo '{Path(caminho_arquivo).name}' concluído.")


# ─────────────────────────────────────────────
# Função pública principal
# ─────────────────────────────────────────────

def upload_para_financas(arquivos: list[Path], unidade: str) -> None:
    """Importa relatórios para o portal FinançasGB.

    Abre o portal, faz login com as credenciais da unidade indicada e
    realiza o upload de cada arquivo da lista. Deve ser chamada ao final
    do main() dos módulos Retaguarda e Extranet.

    Args:
        arquivos: Lista de Path dos relatórios a importar.
                  Arquivos inexistentes são ignorados com aviso.
        unidade:  'BH' ou 'UDI' — define qual login usar no portal.
    """
    unidade = unidade.upper()
    if unidade not in CREDENCIAIS:
        raise ValueError(f"Unidade inválida: '{unidade}'. Use 'BH' ou 'UDI'.")

    credenciais = CREDENCIAIS[unidade]
    email = credenciais["email"]
    senha = credenciais["senha"]

    if not email or not senha:
        raise RuntimeError(
            f"Credenciais do FinançasGB para a unidade '{unidade}' não encontradas no .env. "
            f"Verifique FINANCAS_{unidade}_USER e FINANCAS_{unidade}_PASS."
        )

    # Filtra apenas arquivos que existem
    arquivos_validos = [f for f in arquivos if f.exists()]
    arquivos_invalidos = [f for f in arquivos if not f.exists()]

    for arq in arquivos_invalidos:
        print(f"  [AVISO] Arquivo não encontrado, ignorando: {arq}")

    if not arquivos_validos:
        print("  [AVISO] Nenhum arquivo válido para importar. Encerrando upload.")
        return

    print(f"\n--- IMPORTAÇÃO FINANÇAS GB ({unidade}) ---")
    print(f"  Arquivos a importar: {len(arquivos_validos)}")
    for f in arquivos_validos:
        print(f"    - {f.name}")

    driver = _setup_driver()
    try:
        driver.get(FINANCAS_URL)
        time.sleep(3)

        _fazer_login(driver, email, senha)
        _navegar_para_upload(driver)

        for arquivo in arquivos_validos:
            print(f"\n  Iniciando upload: {arquivo.name}")
            _fazer_upload_arquivo(driver, str(arquivo))

        print("\n--- IMPORTAÇÃO CONCLUÍDA COM SUCESSO! ---")

    except Exception as e:
        print(f"\n  ERRO DURANTE A IMPORTAÇÃO: {e}")
        try:
            screenshot_path = Path(__file__).parent / "erro_importacao.png"
            driver.save_screenshot(str(screenshot_path))
            print(f"  Screenshot salva em: {screenshot_path}")
        except Exception:
            pass
        raise
    finally:
        driver.quit()
        print("  Navegador fechado.\n")


# ─────────────────────────────────────────────
# Modo standalone (fallback interativo)
# ─────────────────────────────────────────────

def _modo_standalone() -> None:
    """Execução interativa via terminal quando chamado diretamente."""
    from datetime import datetime, timedelta

    print("=" * 55)
    print("  IMPORTAR FINANÇAS GB — Modo Interativo")
    print("=" * 55)

    # Selecionar unidade
    while True:
        unidade = input("\nUnidade [BH/UDI]: ").strip().upper()
        if unidade in ("BH", "UDI"):
            break
        print("  Opção inválida. Digite BH ou UDI.")

    # Selecionar data
    d_minus_1 = datetime.now() - timedelta(days=1)
    data_str = input(
        f"\nData dos relatórios (DD/MM/AAAA) ou ENTER para D-1 [{d_minus_1.strftime('%d/%m/%Y')}]: "
    ).strip()

    if data_str:
        try:
            data_ref = datetime.strptime(data_str, "%d/%m/%Y")
        except ValueError:
            print("  Formato inválido. Usando D-1.")
            data_ref = d_minus_1
    else:
        data_ref = d_minus_1

    dia = data_ref.strftime("%d")
    mes_num = data_ref.strftime("%m")
    ano = data_ref.strftime("%Y")
    meses_pt = {
        "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARCO", "04": "ABRIL",
        "05": "MAIO", "06": "JUNHO", "07": "JULHO", "08": "AGOSTO",
        "09": "SETEMBRO", "10": "OUTUBRO", "11": "NOVEMBRO", "12": "DEZEMBRO",
    }
    nome_mes = f"{mes_num} {meses_pt[mes_num]}"

    # Monta o caminho de rede
    base_path = Path(
        rf"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\{unidade}"
    )
    pasta_data = base_path / ano / nome_mes / dia

    print(f"\n  Buscando arquivos em: {pasta_data}")

    if not pasta_data.exists():
        print(f"  [ERRO] Pasta não encontrada: {pasta_data}")
        return

    # Lista arquivos .xls e .csv (excluindo "Pagamento a Maior")
    arquivos = [
        f for f in pasta_data.iterdir()
        if f.suffix.lower() in (".xls", ".csv")
        and "pagamento a maior" not in f.name.lower()
        and "boletos pagos a maior" not in f.name.lower()
    ]

    if not arquivos:
        print("  [AVISO] Nenhum arquivo encontrado para importar.")
        return

    print(f"\n  Arquivos encontrados para upload ({len(arquivos)}):")
    for f in arquivos:
        print(f"    - {f.name}")

    confirma = input("\nConfirmar importação? [S/N]: ").strip().upper()
    if confirma != "S":
        print("  Operação cancelada.")
        return

    upload_para_financas(arquivos=arquivos, unidade=unidade)


if __name__ == "__main__":
    _modo_standalone()
