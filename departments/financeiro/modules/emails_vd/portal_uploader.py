import os
import sys
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Configuração de Logging simples para o uploader
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Carrega o .env global do SOFI
# Carrega o .env global do SOFI + .env.local do departamento
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

class PortalUploader:
    def __init__(self):
        self.url = "https://financasgb.grupoboticario.com.br/"
        self.user = os.getenv("FINANCAS_UDI_USER")
        self.password = os.getenv("FINANCAS_UDI_PASS")
        self.headless = os.getenv("HEADLESS", "True").lower() == "true"
        
    def _close_popups(self, page, use_x=False):
        """Tenta fechar popups clicando fora ou no 'X'."""
        try:
            if use_x:
                # Procura por elementos que pareçam botões de fechar (X)
                # Seletores comuns para 'X' de fechamento
                x_selectors = [
                    "button[aria-label='Close']",
                    "button:has-text('X')",
                    ".close",
                    ".modal-close",
                    "[class*='close']"
                ]
                for selector in x_selectors:
                    close_buttons = page.query_selector_all(selector)
                    for btn in close_buttons:
                        if btn.is_visible():
                            logger.info(f"Clicando no 'X' de fechamento: {selector}")
                            btn.click()
            else:
                # Clica em um ponto neutro da tela (ex: canto superior esquerdo ou no body)
                logger.info("Tentando fechar popup clicando fora.")
                page.mouse.click(10, 10)
        except Exception as e:
            logger.warning(f"Erro ao tentar fechar popups: {e}")

    def upload_files(self, file_paths):
        """Executa o processo de login e upload."""
        if not self.user or not self.password:
            logger.error("Credenciais não encontradas no arquivo .env")
            return False

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # 1. Navegar e Login
                logger.info(f"Acessando {self.url}")
                page.goto(self.url)
                
                # Preencher login usando XPaths fornecidos
                logger.info("Tentando preencher credenciais...")
                page.locator('xpath=//*[@id="email"]').fill(self.user)
                page.locator('xpath=//*[@id="input-button-icon-right"]').fill(self.password)
                page.get_by_role("button", name="Entrar").click()
                
                # 2. Tratar "Acesso em andamento" (XPath fornecido)
                try:
                    xpath_continuar = 'xpath=//*[@id="login-root"]/div/div/div[2]/div/div/div/div/div/button[1]'
                    # Espera o botão aparecer por até 10 segundos
                    page.wait_for_selector(xpath_continuar, timeout=10000)
                    logger.info("Aviso de acesso em andamento detectado. Clicando em Continuar.")
                    page.locator(xpath_continuar).click()
                    time.sleep(3) # Espera carregar o dashboard sem travar no networkidle
                except:
                    logger.info("Tela de 'Acesso em andamento' não apareceu ou timeout.")
                
                # 3. Fechar popups iniciais (clicando fora)
                # Ao invés de networkidle (que pode travar se a página continuar carregando requisições em background),
                # esperamos um elemento chave ficar visível (Dashboard) ou apenas deixamos um tempo fixo
                time.sleep(3) # Espera o dashboard e popups aparecerem
                self._close_popups(page, use_x=False)
                
                # Opcionalmente, pode ser que o próprio clique do passo 3 acidentalmente abra algo ou tire o foco.
                # Garantir tempo para fechamento.
                time.sleep(1)
                
                # Navegar para Upload de Arquivos na barra lateral (XPath fornecido)
                logger.info("Navegando para Upload de Arquivos.")
                xpath_menu_upload = 'xpath=//*[@id="mfe-sidebar-react"]/div/nav/div[2]/div[12]/a'
                
                # Se o menu lateral precisa ser expandido, este .click() com action_timeout evita travamento
                menu_btn = page.locator(xpath_menu_upload)
                menu_btn.wait_for(state="visible", timeout=15000)
                menu_btn.click(force=True)
                
                # 5. Tratar popups pós-clique em Upload (clicando no X)
                time.sleep(2) # Pequena espera para os popups carregarem
                self._close_popups(page, use_x=True)
                
                # 6. Upload dos arquivos
                # Localizar o botão "Selecione" (XPath fornecido)
                logger.info(f"Realizando upload de {len(file_paths)} arquivos.")
                
                try:
                    # O "Selecione" é um div/botão. Usaremos expect_file_chooser se o set_input_files direto falhar
                    # Mas primeiro tentamos localizar o input de arquivo na página (usamos .first para evitar StrictMode violation)
                    file_input = page.locator("input[type='file']").first
                    if file_input.count() > 0:
                        file_input.set_input_files(file_paths)
                    else:
                        # Se não houver input pronto, clicamos no Selecione e aguardamos o seletor
                        with page.expect_file_chooser() as fc_info:
                            page.locator('xpath=//*[@id="tabstrip-1"]/div[1]/div/form/div/div/div/div/div[1]').click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(file_paths)
                except Exception as e:
                    logger.warning(f"Falha ao realizar upload via seletor: {e}")
                    # Última tentativa genérica usando o ID do input de Lojas
                    page.locator("#arquivosLojas").set_input_files(file_paths)

                # 7. Finalização
                logger.info("Upload concluído com sucesso!")
                time.sleep(5) # Espera garantia antes de fechar
                return True

            except PlaywrightTimeout:
                logger.error("Tempo limite (Timeout) excedido durante a automação.")
                self._take_error_screenshot(page)
                return False
            except Exception as e:
                logger.error(f"Erro inesperado no portal: {e}")
                self._take_error_screenshot(page)
                return False
            finally:
                browser.close()

    def _take_error_screenshot(self, page):
        """Captura um print em caso de erro para debug."""
        try:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"erro_upload_{timestamp}.png"
            filepath = os.path.join(os.getcwd(), filename)
            page.screenshot(path=filepath, full_page=True)
            logger.info(f"Screenshot de erro salvo em: {filepath}")
        except Exception as e:
            logger.error(f"Falha ao capturar screenshot: {e}")

if __name__ == "__main__":
    # Teste isolado (pode ser rodado via comando para verificar os seletores)
    uploader = PortalUploader()
    # Exemplo: uploader.upload_files(["caminho/arquivo1.xls", "caminho/arquivo2.xls"])
    print("Módulo PortalUploader carregado.")
