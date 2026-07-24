r"""
extrator_dfc.py — Extração automatizada do Fluxo Analítico (DFC) da Unidade UDI no FinançasGB.

Navega no portal FinançasGB:
  1. Login com credenciais UDI (PORTAL_USER / PORTAL_PASS)
  2. Menu lateral: Fluxo de caixa
  3. Aba: Fluxo Analítico - DFC
  4. Marca os 2 checkboxes dos filtros
  5. Preenche a data de referência inicial (Mês Atual) e final (Mês Atual + 12 Meses)
  6. Pesquisa e aguarda a geração dinâmica do relatório
  7. Baixa o relatório em Excel e salva no diretório de rede estruturado:
     \\srv-dc01\File Server\05-FIN\Fluxo Analítico Diário\UDI\<ANO>\<MÊS_FORMATADO>\<DIA>\

Uso via CLI:
    python extrator_dfc.py
    python extrator_dfc.py --data 21/07/2026
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path

from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

# ─────────────────────────────────────────────
# Resolução do projeto e ambiente SOFI
# ─────────────────────────────────────────────
_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
from core.database.logger import log_execution

load_sofi_env(department="financeiro")

from departments.financeiro.modules.importar_financas import (
    CREDENCIAIS,
    FINANCAS_URL,
    REALISTIC_USER_AGENT,
    STEALTH_INIT_SCRIPT,
    browser_args,
    env_bool,
    optional_env,
    _fazer_login,
)

UNIDADE = "UDI"
BASE_NETWORK_PATH = Path(r"\\srv-dc01\File Server\05-FIN\FLUXO ANALÍTICO DIÁRIO")

MESES_PT = {
    "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARÇO",    "04": "ABRIL",
    "05": "MAIO",    "06": "JUNHO",     "07": "JULHO",    "08": "AGOSTO",
    "09": "SETEMBRO","10": "OUTUBRO",  "11": "NOVEMBRO", "12": "DEZEMBRO",
}

XPATHS = {
    "menu_fluxo_caixa": 'xpath=//*[@id="mfe-sidebar-react"]/div/nav/div[2]/div[8]/a',
    "aba_dfc":          'xpath=//*[@id="tabstrip"]/ul/li[2]/a',
    "checkbox_1":       'xpath=//*[@id="undefined-1"]/div[1]/div[1]/div[2]/div/div[2]/div/div/div[9]/label/input',
    "checkbox_2":       'xpath=//*[@id="undefined-1"]/div[1]/div[1]/div[2]/div/div[2]/div/div/div[11]/label/input',
    "data_inicio":      'xpath=//*[@id="undefined-1"]/div[1]/div[1]/div[2]/div/div[1]/div/div/div[5]/span/span/input',
    "data_fim":         'xpath=//*[@id="undefined-1"]/div[1]/div[1]/div[2]/div/div[1]/div/div/div[6]/span/span/input',
    "btn_pesquisar":    'xpath=//*[@id="undefined-1"]/div[1]/div[1]/div[3]/button[2]',
    "btn_exportar":     'a[data-bind="click: Analitico.Exportar"]',
}

EXIT_OK        = 0
EXIT_RETRYABLE = 1
EXIT_PERMANENT = 2


def _encontrar_e_clicar_aba_dfc(page: Page) -> None:
    """Localiza e clica na aba 'Fluxo Analítico - DFC'."""
    print("  Aguardando renderização da página de Fluxo de caixa...")
    page.wait_for_timeout(3000)

    try:
        clicou_js = page.evaluate("""() => {
            const tab = document.querySelector('li[data-value="analitico"] a') || document.querySelector('li[data-value="analitico"]');
            if (tab) {
                tab.click();
                return true;
            }
            return false;
        }""")
        if clicou_js:
            print("  [OK] Aba 'Fluxo Analítico - DFC' clicada via JS.")
            page.wait_for_timeout(2000)
            return
    except Exception:
        pass

    seletores_aba = [
        XPATHS["aba_dfc"],
        "li[data-value='analitico'] a",
        "li[data-value='analitico']",
        "a:has-text('Fluxo Analítico - DFC')",
    ]

    for sel in seletores_aba:
        try:
            locator = page.locator(sel).first
            if locator.is_visible(timeout=3000) or locator.is_attached():
                locator.scroll_into_view_if_needed()
                locator.click(force=True)
                print(f"  [OK] Aba DFC clicada via seletor: {sel}")
                page.wait_for_timeout(2000)
                return
        except Exception:
            continue

    try:
        page.get_by_text("Fluxo Analítico - DFC", exact=False).first.click(force=True)
        print("  [OK] Clique fallback get_by_text efetuado.")
    except Exception as e:
        raise RuntimeError(f"Não foi possível clicar na aba 'Fluxo Analítico - DFC': {e}")


def _garantir_checkbox(page: Page, xpath: str, descricao: str) -> None:
    """Garante a marcação do checkbox via clique triplo (JS, input e label)."""
    print(f"  [Filtro] Garantindo marcação do Checkbox {descricao}...")
    page.wait_for_timeout(500)

    try:
        page.evaluate(f"""(xpath_str) => {{
            function triggerCheck(el) {{
                if (el) {{
                    el.click();
                    el.checked = true;
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}
            let el = null;
            try {{
                const res = document.evaluate(xpath_str.replace('xpath=', ''), document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                el = res.singleNodeValue;
            }} catch(e) {{}}

            if (el) {{
                triggerCheck(el);
            }} else {{
                const idx = '{descricao}'.includes('1') ? 0 : 1;
                const cbs = document.querySelectorAll('input[type="checkbox"]');
                if (cbs[idx]) triggerCheck(cbs[idx]);
            }}
        }}""", xpath)
        print(f"    [OK] Checkbox {descricao} acionado via JS.")
    except Exception as e:
        print(f"    [Aviso] Clique JS no checkbox {descricao}: {e}")

    try:
        cb = page.locator(xpath)
        if cb.is_attached():
            cb.scroll_into_view_if_needed()
            cb.click(force=True)
    except Exception:
        pass

    try:
        parent_label = page.locator(f"{xpath}/ancestor::label")
        if parent_label.is_attached():
            parent_label.click(force=True)
    except Exception:
        pass


def _preencher_campo_data_mensal(page: Page, xpath: str, data_str: str, rotulo: str) -> None:
    """Preenche um campo de data mensal via XPath fixo com digitação e disparo de eventos."""
    print(f"  [Filtro] Preenchendo {rotulo} ({data_str})...")
    try:
        field = page.locator(xpath)
        field.wait_for(state="visible", timeout=20_000)
        field.scroll_into_view_if_needed()
        field.click()
        page.wait_for_timeout(300)

        field.fill("")
        page.wait_for_timeout(200)
        field.fill(data_str)
        page.wait_for_timeout(200)
        field.press("Tab")

        page.evaluate(f"""(xpath_str) => {{
            const result = document.evaluate(xpath_str.replace('xpath=', ''), document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            const el = result.singleNodeValue;
            if (el) {{
                el.value = '{data_str}';
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
            }}
        }}""", xpath)
        print(f"    [OK] {rotulo} preenchido com sucesso.")
    except Exception as e:
        print(f"    [ERRO] Falha ao preencher {rotulo} via XPath: {e}")


def _aguardar_carregamento_relatorio(page: Page) -> None:
    """Aguarda de forma inteligente e dinâmica a conclusão da geração do relatório DFC."""
    print("  Iniciando espera pela geração do relatório DFC (UDI)...")
    page.wait_for_timeout(3000)

    indicador_detectado = False
    selectors_loading = ".k-loading-mask, .k-loading-image, .k-i-loading, .k-block-ui, .loading, .spinner, [class*='loading']"
    
    try:
        page.wait_for_selector(selectors_loading, state="visible", timeout=8000)
        print("  [Loading] Spinner/Mask de carregamento detectado na tela.")
        indicador_detectado = True
    except Exception:
        print("  [Loading] Spinner não foi detectado (requisição rápida ou já iniciou).")

    if indicador_detectado:
        try:
            print("  Aguardando o encerramento do carregamento...")
            page.wait_for_selector(selectors_loading, state="hidden", timeout=300_000)
            print("  [OK] Spinner/Mask de carregamento desapareceu. Relatório pronto!")
        except Exception as e:
            print(f"  [Aviso] Timeout aguardando remoção do spinner: {e}")

    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
    except Exception:
        pass

    try:
        print("  Aguardando o botão 'Exportar Excel' estar visível...")
        page.locator('a[data-bind*="Analitico.Exportar"], li[data-original-title*="Exportar"]').first.wait_for(state="visible", timeout=60_000)
        print("  [OK] Botão 'Exportar Excel' está totalmente visível!")
    except Exception:
        print("  [Aviso] Aguarde adicional de 5s para garantia da renderização final do DOM...")
        page.wait_for_timeout(5000)


def _clicar_exportar_excel(page: Page) -> None:
    """Aciona a exportação para Excel via Knockout.js e seletores de fallback."""
    print("  Acionando exportação para Excel (UDI)...")
    page.wait_for_timeout(2000)

    try:
        clicou_js = page.evaluate("""() => {
            const btn = document.querySelector('a[data-bind*="Analitico.Exportar"]')
                     || document.querySelector('li[data-original-title*="Exportar"] a')
                     || document.querySelector('li[data-original-title*="Exportar"]');
            if (btn) {
                btn.scrollIntoView({ block: 'center' });
                btn.click();
                if (window.ko && ko.dataFor && ko.dataFor(btn) && ko.dataFor(btn).Analitico && ko.dataFor(btn).Analitico.Exportar) {
                    try { ko.dataFor(btn).Analitico.Exportar(); } catch(e) {}
                }
                return true;
            }
            return false;
        }""")
        if clicou_js:
            print("    [OK] Clique em 'Exportar Excel' acionado via binding Knockout (Analitico.Exportar).")
            return
    except Exception as e:
        print(f"    [Aviso] Acionamento JS de Analitico.Exportar: {e}")

    seletores = [
        'a[data-bind="click: Analitico.Exportar"]',
        'a[data-bind*="Analitico.Exportar"]',
        'li[data-original-title="Exportar para Excel"] a',
        'li[data-original-title="Exportar para Excel"]',
        XPATHS["btn_exportar"],
        "a:has-text('Exportar Excel')",
        "span:has-text('Exportar Excel')",
        "text=Exportar Excel",
    ]

    for sel in seletores:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000) or el.is_attached():
                el.scroll_into_view_if_needed()
                el.click(force=True)
                print(f"    [OK] Clique efetuado via seletor: {sel}")
                return
        except Exception:
            continue

    try:
        page.get_by_text("Exportar Excel", exact=False).first.click(force=True)
        print("    [OK] Clique fallback via get_by_text efetuado.")
    except Exception as e:
        raise RuntimeError(f"Não foi possível clicar no botão 'Exportar Excel': {e}")


def _navegar_e_extrair_dfc(page: Page, data_ref: datetime) -> Path:
    """Executa os passos de navegação, preenchimento, geração e download do DFC UDI."""
    print("  Clicando em 'Fluxo de caixa' no menu lateral (UDI)...")
    menu_btn = page.locator(XPATHS["menu_fluxo_caixa"])
    try:
        menu_btn.wait_for(state="visible", timeout=30_000)
        menu_btn.click(force=True)
    except PlaywrightTimeoutError:
        print("  [Fallback] Tentando localizar menu pelo texto 'Fluxo de caixa'...")
        page.get_by_text("Fluxo de caixa", exact=False).first.click(force=True)

    page.wait_for_timeout(4000)

    _encontrar_e_clicar_aba_dfc(page)
    page.wait_for_timeout(3000)

    _garantir_checkbox(page, XPATHS["checkbox_1"], "1 (posição 9)")
    _garantir_checkbox(page, XPATHS["checkbox_2"], "2 (posição 11)")

    dt_inicio = data_ref
    dt_fim    = data_ref + relativedelta(years=1)

    str_data_inicio = dt_inicio.strftime("%m/%Y")
    str_data_fim    = dt_fim.strftime("%m/%Y")

    _preencher_campo_data_mensal(page, XPATHS["data_inicio"], str_data_inicio, "Data Referência Início")
    _preencher_campo_data_mensal(page, XPATHS["data_fim"], str_data_fim, "Data Referência Fim")

    print("  Clicando no botão 'Pesquisar'...")
    try:
        btn_pesquisar = page.locator(XPATHS["btn_pesquisar"])
        btn_pesquisar.wait_for(state="visible", timeout=15_000)
        btn_pesquisar.click(force=True)
    except Exception:
        page.get_by_role("button", name=re.compile(r"Pesquisar", re.I)).first.click(force=True)

    _aguardar_carregamento_relatorio(page)

    with page.expect_download(timeout=180_000) as dl_info:
        _clicar_exportar_excel(page)

    download = dl_info.value
    original_filename = download.suggested_filename or "DFC_Fluxo_Analitico_UDI.xlsx"
    print(f"  Download concluído pelo navegador: {original_filename}")

    dia = data_ref.strftime("%d")
    mes_num = data_ref.strftime("%m")
    ano = data_ref.strftime("%Y")
    nome_mes_pasta = f"{mes_num} {MESES_PT.get(mes_num, 'MES')}"

    target_dir = BASE_NETWORK_PATH / UNIDADE / ano / nome_mes_pasta / dia
    target_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(original_filename).suffix or ".xlsx"
    target_filename = f"DFC_Fluxo_Analitico_UDI_{dia}-{mes_num}-{ano}{ext}"
    target_path = target_dir / target_filename

    download.save_as(str(target_path))
    print(f"  [OK] Relatório DFC UDI gravado com sucesso em: {target_path}")

    return target_path


@log_execution(modulo="Fluxo Analítico DFC UDI")
def main() -> None:
    parser = argparse.ArgumentParser(description="Extração Automatizada DFC UDI - FinançasGB")
    parser.add_argument("--unidade", type=str, default="UDI", help="Reservado para compatibilidade")
    parser.add_argument("--data", type=str, default=None, help="Data de referência (DD/MM/AAAA) - padrão: hoje")
    parser.add_argument("--dias", type=int, default=0, help="Reservado para compatibilidade")
    args = parser.parse_args()

    if args.data:
        try:
            data_ref = datetime.strptime(args.data, "%d/%m/%Y")
        except ValueError:
            print(f"Data inválida '{args.data}'. Usando data atual.")
            data_ref = datetime.now()
    else:
        data_ref = datetime.now()

    credenciais = CREDENCIAIS[UNIDADE]
    email = credenciais["email"]
    senha = credenciais["senha"]

    if not email or not senha:
        raise RuntimeError(f"Credenciais do FinançasGB não encontradas para unidade '{UNIDADE}'.")

    print(f"\n--- EXTRAÇÃO FLUXO ANALÍTICO (DFC) — FinançasGB ({UNIDADE}) ---")
    print(f"  Data de Referência: {data_ref.strftime('%d/%m/%Y')}")

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
            print(f"  Abrindo portal FinançasGB ({UNIDADE})...")
            page.goto(FINANCAS_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)

            _fazer_login(page, email, senha)

            target_file = _navegar_e_extrair_dfc(page, data_ref)
            print(f"\n--- PROCESSO DFC UDI CONCLUÍDO COM SUCESSO! ---")
            print(f"  Arquivo salvo: {target_file}")

        except Exception as e:
            print(f"\n  [ERRO FATAL] Falha durante a extração do DFC UDI: {e}")
            try:
                err_png = Path(__file__).parent / "erro_dfc_udi.png"
                page.screenshot(path=str(err_png))
                print(f"  Screenshot de erro salvo em: {err_png}")
            except Exception:
                pass
            raise e
        finally:
            context.close()
            browser.close()
            print("  Navegador fechado.\n")


if __name__ == "__main__":
    try:
        main()
        sys.exit(EXIT_OK)
    except Exception:
        sys.exit(EXIT_RETRYABLE)
