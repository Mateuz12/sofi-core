"""
extrator_retaguarda.py — Extração automatizada do Portal Retaguarda (BH/UDI) via Playwright.

Gera o relatório de receitas de vendas (PDV Retaguarda GB Vendas Lojas)
no portal Retaguarda do Grupo Boticário, salva em formato .xls legado
na pasta de rede correspondente e, ao final, faz o upload automático
no portal FinançasGB via o utilitário compartilhado importar_financas.

Uso via CLI:
    python extrator_retaguarda.py --unidade UDI
    python extrator_retaguarda.py --unidade BH --data 02/06/2026

Uso via Dashboard Streamlit:
    Chamado como subprocesso pela página dashboard/pages/retaguarda.py
"""

from __future__ import annotations

import os
import sys
import time
import argparse
import pandas as pd
import xlwt
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

# ─────────────────────────────────────────────
# Configurar caminho do projeto e carregar ambiente dual-layer do core
# ─────────────────────────────────────────────
_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
from core.database.logger import log_execution

load_sofi_env(department="financeiro")

# Importar o utilitário de importação compartilhado
from departments.financeiro.modules.importar_financas import upload_para_financas


# ─────────────────────────────────────────────
# Constantes e Configurações
# ─────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent

PORTAL_URL  = os.getenv("RETAGUARDA_URL")
PORTAL_USER = os.getenv("RETAGUARDA_USER")
PORTAL_PASS = os.getenv("RETAGUARDA_PASS")

MESES_PT = {
    "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARCO", "04": "ABRIL",
    "05": "MAIO", "06": "JUNHO", "07": "JULHO", "08": "AGOSTO",
    "09": "SETEMBRO", "10": "OUTUBRO", "11": "NOVEMBRO", "12": "DEZEMBRO",
}

# Configuração parametrizada por unidade
CONFIGS = {
    "UDI": {
        "holding_text": "UDI LOJAS",
        "base_path": Path(r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI"),
        "filename_tpl": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.1.1 PDV RETAGUARDA GB VENDAS LOJAS.{dia}-{mes}-{ano}.xls",
    },
    "BH": {
        "holding_text": "BH",
        "base_path": Path(r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\BH"),
        "filename_tpl": "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.BH.1.1 PDV RETAGUARDA GB VENDAS LOJAS.{dia}-{mes}-{ano}.xls",
    },
}

# Seletores do portal (suporta XPath ou CSS)
XPATHS = {
    "login_user":           'input[data-cy="login-usuario-input-field"]',
    "login_pass":           'input[data-cy="login-senha-input-field"]',
    "btn_login":            'button[data-cy="login-entrar-button"]',

    "menu_financeiro":      '//*[@id="sidemenu-item-7"]/div',
    "menu_tesouraria":      '//*[@id="sidemenu-item-200"]',
    "menu_exportar_receitas": '//*[@id="sidemenu-item-1627"]',

    "campo_loja_expand":    '//div[@data-target="#collapseLojaFiltro"]',
    "btn_add_mais":         '//*[@id="jqgh_gridLoja_descricao"]/a',
    "holding_container":    '//*[@id="select2-filtroDaHolding-container"]',
    "holding_dropdown":     '//span[@aria-labelledby="select2-filtroDaHolding-container"]',
    "btn_pesquisar_popup":  '//*[@id="botaoPesquisarPopup"]',
    "check_todos_popup":    '//*[@id="marcaTodosPopupPesquisa"]',
    "btn_confirmar_popup":  '//*[@id="botaoConcluirSelecaoPopupPesquisa"]',

    "origem_container":     '//*[@id="select2-origens-container"]',
    "origem_option_todos":  '//li[contains(@class, "select2-results__option") and (text()="Todos" or text()="TODOS")]',
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
# Funções utilitárias
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


def by_xpath(page_or_frame, xpath: str):
    """Helper para localizar elementos via XPath ou CSS."""
    if xpath.startswith("/") or xpath.startswith("xpath=") or xpath.startswith("("):
        if not xpath.startswith("xpath="):
            xpath = f"xpath={xpath}"
        return page_or_frame.locator(xpath)
    return page_or_frame.locator(xpath)


def save_to_excel_97_2003(df: pd.DataFrame, path: Path) -> None:
    """Salva um DataFrame no formato Excel 97-2003 (.xls) via xlwt."""
    workbook = xlwt.Workbook(encoding="utf-8")
    sheet = workbook.add_sheet("Planilha1")

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
            except Exception:
                sheet.write(i + 1, j, str(val))

    workbook.save(str(path))


# ─────────────────────────────────────────────
# Fluxo do Portal Retaguarda
# ─────────────────────────────────────────────

def login(page: Page) -> None:
    """Faz login no portal Retaguarda."""
    print("Abrindo o portal Retaguarda...")
    page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=60_000)

    try:
        user_field = by_xpath(page, XPATHS["login_user"])
        user_field.wait_for(state="visible", timeout=15_000)
        user_field.fill(PORTAL_USER)
        by_xpath(page, XPATHS["login_pass"]).fill(PORTAL_PASS)
        print("Credenciais preenchidas. Aguardando 10 segundos antes do clique...")
        page.wait_for_timeout(10_000)
        by_xpath(page, XPATHS["btn_login"]).click()
    except Exception as e:
        print(f"Tela de login não encontrada ou já logado. Prosseguindo... ({e})")

    print("Aguardando login completo (menu financeiro)...")
    by_xpath(page, XPATHS["menu_financeiro"]).wait_for(state="visible", timeout=60_000)
    print("Login realizado com sucesso!")


def navigate_to_export(page: Page) -> None:
    """Navega nos menus: Financeiro → Tesouraria → Exportar Receitas."""
    print("Navegando nos menus...")
    by_xpath(page, XPATHS["menu_financeiro"]).click()
    by_xpath(page, XPATHS["menu_tesouraria"]).wait_for(state="visible", timeout=10_000)
    by_xpath(page, XPATHS["menu_tesouraria"]).click()
    by_xpath(page, XPATHS["menu_exportar_receitas"]).wait_for(state="visible", timeout=10_000)
    by_xpath(page, XPATHS["menu_exportar_receitas"]).click()
    page.wait_for_timeout(3_000)


def select_holding(frame, unidade: str) -> None:
    """Seleciona a holding (BH ou UDI) dentro do iframe legadoFrame.
    
    Args:
        frame: playwright Frame (não FrameLocator) para suportar evaluate().
    """
    config = CONFIGS[unidade]
    holding_text = config["holding_text"]

    print("Expandindo painel de Loja...")
    campo_loja = by_xpath(frame, XPATHS["campo_loja_expand"])
    campo_loja.wait_for(state="visible", timeout=10_000)
    campo_loja.scroll_into_view_if_needed()
    frame.wait_for_timeout(1_000)
    campo_loja.click(force=True)

    by_xpath(frame, XPATHS["btn_add_mais"]).wait_for(state="visible", timeout=10_000)
    by_xpath(frame, XPATHS["btn_add_mais"]).click()

    print(f"Buscando Holding {unidade}...")
    frame.wait_for_timeout(2_000)
    holding_box = by_xpath(frame, XPATHS["holding_dropdown"])
    holding_box.scroll_into_view_if_needed()
    frame.wait_for_timeout(1_000)
    holding_box.click(force=True)
    frame.wait_for_timeout(1_000)

    # Seleção da holding — busca flexível por texto
    if unidade == "UDI":
        holding_option = frame.locator(
            'xpath=//li[contains(@class, "select2-results__option") and text()="UDI LOJAS"]'
        )
    else:
        # BH tem variação de capitalização ("BH LOjas", "BH LOJAS")
        holding_option = frame.locator(
            'xpath=//li[contains(@class, "select2-results__option") and contains(text(), "BH")]'
        ).first

    try:
        holding_option.wait_for(state="visible", timeout=10_000)
        holding_option.click()
    except Exception:
        print(f"Aviso: Seleção direta de {unidade} falhou. Tentando busca genérica...")
        fallback = frame.locator(
            f'xpath=//li[contains(@class, "select2-results__option") and contains(text(), "{holding_text}")]'
        ).first
        fallback.click()

    by_xpath(frame, XPATHS["btn_pesquisar_popup"]).click()
    frame.wait_for_timeout(3_000)

    checkbox_todos = by_xpath(frame, XPATHS["check_todos_popup"])
    checkbox_todos.wait_for(state="visible", timeout=10_000)
    if not checkbox_todos.is_checked():
        checkbox_todos.click()
    by_xpath(frame, XPATHS["btn_confirmar_popup"]).click()


def apply_filters(frame, data_str: str) -> None:
    """Aplica os filtros de Origem, PDV e Datas no formulário do iframe.
    
    Args:
        frame: playwright Frame (não FrameLocator) para suportar evaluate().
    """
    print("Aplicando filtros de Origem e Datas...")
    frame.wait_for_timeout(1_000)

    # Origem → "Todos"
    origem_box = by_xpath(frame, XPATHS["origem_container"])
    origem_box.scroll_into_view_if_needed()
    frame.wait_for_timeout(1_000)
    origem_box.click(force=True)
    frame.wait_for_timeout(1_000)

    by_xpath(frame, XPATHS["origem_option_todos"]).wait_for(state="visible", timeout=10_000)
    by_xpath(frame, XPATHS["origem_option_todos"]).click()
    frame.wait_for_timeout(1_000)

    # Checkbox PDV
    print("Marcando checkbox PDV...")
    cb_pdv = frame.locator("#exportaRecebimentoPDV")
    if not cb_pdv.is_checked():
        cb_pdv.click(force=True)
    frame.wait_for_timeout(1_000)

    # Datas via jQuery datepicker
    print(f"Definindo datas via jQuery datepicker: {data_str}")
    frame.evaluate(f"""() => {{
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
    }}""")
    frame.wait_for_timeout(2_000)

    val_ini = frame.evaluate("() => document.getElementById('dataInicial').value")
    val_fim = frame.evaluate("() => document.getElementById('dataFinal').value")
    print(f"Datas preenchidas → Inicial: '{val_ini}' | Final: '{val_fim}'")


def export_and_download(page: Page, frame) -> Path:
    """Clica em Pesquisar, aguarda processamento, exporta e baixa o XLS.
    
    Args:
        page: playwright Page (necessário para expect_download).
        frame: playwright Frame do iframe legadoFrame.
    """
    print("Pesquisando relatório...")
    frame.locator("#botaoPesquisar").click()
    print("Aguardando 30 segundos para o processamento do portal...")
    frame.wait_for_timeout(30_000)

    print("Exportando arquivo XLS...")
    with page.expect_download(timeout=120_000) as dl_info:
        frame.locator("#exportar").wait_for(state="visible", timeout=30_000)
        frame.locator("#exportar").click()

    download = dl_info.value

    # Salva o download na pasta temporária
    temp_dir = ROOT_DIR / "temp_downloads"
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / download.suggested_filename
    download.save_as(temp_path)
    print(f"Arquivo baixado com sucesso: {temp_path.name}")
    return temp_path


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Automação Relatório Retaguarda — Extração e Upload (BH/UDI)"
    )
    parser.add_argument(
        "--unidade", type=str, required=True, choices=["BH", "UDI"],
        help="Unidade a ser processada: BH ou UDI"
    )
    parser.add_argument(
        "--data", type=str, default=None,
        help="Data no formato DD/MM/AAAA (padrão: D-1)"
    )
    return parser.parse_args()


def _run_extraction(unidade: str, data_referencia: datetime) -> None:
    """Executa a extração e upload para a unidade indicada (lógica interna)."""
    config = CONFIGS[unidade]

    dia = data_referencia.strftime("%d")
    mes_num = data_referencia.strftime("%m")
    ano = data_referencia.strftime("%Y")
    nome_mes_pasta = f"{mes_num} {MESES_PT[mes_num]}"
    data_str = f"{dia}/{mes_num}/{ano}"

    # Caminhos de rede
    target_folder = config["base_path"] / ano / nome_mes_pasta / dia
    filename_final = config["filename_tpl"].format(dia=dia, mes=mes_num, ano=ano)
    output_path = target_folder / filename_final

    print(f"Iniciando Extração da Retaguarda para {unidade} na data {data_str}")

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
            # FASE 1: Extração no Portal Retaguarda
            login(page)
            navigate_to_export(page)

            print("Entrando no iframe legadoFrame...")
            # Usa page.frame() em vez de frame_locator() para ter acesso
            # completo a evaluate(), wait_for_timeout() e locator()
            page.wait_for_selector("#legadoFrame", state="attached", timeout=15_000)
            frame = page.frame(name="legadoFrame")
            if frame is None:
                # Fallback: busca por URL parcial do iframe
                for f in page.frames:
                    if f != page.main_frame and f.url and "legado" in f.url.lower():
                        frame = f
                        break
            if frame is None:
                raise RuntimeError("Não foi possível acessar o iframe legadoFrame.")

            select_holding(frame, unidade)
            apply_filters(frame, data_str)
            temp_file = export_and_download(page, frame)

            # Converter e salvar no destino final
            df = pd.read_excel(temp_file)
            target_folder.mkdir(parents=True, exist_ok=True)
            save_to_excel_97_2003(df, output_path)
            print(f"Relatório gravado com sucesso no formato .xls legado em: {output_path}")

            # Limpeza do arquivo temporário
            os.remove(temp_file)

        except Exception as e:
            print(f"OCORREU UM ERRO DURANTE A AUTOMAÇÃO: {e}")
            try:
                screenshot_path = ROOT_DIR / "erro_automacao.png"
                page.screenshot(path=str(screenshot_path))
                print(f"Screenshot salva em: {screenshot_path}")
            except Exception as se:
                print(f"Não foi possível salvar screenshot: {se}")
            raise e
        finally:
            context.close()
            browser.close()
            print("Navegador fechado.")

    # FASE 2: Upload para o Portal Finanças GB
    print(f"\n--- FASE 2: Iniciando Importação para o Finanças GB via Playwright ---")
    success = upload_para_financas(arquivos=[output_path], unidade=unidade)
    if success:
        print("Processo concluído com SUCESSO!")
    else:
        raise Exception("Erro durante o upload do relatório no Finanças GB.")


@log_execution(modulo="Retaguarda UDI")
def run_udi(data_referencia: datetime) -> None:
    _run_extraction("UDI", data_referencia)


@log_execution(modulo="Retaguarda BH")
def run_bh(data_referencia: datetime) -> None:
    _run_extraction("BH", data_referencia)


def main():
    args = parse_args()
    unidade = args.unidade.upper()

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

    if unidade == "UDI":
        run_udi(data_referencia)
    else:
        run_bh(data_referencia)


if __name__ == "__main__":
    main()
