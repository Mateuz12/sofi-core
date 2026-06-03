"""
importar_financas.py — Utilitário compartilhado de importação para o portal FinançasGB via Playwright.

Chamado ao final da execução dos módulos Retaguarda e Extranet para fazer
o upload automático dos relatórios gerados no portal FinançasGB.

Uso como função (chamado pelo próprio script do módulo):
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
from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

# Carrega o .env global do SOFI + .env.local do departamento
_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and _ROOT != _ROOT.parent:
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

REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
"""


# ─────────────────────────────────────────────
# Funções Utilitárias do Browser
# ─────────────────────────────────────────────

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "s"}


def optional_env(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def browser_args() -> list[str]:
    args = [
        "--disable-quic",
        "--ignore-certificate-errors",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if env_bool("DISABLE_HTTP2", default=True):
        args.append("--disable-http2")
    return args


# ─────────────────────────────────────────────
# Login e Navegação
# ─────────────────────────────────────────────

def _limpar_popups_e_overlays(page: Page) -> None:
    """Remove overlays, backdrops e widgets externos (como Maze) do DOM via JS."""
    try:
        page.evaluate("""() => {
            // 1. Remove widgets e iframes intrusivos (Maze, Zendesk widget)
            document.querySelectorAll('#maze-contextual-widget-host, #maze-media-host, iframe[id*="maze"], [class*="widget"]').forEach(function(el) {
                el.remove();
            });
            
            // 2. Remove overlays, backdrops e scrims
            document.querySelectorAll('.v-overlay, .modal-backdrop, [class*="overlay"], [class*="scrim"], [class*="backdrop"]').forEach(function(el) {
                el.remove();
            });
            
            // 3. Força o scroll e remove overflow hidden no body/html
            document.documentElement.style.overflow = 'auto';
            document.body.style.overflow = 'auto';
        }""")
        print("  [JS] Overlays, backdrops e widgets de terceiros (como Maze) removidos com sucesso.")
    except Exception as e:
        print(f"  [AVISO] Falha ao executar script JS de limpeza de modais: {e}")


def _tratar_onboarding_modal(page: Page) -> None:
    """Bypassa o modal de onboarding clicando nos botões de avançar e fechar se ele aparecer na tela."""
    try:
        modal_selector = '#dashboard-onboarding-modal'
        # Aguarda de forma inteligente até 8 segundos para o modal renderizar
        page.locator(modal_selector).wait_for(state="visible", timeout=8_000)
        print("  [Onboarding] Modal de Onboarding detectado. Iniciando cliques de bypass...")
        
        btn_avancar_xpath = 'xpath=//*[@id="dashboard-onboarding-modal"]/div[2]/div[2]/button[2]'
        btn_fechar_xpath = 'xpath=//*[@id="dashboard-onboarding-modal"]/div[2]/div[3]/button'
        
        # Clica no botão Avançar duas vezes
        for i in range(2):
            try:
                btn = page.locator(btn_avancar_xpath)
                btn.wait_for(state="visible", timeout=3_000)
                btn.click()
                print(f"    [Onboarding] Botão Avançar clicado ({i+1}/2).")
                page.wait_for_timeout(1500)
            except Exception as e_avancar:
                print(f"    [Onboarding] Erro ao clicar no botão Avançar ({i+1}/2): {e_avancar}")
                break
                
        # Clica no botão Fechar
        try:
            btn_f = page.locator(btn_fechar_xpath)
            btn_f.wait_for(state="visible", timeout=3_000)
            btn_f.click()
            print("    [Onboarding] Botão Fechar clicado. Onboarding concluído.")
            page.wait_for_timeout(2000)
        except Exception as e_fechar:
            print(f"    [Onboarding] Erro ao clicar no botão Fechar: {e_fechar}")
            
    except PlaywrightTimeoutError:
        print("  [Onboarding] Modal de onboarding não apareceu na tela (Timeout). Pulando...")
    except Exception as e:
        print(f"  [Onboarding] Erro ou pulado ao interagir com modal de onboarding: {e}")


def _fazer_login(page: Page, email: str, senha: str) -> None:
    """Faz login no portal FinançasGB."""
    print(f"  Fazendo login no FinançasGB com: {email}")
    page.locator('xpath=//*[@id="email"]').wait_for(state="visible", timeout=30_000)
    page.locator('xpath=//*[@id="email"]').fill(email)
    page.locator('xpath=//*[@id="input-button-icon-right"]').fill(senha)

    print("  Aguardando 10 segundos antes de clicar em Entrar...")
    page.wait_for_timeout(10_000)
    page.locator('xpath=//*[@id="login-root"]/div/div/div[2]/div/div/form/button').click()
    print("  Botão Entrar clicado.")
    page.wait_for_timeout(4000)

    # Tela "Acesso em andamento" — continua se aparecer
    try:
        btn_continuar = page.locator('xpath=//*[@id="login-root"]/div/div/div[2]/div/div/div/div/div/button[1]')
        if btn_continuar.is_visible(timeout=5_000):
            print("  >> Detectado 'Acesso em andamento'. Clicando em Continuar...")
            btn_continuar.click()
            page.wait_for_timeout(3000)
    except Exception:
        print("  >> Sem página de 'Acesso em andamento'. Continuando...")

    # Trata o modal de onboarding do dashboard se ele aparecer
    _tratar_onboarding_modal(page)

    # Fecha outros pop-ups e modais residuais (como widget do Maze)
    print("  Fechando pop-ups do dashboard...")
    _limpar_popups_e_overlays(page)


def _navegar_para_upload(page: Page) -> None:
    """Navega até a tela de Upload de Arquivos."""
    page.wait_for_timeout(2000)
    print("  Clicando em 'Upload De Arquivos' no menu...")
    
    upload_btn = page.locator('xpath=//*[@id="mfe-sidebar-react"]/div/nav/div[2]/div[12]/a')
    upload_btn.wait_for(state="visible", timeout=30_000)
    upload_btn.click()
    print("  >> Clicou em Upload De Arquivos.")
    page.wait_for_timeout(3000)


def _fazer_upload_arquivo(page: Page, caminho_arquivo: str) -> None:
    """Envia um arquivo clicando no botão visual de upload e interceptando o seletor de arquivos."""
    print(f"  Selecionando arquivo para upload: {caminho_arquivo}")
    
    upload_btn_xpath = 'xpath=//*[@id="tabstrip-1"]/div[1]/div/form/div/div/div/div/div[1]'
    page.locator(upload_btn_xpath).wait_for(state="visible", timeout=30_000)
    
    with page.expect_file_chooser() as fc_info:
        page.locator(upload_btn_xpath).click()
        
    file_chooser = fc_info.value
    file_chooser.set_files(caminho_arquivo)
    page.wait_for_timeout(3000)
    print(f"  >> Upload do arquivo '{Path(caminho_arquivo).name}' concluído.")


# ─────────────────────────────────────────────
# Função Pública Principal
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

    headless = env_bool("HEADLESS", default=False)
    browser_channel = optional_env("BROWSER_CHANNEL", "chrome")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless, slow_mo=250, channel=browser_channel, args=browser_args()
        )
        context = browser.new_context(
            accept_downloads=True,
            ignore_https_errors=True,
            user_agent=REALISTIC_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )
        page = context.new_page()
        page.add_init_script(STEALTH_INIT_SCRIPT)
        page.set_default_timeout(30_000)

        try:
            page.goto(FINANCAS_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)

            _fazer_login(page, email, senha)
            _navegar_para_upload(page)

            for arquivo in arquivos_validos:
                print(f"\n  Iniciando upload: {arquivo.name}")
                _fazer_upload_arquivo(page, str(arquivo))

            print("\n--- IMPORTAÇÃO CONCLUÍDA COM SUCESSO! ---")

        except Exception as e:
            print(f"\n  ERRO DURANTE A IMPORTAÇÃO: {e}")
            try:
                screenshot_path = Path(__file__).parent / "erro_importacao.png"
                page.screenshot(path=str(screenshot_path))
                print(f"  Screenshot salva em: {screenshot_path}")
            except Exception:
                pass
            raise
        finally:
            context.close()
            browser.close()
            print("  Navegador fechado.\n")


# ─────────────────────────────────────────────
# Modo Standalone (Interactive Fallback)
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
