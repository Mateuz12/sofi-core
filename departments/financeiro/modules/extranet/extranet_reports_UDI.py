from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

# Carrega o .env global do SOFI
# Carrega o .env global do SOFI + .env.local do departamento
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

# Importa o logger
_ROOT_L = Path(__file__).resolve()
while not (_ROOT_L / ".env").exists() and _ROOT_L != _ROOT_L.parent:
    _ROOT_L = _ROOT_L.parent
if str(_ROOT_L) not in sys.path:
    sys.path.insert(0, str(_ROOT_L))
from core.database.logger import log_execution

ROOT = Path(__file__).resolve().parent
DOWNLOADS_DIR = ROOT / "downloads"

# XPaths estáveis (IDs fixos do portal, não mudam entre sessões)
XPATHS = {
    "user": '//*[@id="signInName"]',
    "password": '//*[@id="password"]',
    "codigo_cs": '//*[@id="multiple-selection-codigo-da-cs"]',
    "data": '//*[@id="DateAndStatus"]',
}

MONTH_NAMES_DIR = {
    1: "01 JANEIRO", 2: "02 FEVEREIRO", 3: "03 MARÇO", 4: "04 ABRIL",
    5: "05 MAIO", 6: "06 JUNHO", 7: "07 JULHO", 8: "08 AGOSTO",
    9: "09 SETEMBRO", 10: "10 OUTUBRO", 11: "11 NOVEMBRO", 12: "12 DEZEMBRO",
}

def get_target_path(target_date: datetime, filename: str) -> Path:
    # Caminho base na rede
    base_dir = Path(r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI")
    
    year_str = str(target_date.year)
    month_str = MONTH_NAMES_DIR[target_date.month]
    day_str = f"{target_date.day:02d}"
    
    target_dir = base_dir / year_str / month_str / day_str
    target_dir.mkdir(parents=True, exist_ok=True)
    
    return target_dir / filename


def validate_report_not_empty(file_path: Path, report_name: str) -> None:
    """Verifica se o relatório baixado não está em branco.
    
    Lê o conteúdo do arquivo e verifica se há dados além de cabeçalhos vazios.
    Se estiver em branco, remove o arquivo e levanta um erro para parar a operação.
    """
    if not file_path.exists():
        raise RuntimeError(f"⚠ ERRO: Arquivo do relatório '{report_name}' não foi encontrado em: {file_path}")
    
    file_size = file_path.stat().st_size
    if file_size == 0:
        file_path.unlink()  # Remove o arquivo em branco
        raise RuntimeError(
            f"⚠ RELATÓRIO EM BRANCO: O relatório '{report_name}' está completamente vazio (0 bytes).\n"
            f"  Arquivo descartado: {file_path}\n"
            f"  Operação interrompida."
        )
    
    # Lê o conteúdo para verificar se há dados reais (não só cabeçalho/linhas vazias)
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        # Se não conseguir ler como texto (ex: .xls binário), verifica só pelo tamanho
        # Arquivos XLS válidos têm pelo menos alguns KB
        if file_size < 100:
            file_path.unlink()
            raise RuntimeError(
                f"⚠ RELATÓRIO EM BRANCO: O relatório '{report_name}' parece estar vazio ({file_size} bytes).\n"
                f"  Arquivo descartado: {file_path}\n"
                f"  Operação interrompida."
            )
        print(f"  ✔ Relatório '{report_name}' validado ({file_size} bytes).")
        return
    
    # Para CSV: verifica se tem mais que só o cabeçalho
    lines = [line for line in content.splitlines() if line.strip()]
    if len(lines) <= 1:
        file_path.unlink()  # Remove o arquivo em branco
        raise RuntimeError(
            f"⚠ RELATÓRIO EM BRANCO: O relatório '{report_name}' contém apenas cabeçalho ou está vazio "
            f"({len(lines)} linha(s) com conteúdo).\n"
            f"  Arquivo descartado: {file_path}\n"
            f"  Operação interrompida."
        )
    
    print(f"  ✔ Relatório '{report_name}' validado ({len(lines)} linhas com conteúdo).")

STORE_CODES = ["23275", "20844", "24417"]



def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "s"}


# User-Agent realista para evitar detecção de bot
REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Script injetado antes de cada página para mascarar automação
STEALTH_INIT_SCRIPT = """
// Remove a flag que denuncia automação
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Simula plugins reais do Chrome
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// Simula linguagens reais
Object.defineProperty(navigator, 'languages', {
    get: () => ['pt-BR', 'pt', 'en-US', 'en'],
});
"""


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


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Preencha {name} no arquivo .env antes de executar.")
    return value


def optional_env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def by_xpath(page_or_locator: Page | Locator, xpath: str) -> Locator:
    return page_or_locator.locator(f"xpath={xpath}")


def click_first_available(page: Page, locators: list[Locator], description: str, timeout: int = 20_000) -> None:
    last_error: Exception | None = None
    for locator in locators:
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
            locator.first.click()
            return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Nao consegui clicar em {description}. Ultimo erro: {last_error}")


# Mapeamento dos meses em português para comparar com o calendário
MONTH_NAMES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def _navigate_to_month(page: Page, target_month: int, target_year: int) -> None:
    """Navega o calendário até o mês/ano desejado usando a seta de voltar."""
    target_month_label = f"{MONTH_NAMES_PT[target_month]} {target_year}"
    max_nav = 24
    for nav_attempt in range(max_nav):
        # Verifica se o mês alvo está visível na tela
        target_label = page.get_by_text(target_month_label)
        try:
            if target_label.first.is_visible(timeout=1_000):
                print(f"  Mês '{target_month_label}' encontrado no calendário.")
                return
        except Exception:
            pass

        # Clica na seta de voltar (mês anterior) - tenta várias estratégias
        back_clicked = False
        back_selectors = [
            "button[aria-label*='anterior']",
            "button[aria-label*='previous']",
            "button[name='previous-month']",
            "button:has(svg):left-of(:text('Janeiro'), :text('Fevereiro'), :text('Março'), "
            ":text('Abril'), :text('Maio'), :text('Junho'), :text('Julho'), :text('Agosto'), "
            ":text('Setembro'), :text('Outubro'), :text('Novembro'), :text('Dezembro'))",
        ]

        for selector in back_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=1_000):
                    btn.click()
                    back_clicked = True
                    break
            except Exception:
                continue

        if not back_clicked:
            try:
                arrow_btn = page.locator("button").filter(has_text="←").first
                arrow_btn.click()
                back_clicked = True
            except Exception:
                pass

        if not back_clicked:
            print(f"  Aviso: não encontrei botão de voltar mês (tentativa {nav_attempt + 1})")

        page.wait_for_timeout(600)
    else:
        raise RuntimeError(
            f"Não consegui navegar até o mês {target_month_label} no calendário "
            f"após {max_nav} tentativas."
        )


def _click_day_in_calendar(page: Page, day: int, label: str) -> None:
    """Clica em um dia específico no calendário aberto."""
    day_str = str(day)
    day_locators = [
        page.get_by_role("gridcell", name=day_str, exact=True),
        page.get_by_role("button", name=day_str, exact=True),
        page.locator(f"button:text-is('{day_str}')"),
        page.locator(f"td:text-is('{day_str}')"),
        page.locator(f"div:text-is('{day_str}')"),
    ]

    for day_btns in day_locators:
        if day_btns.count() == 0:
            continue
        for i in range(day_btns.count()):
            btn = day_btns.nth(i)
            try:
                if not btn.is_visible() or not btn.is_enabled():
                    continue
                classes = btn.get_attribute("class") or ""
                aria_disabled = btn.get_attribute("aria-disabled") or "false"
                if "outside" in classes.lower() or "disabled" in classes.lower() or aria_disabled == "true":
                    continue
                btn.click()
                print(f"  Dia {day} clicado ({label}).")
                return
            except Exception:
                continue
    # Fallback
    print(f"  Aviso: fallback para dia {day} ({label}).")
    page.get_by_text(day_str, exact=True).first.click()


def pick_date_range_from_calendar(
    page: Page, xpath: str, start_date: datetime, end_date: datetime
) -> None:
    """Seleciona um intervalo de datas no calendário visual do portal.

    1. Clica no campo para abrir o calendário
    2. Navega até o mês da data início e clica no dia (1º clique = data início)
    3. Se a data fim estiver em outro mês, navega até ele
    4. Clica no dia da data fim (2º clique = data final)
    """
    print(
        f"  Abrindo calendário para selecionar intervalo: "
        f"{start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}..."
    )

    # Abre o calendário clicando no campo
    field = by_xpath(page, xpath)
    field.wait_for(state="visible", timeout=20_000)
    field.click()
    page.wait_for_timeout(1_500)

    # Verifica se o calendário abriu procurando qualquer nome de mês visível
    calendar_opened = False
    for month_name in MONTH_NAMES_PT.values():
        try:
            locator = page.get_by_text(re.compile(f"{month_name} \\d{{4}}"))
            if locator.first.is_visible(timeout=2_000):
                calendar_opened = True
                print(f"  Calendário aberto. Mês visível: {locator.first.inner_text()}")
                break
        except Exception:
            continue

    if not calendar_opened:
        print("  Calendário não abriu no primeiro clique. Tentando novamente...")
        field.click()
        page.wait_for_timeout(2_000)

    # --- 1º clique: data início ---
    _navigate_to_month(page, start_date.month, start_date.year)
    _click_day_in_calendar(page, start_date.day, "data inicial")
    page.wait_for_timeout(800)

    # --- 2º clique: data final ---
    # Se a data fim estiver em um mês diferente, navega para frente
    if (end_date.year, end_date.month) != (start_date.year, start_date.month):
        # Precisa avançar meses – usa seta de avançar (next)
        end_month_label = f"{MONTH_NAMES_PT[end_date.month]} {end_date.year}"
        print(f"  Navegando para mês da data final: {end_month_label}...")
        max_fwd = 12
        for _ in range(max_fwd):
            try:
                lbl = page.get_by_text(end_month_label)
                if lbl.first.is_visible(timeout=1_000):
                    print(f"  Mês '{end_month_label}' encontrado.")
                    break
            except Exception:
                pass

            # Tenta clicar na seta de avançar (próximo mês)
            fwd_clicked = False
            fwd_selectors = [
                "button[aria-label*='próximo']",
                "button[aria-label*='proximo']",
                "button[aria-label*='next']",
                "button[name='next-month']",
            ]
            for sel in fwd_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=1_000):
                        btn.click()
                        fwd_clicked = True
                        break
                except Exception:
                    continue

            if not fwd_clicked:
                try:
                    arrow_btn = page.locator("button").filter(has_text="→").first
                    arrow_btn.click()
                except Exception:
                    pass

            page.wait_for_timeout(600)

    _click_day_in_calendar(page, end_date.day, "data final")
    page.wait_for_timeout(500)


def is_browser_error_page(page: Page) -> bool:
    title = ""
    body_text = ""

    try:
        title = page.title()
    except Exception:
        pass

    try:
        body_text = page.locator("body").inner_text(timeout=2_000)
    except Exception:
        pass

    error_markers = [
        "Nao e possivel acessar esse site",
        "Não é possível acessar esse site",
        "This site can't be reached",
        "ERR_",
    ]
    text = f"{title}\n{body_text}"
    return any(marker in text for marker in error_markers)


def safe_goto(page: Page, url: str, retries: int = 3) -> None:
    """Navega para a URL com retry em caso de erro HTTP2 ou crash."""
    for attempt in range(1, retries + 1):
        try:
            print(f"  Navegando para {url} (tentativa {attempt}/{retries})...")
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            if not is_browser_error_page(page):
                return
            print(f"  Pagina de erro detectada na tentativa {attempt}. Esperando antes de tentar de novo...")
        except Exception as exc:
            print(f"  Erro na navegacao (tentativa {attempt}): {exc}")
        time.sleep(5)
    # Última tentativa sem catch
    page.goto(url, wait_until="commit", timeout=60_000)


def is_logged_in(page: Page) -> bool:
    """Verifica se a página já está na área logada da extranet."""
    current = page.url
    # Se estiver na página principal da extranet (não na tela de login)
    if "extranet.grupoboticario.com.br" in current and "login." not in current:
        return True
    return False


def wait_for_portal_after_login(page: Page, url: str) -> None:
    print("Login enviado. Aguardando redirecionamento do portal...")

    # Espera o redirect do OAuth completar (sai do dominio login.extranet)
    max_wait = 90  # segundos
    start = time.time()
    while time.time() - start < max_wait:
        current = page.url
        # Já saiu da tela de login? Sucesso!
        if is_logged_in(page):
            print(f"  Login completado! URL: {current}")
            break

        # Verifica se tem erro na página
        if is_browser_error_page(page):
            print("  Pagina de erro detectada. Forçando navegação para a URL principal...")
            safe_goto(page, url)
            time.sleep(3)
            continue

        # Espera um pouco antes de checar de novo
        page.wait_for_timeout(2_000)
    else:
        # Timeout - tenta navegar direto para a extranet
        print(f"  Login não redirecionou em {max_wait}s. Tentando navegar direto...")
        safe_goto(page, url)
        page.wait_for_timeout(5_000)

    print(f"URL final depois do login: {page.url}")

    # Aguarda a sidebar com o menu Financeiro ficar visivel
    print("  Aguardando sidebar carregar...")
    page.get_by_text("Financeiro", exact=True).first.wait_for(state="visible", timeout=120_000)
    print("  Sidebar carregada.")


def login(page: Page, url: str, user: str, password: str) -> None:
    print("Abrindo extranet...")
    safe_goto(page, url)

    by_xpath(page, XPATHS["user"]).wait_for(state="visible", timeout=60_000)
    by_xpath(page, XPATHS["user"]).fill(user)
    by_xpath(page, XPATHS["password"]).fill(password)
    print("Credenciais preenchidas. Aguardando 10 segundos antes de enviar o login...")
    time.sleep(10)
    page.keyboard.press("Enter")
    wait_for_portal_after_login(page, url)


def open_reports_area(page: Page) -> None:
    print("Abrindo menu Financeiro > Relatorios...")

    # Clica em "Financeiro" na sidebar esquerda
    financeiro = page.get_by_text("Financeiro", exact=True).first
    financeiro.click()
    page.wait_for_timeout(1_500)

    # O botão Relatórios pode estar direto em "Mais acessados" ou dentro de "Portal de gestão de crédito"
    relatorios = page.get_by_text("Relatórios", exact=True)
    
    # Tenta clicar em "Portal de gestão de crédito" para abrir o submenu caso Relatórios não esteja visível
    try:
        if relatorios.count() == 0 or not relatorios.first.is_visible():
            portal_credito = page.get_by_text("Portal de gestão de crédito")
            if portal_credito.count() > 0 and portal_credito.first.is_visible():
                print("  Abrindo submenu 'Portal de gestão de crédito'...")
                portal_credito.first.click()
                page.wait_for_timeout(1_500)
    except Exception:
        pass

    # Aguarda o botão Relatórios ficar visível e clica
    relatorios.first.wait_for(state="visible", timeout=10_000)
    relatorios.first.click()
    page.wait_for_timeout(2_000)

    # Aguarda a página de relatórios carregar (URL deve conter 'relatorios')
    try:
        page.wait_for_url(lambda u: "relatorios" in u.lower(), timeout=15_000)
        print(f"  Página de relatórios carregada: {page.url}")
    except PlaywrightTimeoutError:
        print(f"  Aviso: URL não mudou para relatórios. URL atual: {page.url}")

    # Fecha o dropdown do menu clicando fora dele ou pressionando Escape
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    # Clica no corpo da página para garantir que o dropdown fechou
    try:
        page.locator("main").first.click(position={"x": 500, "y": 300})
    except Exception:
        try:
            page.locator("body").click(position={"x": 500, "y": 300})
        except Exception:
            pass
    page.wait_for_timeout(500)


def select_store_codes(page: Page) -> None:
    print("Selecionando Codigos da CS...")
    cs_field = by_xpath(page, XPATHS["codigo_cs"])
    cs_field.wait_for(state="visible", timeout=20_000)
    cs_field.click()
    page.wait_for_timeout(1_000)

    for code in STORE_CODES:
        print(f"  Selecionando loja {code}...")
        clicked = False
        
        # Tenta primeiro a correspondência exata, depois parcial
        for exact_match in [True, False]:
            options = page.get_by_text(code, exact=exact_match)
            try:
                # Aguarda apenas na primeira tentativa
                if exact_match:
                    options.first.wait_for(state="visible", timeout=5_000)
                
                for i in range(options.count()):
                    opt = options.nth(i)
                    if not opt.is_visible():
                        continue
                    
                    # Evita clicar no código se ele estiver dentro da tabela de relatórios gerados
                    is_in_table = opt.evaluate("el => el.closest('table') !== null")
                    if not is_in_table:
                        opt.click()
                        page.wait_for_timeout(500)
                        clicked = True
                        break
            except Exception:
                pass
                
            if clicked:
                break

        if not clicked:
            print(f"  Aviso: não consegui clicar na loja {code} (nenhuma opção válida encontrada fora da tabela)")

    page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def wait_for_new_completed_report_row(page: Page, timeout_ms: int = 180_000) -> Locator:
    print("Aguardando a nova linha com selo 'Novo' e status 'Concluido'...")

    deadline = datetime.now().timestamp() + timeout_ms / 1000
    expected_codes = ", ".join(STORE_CODES)
    last_rows_count = 0

    while datetime.now().timestamp() < deadline:
        rows = page.locator("table tbody tr")
        last_rows_count = rows.count()

        for index in range(last_rows_count):
            row = rows.nth(index)
            text = row.inner_text(timeout=2_000)
            normalized = " ".join(text.split())

            has_new_badge = re.search(r"\bNovo\b", normalized, re.I)
            has_done_status = re.search(r"Conclu[ií]do", normalized, re.I)
            has_expected_codes = all(code in normalized for code in STORE_CODES) or expected_codes in normalized

            if has_new_badge and has_done_status and has_expected_codes:
                print(f"Linha nova encontrada: {normalized}")
                return row

        page.wait_for_timeout(3_000)

    raise TimeoutError(f"Nao apareceu linha nova concluida em {timeout_ms / 1000:.0f}s. Linhas vistas: {last_rows_count}")


def download_csv_from_row(page: Page, row: Locator, target_path: Path) -> Path:
    print(f"Baixando CSV da linha nova para: {target_path.name}...")

    csv_button = row.locator("td").nth(4).locator("button").first
    if csv_button.count() == 0:
        csv_button = row.locator("button").first

    with page.expect_download(timeout=60_000) as download_info:
        csv_button.click()

    download = download_info.value
    target_path.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(target_path)

    print(f"Download salvo em: {target_path}")
    return target_path


def download_xls_from_row(page: Page, row: Locator, target_path: Path) -> Path:
    print(f"Baixando XLS da linha nova para: {target_path.name}...")

    # O botão XLS costuma ser o segundo botão dentro do td
    xls_button = row.locator("td").nth(4).locator("button").nth(1)
    if xls_button.count() == 0:
        # Se não tiver um segundo botão, tenta pegar o último botão
        xls_button = row.locator("button").last

    with page.expect_download(timeout=60_000) as download_info:
        xls_button.click()

    download = download_info.value
    target_path.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(target_path)

    print(f"Download salvo em: {target_path}")
    return target_path


def open_sales_report_tab(page: Page) -> None:
    """Abre a aba 'Relatório de Vendas' usando seletores por texto (não IDs dinâmicos)."""
    print("Abrindo aba Relatorio de Vendas...")

    # Procura por um trigger/tab que contenha "Relatório de Vendas" ou "Relatorio de Vendas"
    tab_selectors = [
        page.get_by_role("tab", name=re.compile(r"Relat[oó]rio de Vendas", re.I)),
        page.get_by_text(re.compile(r"Relat[oó]rio de Vendas", re.I)),
        page.locator("[data-state] >> text=Relatório de Vendas"),
        # Fallback: procura pelo ID parcial que contém 'salesReports'
        page.locator("[id*='salesReports'][id*='trigger']"),
    ]

    for selector in tab_selectors:
        try:
            if selector.first.is_visible(timeout=5_000):
                selector.first.click()
                print("  Aba 'Relatório de Vendas' clicada.")
                page.wait_for_timeout(1_000)
                return
        except Exception:
            continue

    raise RuntimeError("Não encontrei a aba 'Relatório de Vendas' na página.")


def click_generate_report_button(page: Page) -> None:
    """Clica no botão 'Gerar relatório' usando seletores por texto (não IDs dinâmicos)."""
    print("Gerando relatorio...")

    btn_selectors = [
        page.get_by_role("button", name=re.compile(r"Gerar", re.I)),
        page.get_by_text(re.compile(r"Gerar\s+relat[oó]rio", re.I)),
        page.locator("button:has-text('Gerar')"),
        # Fallback: procura pelo ID parcial que contém 'salesReports'
        page.locator("[id*='salesReports'] button").last,
    ]

    for selector in btn_selectors:
        try:
            if selector.first.is_visible(timeout=5_000):
                selector.first.click()
                print("  Botão 'Gerar relatório' clicado.")
                return
        except Exception:
            continue

    raise RuntimeError("Não encontrei o botão 'Gerar relatório' na página.")


def generate_sales_report(page: Page) -> Path:
    d_minus_1 = datetime.now() - timedelta(days=1)
    d_minus_5 = datetime.now() - timedelta(days=5)

    open_sales_report_tab(page)

    select_store_codes(page)

    print(f"Filtrando período: {d_minus_5.strftime('%d/%m/%Y')} até {d_minus_1.strftime('%d/%m/%Y')}")
    pick_date_range_from_calendar(page, XPATHS["data"], d_minus_5, d_minus_1)

    click_generate_report_button(page)

    row = wait_for_new_completed_report_row(page)
    
    data_str = d_minus_1.strftime('%d-%m-%Y')
    filename = f"05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI. 4.1 BOLETOS VENDAS - MOOZ BOLETOS .{data_str}.csv"
    target_path = get_target_path(d_minus_1, filename)
    
    return download_csv_from_row(page, row, target_path)


def open_receivables_report_tab(page: Page) -> None:
    """Abre a aba 'Relatório de Recebíveis'."""
    print("Abrindo aba Relatorio de Recebiveis...")

    tab_selectors = [
        page.locator('//*[@id="radix-:rjg:-trigger-financialTransfersReports"]'),
        page.get_by_role("tab", name=re.compile(r"Relat[oó]rio de Receb[ií]veis", re.I)),
        page.get_by_text(re.compile(r"Relat[oó]rio de Receb[ií]veis", re.I)),
        page.locator("[data-state] >> text=Relatório de Recebíveis"),
        page.locator("[id*='financialTransfersReports'][id*='trigger']"),
    ]

    for selector in tab_selectors:
        try:
            if selector.first.is_visible(timeout=5_000):
                selector.first.click()
                print("  Aba 'Relatório de Recebíveis' clicada.")
                page.wait_for_timeout(1_000)
                return
        except Exception:
            continue

    raise RuntimeError("Não encontrei a aba 'Relatório de Recebíveis' na página.")


def generate_receivables_report(page: Page) -> Path:
    d_minus_1 = datetime.now() - timedelta(days=1)
    d_minus_5 = datetime.now() - timedelta(days=5)

    open_receivables_report_tab(page)

    # Como o layout é igual, usamos as mesmas funções de preenchimento
    select_store_codes(page)

    print(f"Filtrando período para Recebiveis: {d_minus_5.strftime('%d/%m/%Y')} até {d_minus_1.strftime('%d/%m/%Y')}")
    pick_date_range_from_calendar(page, XPATHS["data"], d_minus_5, d_minus_1)

    click_generate_report_button(page)

    row = wait_for_new_completed_report_row(page)
    
    data_str = d_minus_1.strftime('%d-%m-%Y')
    filename = f"05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI. 4.2 BOLETOS RECEBIVEIS - MOOZ BOLETOS {data_str}.csv"
    target_path = get_target_path(d_minus_1, filename)
    
    return download_csv_from_row(page, row, target_path)


def open_overpayment_report_tab(page: Page) -> None:
    """Abre a aba 'Pagamento a maior'."""
    print("Abrindo aba Pagamento a maior...")

    tab_selectors = [
        page.locator('//*[@id="radix-:rjg:-trigger-overpaymentReports"]'),
        page.get_by_role("tab", name=re.compile(r"Pagamento a maior", re.I)),
        page.get_by_text(re.compile(r"Pagamento a maior", re.I)),
        page.locator("[data-state] >> text=Pagamento a maior"),
        page.locator("[id*='overpaymentReports'][id*='trigger']"),
    ]

    for selector in tab_selectors:
        try:
            if selector.first.is_visible(timeout=5_000):
                selector.first.click()
                print("  Aba 'Pagamento a maior' clicada.")
                page.wait_for_timeout(1_000)
                return
        except Exception:
            continue

    raise RuntimeError("Não encontrei a aba 'Pagamento a maior' na página.")


def generate_overpayment_report(page: Page) -> Path:
    d_minus_1 = datetime.now() - timedelta(days=1)

    open_overpayment_report_tab(page)

    select_store_codes(page)

    print(f"Filtrando data D-1 para Pagamento a maior: {d_minus_1.strftime('%d/%m/%Y')}")
    pick_date_range_from_calendar(page, XPATHS["data"], d_minus_1, d_minus_1)

    click_generate_report_button(page)

    row = wait_for_new_completed_report_row(page)
    
    data_str = d_minus_1.strftime('%d-%m-%Y')
    filename = f"Boletos pagos a maior. {data_str}.xls"
    target_path = get_target_path(d_minus_1, filename)
    
    return download_xls_from_row(page, row, target_path)


@log_execution(modulo="Extranet - Relatórios (UDI)")
def main() -> None:
    load_sofi_env()
    url = os.getenv("EXTRANET_URL", "https://extranet.grupoboticario.com.br/")
    user = required_env("EXTRANET_USER")
    password = required_env("EXTRANET_PASSWORD")
    headless = env_bool("HEADLESS", default=False)
    browser_channel = optional_env("BROWSER_CHANNEL", "chrome")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            slow_mo=250,
            channel=browser_channel,
            args=browser_args(),
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
            login(page, url, user, password)
            open_reports_area(page)
            
            downloaded_sales_file = generate_sales_report(page)
            validate_report_not_empty(downloaded_sales_file, "Relatório de Vendas")
            print(f"Relatorio de Vendas concluido. Arquivo baixado: {downloaded_sales_file}")
            
            downloaded_receivables_file = generate_receivables_report(page)
            validate_report_not_empty(downloaded_receivables_file, "Relatório de Recebíveis")
            print(f"Relatorio de Recebiveis concluido. Arquivo baixado: {downloaded_receivables_file}")
            
            downloaded_overpayment_file = generate_overpayment_report(page)
            validate_report_not_empty(downloaded_overpayment_file, "Relatório de Pagamento a Maior")
            print(f"Relatorio de Pagamento a maior concluido. Arquivo baixado: {downloaded_overpayment_file}")
            
        except Exception as exc:
            # Tira screenshot para debug antes de fechar
            try:
                screenshot_path = ROOT / "erro_debug.png"
                page.screenshot(path=str(screenshot_path))
                print(f"Screenshot de erro salvo em: {screenshot_path}")
            except Exception:
                pass
            raise exc
        finally:
            print("Mantendo o navegador aberto por 15 segundos para conferencia visual...")
            try:
                page.wait_for_timeout(15_000)
            except Exception:
                time.sleep(15)
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
