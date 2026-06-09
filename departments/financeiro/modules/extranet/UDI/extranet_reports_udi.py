"""
extranet_reports_udi.py - Geração dos relatórios Extranet para a unidade UDI.

Gera três relatórios das lojas UDI no portal Extranet do Grupo Boticário:
  - Relatório de Vendas (CSV)      - importado para o FinançasGB
  - Relatório de Recebíveis (CSV)  - importado para o FinançasGB
  - Pagamento a Maior (XLS)        - salvo em IMPORTAÇÃO FINANÇAS GB/UDI (NÃO importado)

Ao final, chama o utilitário importar_financas para fazer o upload dos
relatórios de Vendas e Recebíveis no portal FinançasGB.
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

# Carrega o .env global do SOFI + .env.local do departamento
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

from core.database.logger import log_execution

# Importa utilitário de importação para o FinançasGB
from departments.financeiro.modules.importar_financas import upload_para_financas

# ─────────────────────────────────────────────
# Constantes e Configurações
# ─────────────────────────────────────────────

ROOT          = Path(__file__).resolve().parent
DOWNLOADS_DIR = ROOT / "downloads"

UNIDADE     = "UDI"
STORE_CODES = ["23275", "20844", "24417"]

XPATHS = {
    "user":      '//*[@id="signInName"]',
    "password":  '//*[@id="password"]',
    "codigo_cs": '//*[@id="multiple-selection-codigo-da-cs"]',
    "data":      '//*[@id="DateAndStatus"]',
}

MONTH_NAMES_DIR = {
    1: "01 JANEIRO", 2: "02 FEVEREIRO",  3: "03 MARÇO",    4: "04 ABRIL",
    5: "05 MAIO",    6: "06 JUNHO",       7: "07 JULHO",    8: "08 AGOSTO",
    9: "09 SETEMBRO",10: "10 OUTUBRO",   11: "11 NOVEMBRO",12: "12 DEZEMBRO",
}

MONTH_NAMES_PT = {
    1: "Janeiro", 2: "Fevereiro",  3: "Março",    4: "Abril",
    5: "Maio",    6: "Junho",      7: "Julho",    8: "Agosto",
    9: "Setembro",10: "Outubro",  11: "Novembro",12: "Dezembro",
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


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Preencha {name} no arquivo .env antes de executar.")
    return value


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


def by_xpath(page_or_locator: Page | Locator, xpath: str) -> Locator:
    return page_or_locator.locator(f"xpath={xpath}")


# ─────────────────────────────────────────────
# Perguntar data ao usuário
# ─────────────────────────────────────────────

def ask_target_date() -> datetime:
    """Pergunta a data do relatório. ENTER usa D-1."""
    d_minus_1  = datetime.now() - timedelta(days=1)
    default_str = d_minus_1.strftime("%d/%m/%Y")
    while True:
        raw = input(
            f"\nDigite a data do relatório (dd/mm/aaaa) "
            f"ou pressione Enter para usar D-1 [{default_str}]: "
        ).strip()
        if not raw:
            print(f"Usando data padrão D-1: {default_str}")
            return d_minus_1
        try:
            chosen = datetime.strptime(raw, "%d/%m/%Y")
            print(f"Data escolhida: {chosen.strftime('%d/%m/%Y')}")
            return chosen
        except ValueError:
            print("Formato inválido! Use dd/mm/aaaa (ex: 03/05/2026).")


# ─────────────────────────────────────────────
# Caminhos de arquivo
# ─────────────────────────────────────────────

def get_target_path(target_date: datetime, filename: str) -> Path:
    """Caminho para relatórios de Vendas, Recebíveis e Pagamento a Maior (IMPORTAÇÃO FINANÇAS GB/UDI)."""
    base_dir  = Path(r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI")
    target_dir = base_dir / str(target_date.year) / MONTH_NAMES_DIR[target_date.month] / f"{target_date.day:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / filename


# ─────────────────────────────────────────────
# Validação de relatório
# ─────────────────────────────────────────────

def validate_report_not_empty(file_path: Path, report_name: str) -> None:
    """Verifica se o relatório baixado não está em branco."""
    if not file_path.exists():
        raise RuntimeError(f"⚠ ERRO: Arquivo '{report_name}' não foi encontrado em: {file_path}")
    file_size = file_path.stat().st_size
    if file_size == 0:
        file_path.unlink()
        raise RuntimeError(f"⚠ RELATÓRIO EM BRANCO: '{report_name}' está vazio (0 bytes). Arquivo descartado.")
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        lines   = [l for l in content.splitlines() if l.strip()]
        if len(lines) <= 1:
            file_path.unlink()
            raise RuntimeError(
                f"⚠ RELATÓRIO EM BRANCO: '{report_name}' contém apenas cabeçalho. Arquivo descartado."
            )
    except Exception:
        if file_size < 100:
            file_path.unlink()
            raise RuntimeError(f"⚠ RELATÓRIO EM BRANCO: '{report_name}' parece vazio ({file_size} bytes).")
    print(f"  ✔ Relatório '{report_name}' validado ({file_size} bytes).")


# ─────────────────────────────────────────────
# Navegação no Calendário
# ─────────────────────────────────────────────

def _is_month_visible(page: Page, target_month: int, target_year: int) -> bool:
    """Verifica se o mês alvo está visível no calendário aberto (Ant Design)."""
    month_pt = MONTH_NAMES_PT[target_month]
    month_abbr = month_pt[:3]  # Versão abreviada de 3 letras (ex: Jan, Fev, Mar, ..., Jun)
    
    # 1. Tenta buscar pelo texto direto usando regex flexível (com nome por extenso ou abreviação de 3 letras, sem \b rígidos)
    try:
        pattern = rf"({month_pt}|{month_abbr}).*?{target_year}"
        target_regex = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        if page.get_by_text(target_regex).first.is_visible(timeout=500):
            return True
    except Exception:
        pass
        
    # 2. Tenta inspecionar o inner_text dos cabeçalhos dos painéis de calendário (Ant Design)
    try:
        headers = page.locator(".ant-picker-header, .ant-picker-header-view, .calendar-header, .ant-calendar-header, [class*='header-view']")
        for idx in range(headers.count()):
            try:
                h = headers.nth(idx)
                if h.is_visible(timeout=200):
                    h_text = h.inner_text(timeout=200).lower()
                    if (month_pt.lower() in h_text or month_abbr.lower() in h_text) and str(target_year) in h_text:
                        return True
            except Exception:
                continue
    except Exception:
        pass
        
    return False


def _navigate_to_month(page: Page, target_month: int, target_year: int) -> None:
    """Navega o calendário até o mês/ano desejado usando a seta de voltar."""
    month_pt = MONTH_NAMES_PT[target_month]
    max_nav = 24
    for nav_attempt in range(max_nav):
        if _is_month_visible(page, target_month, target_year):
            print(f"  Mês '{month_pt} {target_year}' encontrado no calendário.")
            return

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
            f"Não consegui navegar até o mês {month_pt} {target_year} no calendário "
            f"após {max_nav} tentativas."
        )


def _click_day_in_calendar(page: Page, day: int, label: str) -> None:
    day_str = str(day)
    
    # Identifica o contêiner correto se houver múltiplos painéis de meses lado a lado
    container = page
    try:
        panels = page.locator(".ant-picker-panel, table, .ant-picker-content, .calendar-table, [class*='calendar-grid'], .ant-calendar-content")
        visible_panels = []
        for idx in range(panels.count()):
            p = panels.nth(idx)
            if p.is_visible(timeout=500):
                visible_panels.append(p)
                
        if len(visible_panels) >= 2:
            if "inicial" in label.lower():
                container = visible_panels[0]
                print(f"  [Calendário] Restringindo busca de dia '{day_str}' ao painel esquerdo (inicial).")
            else:
                container = visible_panels[1]
                print(f"  [Calendário] Restringindo busca de dia '{day_str}' ao painel direito (final).")
    except Exception as e:
        print(f"  [Aviso] Erro ao identificar painéis do calendário: {e}. Buscando na página inteira...")

    # Realiza a busca do dia dentro do contêiner selecionado
    for day_btns in [
        container.get_by_role("gridcell", name=day_str, exact=True),
        container.get_by_role("button",   name=day_str, exact=True),
        container.locator(f"button:text-is('{day_str}')"),
        container.locator(f"td:text-is('{day_str}')"),
        container.locator(f"div:text-is('{day_str}')"),
    ]:
        if day_btns.count() == 0:
            continue
        for i in range(day_btns.count()):
            btn = day_btns.nth(i)
            try:
                if not btn.is_visible() or not btn.is_enabled():
                    continue
                
                # Obtém a classe do elemento atual e também do pai (ex: td) para identificar 'out-of-view'
                classes = btn.get_attribute("class") or ""
                parent_classes = ""
                try:
                    parent = btn.locator("xpath=..")
                    if parent.count() > 0:
                        parent_classes = parent.first.get_attribute("class") or ""
                except Exception:
                    pass
                
                all_classes = (classes + " " + parent_classes).lower()
                aria_disabled = btn.get_attribute("aria-disabled") or "false"
                
                # Rejeita se for dia de fora do mês ou desabilitado
                if (
                    "outside" in all_classes 
                    or "out-of-view" in all_classes 
                    or "disabled" in all_classes 
                    or aria_disabled == "true"
                ):
                    continue
                
                btn.click()
                print(f"  Dia {day} clicado ({label}).")
                return
            except Exception:
                continue
                
    # Fallback no documento inteiro se não achou no contêiner
    if container != page:
        print("  [Fallback] Dia não encontrado no contêiner específico. Tentando na página inteira...")
        for day_btns in [
            page.get_by_role("gridcell", name=day_str, exact=True),
            page.get_by_role("button",   name=day_str, exact=True),
            page.locator(f"button:text-is('{day_str}')"),
            page.locator(f"td:text-is('{day_str}')"),
            page.locator(f"div:text-is('{day_str}')"),
        ]:
            if day_btns.count() == 0:
                continue
            for i in range(day_btns.count()):
                btn = day_btns.nth(i)
                try:
                    if not btn.is_visible() or not btn.is_enabled():
                        continue
                        
                    classes = btn.get_attribute("class") or ""
                    parent_classes = ""
                    try:
                        parent = btn.locator("xpath=..")
                        if parent.count() > 0:
                            parent_classes = parent.first.get_attribute("class") or ""
                    except Exception:
                        pass
                    
                    all_classes = (classes + " " + parent_classes).lower()
                    aria_disabled = btn.get_attribute("aria-disabled") or "false"
                    
                    if (
                        "outside" in all_classes 
                        or "out-of-view" in all_classes 
                        or "disabled" in all_classes 
                        or aria_disabled == "true"
                    ):
                        continue
                    
                    btn.click()
                    print(f"  Dia {day} clicado ({label} via fallback geral).")
                    return
                except Exception:
                    continue
                    
    # Fallback final
    print(f"  Aviso: fallback geral para dia {day} ({label}).")
    page.get_by_text(day_str, exact=True).first.click()


def pick_date_range_from_calendar(
    page: Page, xpath: str, start_date: datetime, end_date: datetime
) -> None:
    """Seleciona um intervalo de datas no calendário visual do portal."""
    print(
        f"  Abrindo calendário para selecionar intervalo: "
        f"{start_date.strftime('%d/%m/%Y')} ate {end_date.strftime('%d/%m/%Y')}..."
    )
    field = by_xpath(page, xpath)
    field.wait_for(state="visible", timeout=20_000)
    field.click()
    page.wait_for_timeout(1_500)

    calendar_opened = False
    for month_name in MONTH_NAMES_PT.values():
        try:
            if page.get_by_text(re.compile(f"{month_name} \\d{{4}}")).first.is_visible(timeout=2_000):
                calendar_opened = True
                break
        except Exception:
            continue
    if not calendar_opened:
        field.click()
        page.wait_for_timeout(2_000)

    _navigate_to_month(page, start_date.month, start_date.year)
    _click_day_in_calendar(page, start_date.day, "data inicial")
    page.wait_for_timeout(800)

    if (end_date.year, end_date.month) != (start_date.year, start_date.month):
        _navigate_to_month(page, end_date.month, end_date.year)

    _click_day_in_calendar(page, end_date.day, "data final")
    page.wait_for_timeout(500)


# ─────────────────────────────────────────────
# Navegação e Login na Extranet
# ─────────────────────────────────────────────

def is_browser_error_page(page: Page) -> bool:
    try:
        text = f"{page.title()}\n{page.locator('body').inner_text(timeout=2_000)}"
    except Exception:
        text = ""
    return any(m in text for m in ["Não é possível acessar", "This site can't be reached", "ERR_"])


def safe_goto(page: Page, url: str, retries: int = 3) -> None:
    for attempt in range(1, retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            if not is_browser_error_page(page):
                return
        except Exception as exc:
            print(f"  Erro na navegação (tentativa {attempt}): {exc}")
        time.sleep(5)
    page.goto(url, wait_until="commit", timeout=60_000)


def is_logged_in(page: Page) -> bool:
    return "extranet.grupoboticario.com.br" in page.url and "login." not in page.url


def wait_for_portal_after_login(page: Page, url: str) -> None:
    print("Login enviado. Aguardando redirecionamento do portal...")
    start = time.time()
    while time.time() - start < 90:
        if is_logged_in(page):
            break
        if is_browser_error_page(page):
            safe_goto(page, url)
            time.sleep(3)
            continue
        page.wait_for_timeout(2_000)
    else:
        safe_goto(page, url)
        page.wait_for_timeout(5_000)
    page.get_by_text("Financeiro", exact=True).first.wait_for(state="visible", timeout=120_000)


def login(page: Page, url: str, user: str, password: str) -> None:
    print("Abrindo extranet...")
    safe_goto(page, url)
    by_xpath(page, XPATHS["user"]).wait_for(state="visible", timeout=60_000)
    by_xpath(page, XPATHS["user"]).fill(user)
    by_xpath(page, XPATHS["password"]).fill(password)
    print("Credenciais preenchidas. Aguardando 10 segundos...")
    time.sleep(10)
    page.keyboard.press("Enter")
    wait_for_portal_after_login(page, url)


def _tratar_popup_avaliacao(page: Page) -> None:
    """Verifica se há um popup de avaliação (Maze) em Shadow DOM na tela e fecha se houver."""
    try:
        print("  Verificando se ha popup de avaliacao (Maze) na tela...")

        def _popup_visivel() -> bool:
            try:
                return page.locator("#maze-contextual-widget-host").first.is_visible(timeout=300)
            except Exception:
                return False

        for attempt in range(8):
            if not _popup_visivel():
                print("  [Popup] Nenhum popup de avaliacao detectado.")
                return

            print(f"  [Popup] Host do popup Maze detectado (tentativa {attempt+1}). Tentando fechar...")

            # Estratégia 1: JS avancado — busca recursiva em shadow DOMs aninhados
            fechou = page.evaluate("""() => {
                function findAllShadowRoots(root, found) {
                    found = found || [];
                    var all = root.querySelectorAll('*');
                    for (var i = 0; i < all.length; i++) {
                        if (all[i].shadowRoot) {
                            found.push(all[i].shadowRoot);
                            findAllShadowRoots(all[i].shadowRoot, found);
                        }
                    }
                    return found;
                }

                function clickEl(el) {
                    try {
                        el.click();
                        el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, composed: true }));
                        el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, composed: true }));
                        return true;
                    } catch(e) { return false; }
                }

                function findAndClickClose(root) {
                    // 1. Busca por aria-label comum de fechar
                    var ariaClose = root.querySelector('[aria-label*="close" i], [aria-label*="fechar" i], [aria-label*="dismiss" i], [aria-label="×"], [aria-label="✕"]');
                    if (ariaClose) { clickEl(ariaClose); return 'aria:' + (ariaClose.getAttribute('aria-label') || ''); }

                    // 2. Busca por classe de close
                    var classClose = root.querySelector('[class*="close" i], [class*="Close"], [class*="dismiss" i], [class*="skip" i]');
                    if (classClose) { clickEl(classClose); return 'class:' + (classClose.className || '').slice(0, 40); }

                    // 3. Busca botao/espan com texto "fechar", "×", "skip", etc
                    var all = root.querySelectorAll('button, [role="button"], span, a, div[tabindex], [onclick]');
                    for (var i = 0; i < all.length; i++) {
                        var el = all[i];
                        var txt = (el.textContent || '').replace(/\\s+/g, ' ').trim();
                        var aria = (el.getAttribute('aria-label') || '');
                        if (txt === '×' || txt === '✕' || txt === 'x' || txt === 'X') { clickEl(el); return 'text:x'; }
                        if (/^(close|fechar|dismiss|skip|pular|no thanks|não obrigad|dispensar)$/i.test(txt)) { clickEl(el); return 'text:' + txt; }
                        if (/close|fechar|dismiss|skip|pular/i.test(aria)) { clickEl(el); return 'aria:' + aria; }
                    }

                    // 4. Busca botoes: tenta clicar o que contem SVG (icone X) ou o ultimo
                    var buttons = root.querySelectorAll('button');
                    for (var i = buttons.length - 1; i >= 0; i--) {
                        var btn = buttons[i];
                        if (btn.querySelector('svg') || btn.querySelector('i') || btn.querySelector('img')) {
                            clickEl(btn);
                            return 'svg_button';
                        }
                    }
                    if (buttons.length > 0) { clickEl(buttons[buttons.length - 1]); return 'last_button'; }

                    return null;
                }

                // Busca em todos os shadow DOMs a partir do host
                var host = document.querySelector('#maze-contextual-widget-host');
                if (!host) return 'no_host';

                // Tenta no shadowRoot do host primeiro
                if (host.shadowRoot) {
                    var reason = findAndClickClose(host.shadowRoot);
                    if (reason) return 'host_sr:' + reason;
                }

                // Busca em shadow DOMs aninhados dentro do host
                var nested = findAllShadowRoots(host);
                for (var i = 0; i < nested.length; i++) {
                    var reason = findAndClickClose(nested[i]);
                    if (reason) return 'nested_sr:' + reason;
                }

                return 'no_close_found';
            }""")

            print(f"  [Popup JS] Resultado: {fechou}")
            page.wait_for_timeout(1500)

            if not _popup_visivel():
                print("  [Popup] Popup fechado com sucesso (verificado).")
                return

            # Estratégia 2: Playwright CSS com piercing de shadow DOM
            try:
                for sel in [
                    "#maze-contextual-widget-host >>> [aria-label*='close' i]",
                    "#maze-contextual-widget-host >>> [aria-label*='fechar' i]",
                    "#maze-contextual-widget-host >>> [class*='close' i]",
                    "#maze-contextual-widget-host >>> button:last-of-type",
                    "#maze-contextual-widget-host >>> span[class*='close' i]",
                ]:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=800):
                            btn.click(force=True)
                            page.wait_for_timeout(1500)
                            if not _popup_visivel():
                                print(f"  [Popup] Fechado via CSS: {sel}")
                                return
                    except Exception:
                        continue
            except Exception:
                pass

            # Estratégia 3 (nuclear): Remove o elemento host do DOM
            page.evaluate("""() => {
                document.querySelectorAll('#maze-contextual-widget-host, #maze-media-host, iframe[id*="maze"], [id*="maze"][class*="widget"]').forEach(function(el) {
                    el.remove();
                });
                document.documentElement.style.overflow = 'auto';
                document.body.style.overflow = 'auto';
            }""")
            print("  [Popup] Host Maze removido do DOM (estratégia nuclear).")
            page.wait_for_timeout(1500)

            if not _popup_visivel():
                print("  [Popup] Popup removido com sucesso.")
                return

            page.wait_for_timeout(1000)

        print("  [Popup] Aviso: nao foi possivel fechar/remover o popup apos multiplas tentativas.")
    except Exception as e:
        print(f"  [Popup] Erro ao tratar popup de avaliacao: {e}")


def open_reports_area(page: Page) -> None:
    print("Abrindo menu Financeiro > Relatórios...")
    page.get_by_text("Financeiro", exact=True).first.click()
    page.wait_for_timeout(1_500)
    relatorios = page.get_by_text("Relatórios", exact=True)
    try:
        if relatorios.count() == 0 or not relatorios.first.is_visible():
            portal_credito = page.get_by_text("Portal de gestão de crédito")
            if portal_credito.count() > 0 and portal_credito.first.is_visible():
                portal_credito.first.click()
                page.wait_for_timeout(1_500)
    except Exception:
        pass
    relatorios.first.wait_for(state="visible", timeout=10_000)
    relatorios.first.click()
    page.wait_for_timeout(2_000)
    try:
        page.wait_for_url(lambda u: "relatorios" in u.lower(), timeout=15_000)
    except PlaywrightTimeoutError:
        pass
    
    # Trata o popup de avaliação
    _tratar_popup_avaliacao(page)
    
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    try:
        page.locator("main").first.click(position={"x": 500, "y": 300})
    except Exception:
        pass
    page.wait_for_timeout(500)


def select_store_codes(page: Page) -> None:
    print(f"Selecionando códigos das lojas UDI: {STORE_CODES}")
    cs_field = by_xpath(page, XPATHS["codigo_cs"])
    cs_field.wait_for(state="visible", timeout=20_000)
    cs_field.click()
    page.wait_for_timeout(1_000)
    for code in STORE_CODES:
        clicked = False
        for exact_match in [True, False]:
            options = page.get_by_text(code, exact=exact_match)
            try:
                if exact_match:
                    options.first.wait_for(state="visible", timeout=5_000)
                for i in range(options.count()):
                    opt = options.nth(i)
                    if not opt.is_visible():
                        continue
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
            print(f"  Aviso: não consegui clicar na loja {code}")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def wait_for_new_completed_report_row(page: Page, timeout_ms: int = 180_000) -> Locator:
    print("Aguardando nova linha com selo 'Novo' e status 'Concluído'...")
    deadline = datetime.now().timestamp() + timeout_ms / 1000
    while datetime.now().timestamp() < deadline:
        rows = page.locator("table tbody tr")
        for index in range(rows.count()):
            row        = rows.nth(index)
            normalized = " ".join(row.inner_text(timeout=2_000).split())
            if (
                re.search(r"\bNovo\b", normalized, re.I)
                and re.search(r"Conclu[ií]do", normalized, re.I)
                and all(c in normalized for c in STORE_CODES)
            ):
                print(f"  Linha encontrada: {normalized[:80]}...")
                return row
        page.wait_for_timeout(3_000)
    raise TimeoutError("Linha concluída não apareceu no prazo.")


def download_csv_from_row(page: Page, row: Locator, target_path: Path) -> Path:
    csv_button = row.locator("td").nth(4).locator("button").first
    if csv_button.count() == 0:
        csv_button = row.locator("button").first
    with page.expect_download(timeout=60_000) as dl_info:
        csv_button.click()
    dl_info.value.save_as(target_path)
    print(f"  Download salvo em: {target_path}")
    return target_path


def download_xls_from_row(page: Page, row: Locator, target_path: Path) -> Path:
    xls_button = row.locator("td").nth(4).locator("button").nth(1)
    if xls_button.count() == 0:
        xls_button = row.locator("button").last
    with page.expect_download(timeout=60_000) as dl_info:
        xls_button.click()
    dl_info.value.save_as(target_path)
    print(f"  Download salvo em: {target_path}")
    return target_path


# ─────────────────────────────────────────────
# Geração de relatórios
# ─────────────────────────────────────────────

def _open_tab(page: Page, tab_patterns: list, tab_name: str) -> None:
    for selector in tab_patterns:
        try:
            if selector.first.is_visible(timeout=5_000):
                selector.first.click()
                print(f"  Aba '{tab_name}' clicada.")
                page.wait_for_timeout(1_000)
                return
        except Exception:
            continue
    raise RuntimeError(f"Não encontrei a aba '{tab_name}'.")


def _click_generate_button(page: Page) -> None:
    _tratar_popup_avaliacao(page)
    for selector in [
        page.get_by_role("button", name=re.compile(r"Gerar", re.I)),
        page.get_by_text(re.compile(r"Gerar\s+relat[oó]rio", re.I)),
        page.locator("button:has-text('Gerar')"),
        page.locator("[id*='salesReports'] button").last,
    ]:
        try:
            if selector.first.is_visible(timeout=5_000):
                selector.first.click()
                print("  Botão 'Gerar relatório' clicado.")
                return
        except Exception:
            continue
    raise RuntimeError("Não encontrei o botão 'Gerar relatório'.")


def generate_sales_report(page: Page, target_date: datetime, dias: int = 5) -> Path:
    print("\n--- Gerando Relatório de Vendas (UDI) ---")
    d_minus_N = target_date - timedelta(days=dias - 1)
    _open_tab(page, [
        page.get_by_role("tab", name=re.compile(r"Relat[oó]rio de Vendas", re.I)),
        page.get_by_text(re.compile(r"Relat[oó]rio de Vendas", re.I)),
        page.locator("[id*='salesReports'][id*='trigger']"),
    ], "Relatório de Vendas")
    select_store_codes(page)
    print(f"  Periodo: {d_minus_N.strftime('%d/%m/%Y')} - {target_date.strftime('%d/%m/%Y')}")
    pick_date_range_from_calendar(page, XPATHS["data"], d_minus_N, target_date)
    _click_generate_button(page)
    row      = wait_for_new_completed_report_row(page)
    data_str = target_date.strftime("%d-%m-%Y")
    filename = f"05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI. 4.1 BOLETOS VENDAS - MOOZ BOLETOS .{data_str}.csv"
    return download_csv_from_row(page, row, get_target_path(target_date, filename))


def generate_receivables_report(page: Page, target_date: datetime, dias: int = 5) -> Path:
    print("\n--- Gerando Relatório de Recebíveis (UDI) ---")
    d_minus_N = target_date - timedelta(days=dias - 1)
    _open_tab(page, [
        page.locator('//*[@id="radix-:rjg:-trigger-financialTransfersReports"]'),
        page.get_by_role("tab", name=re.compile(r"Relat[oó]rio de Receb[ií]veis", re.I)),
        page.get_by_text(re.compile(r"Relat[oó]rio de Receb[ií]veis", re.I)),
        page.locator("[id*='financialTransfersReports'][id*='trigger']"),
    ], "Relatório de Recebíveis")
    select_store_codes(page)
    print(f"  Periodo: {d_minus_N.strftime('%d/%m/%Y')} - {target_date.strftime('%d/%m/%Y')}")
    pick_date_range_from_calendar(page, XPATHS["data"], d_minus_N, target_date)
    _click_generate_button(page)
    row      = wait_for_new_completed_report_row(page)
    data_str = target_date.strftime("%d-%m-%Y")
    filename = f"05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI. 4.2 BOLETOS RECEBIVEIS - MOOZ BOLETOS {data_str}.csv"
    return download_csv_from_row(page, row, get_target_path(target_date, filename))


def generate_overpayment_report(page: Page, target_date: datetime) -> Path:
    print("\n--- Gerando Relatório de Pagamento a Maior (UDI) ---")
    _open_tab(page, [
        page.locator('//*[@id="radix-:rjg:-trigger-overpaymentReports"]'),
        page.get_by_role("tab", name=re.compile(r"Pagamento a maior", re.I)),
        page.get_by_text(re.compile(r"Pagamento a maior", re.I)),
        page.locator("[id*='overpaymentReports'][id*='trigger']"),
    ], "Pagamento a Maior")
    select_store_codes(page)
    pick_date_range_from_calendar(page, XPATHS["data"], target_date, target_date)
    _click_generate_button(page)
    row      = wait_for_new_completed_report_row(page)
    data_str = target_date.strftime("%d-%m-%Y")
    filename = f"Boletos pagos a maior. {data_str}.xls"
    # Mesmo caminho geral IMPORTAÇÃO FINANÇAS GB\UDI, mas NÃO é importado para o portal
    return download_xls_from_row(page, row, get_target_path(target_date, filename))


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

import argparse

# ─────────────────────────────────────────────
# Exit codes (usados pelo scheduler para decidir sobre retry)
# ─────────────────────────────────────────────
EXIT_OK        = 0  # execução concluída com sucesso
EXIT_RETRYABLE = 1  # falha transitória (Playwright, rede) → scheduler fará retry
EXIT_PERMANENT = 2  # falha permanente (dados vazios)     → scheduler NÃO fará retry

def parse_args():
    parser = argparse.ArgumentParser(description="Extração Extranet UDI")
    parser.add_argument("--data", type=str, default=None, help="Data de referência (DD/MM/AAAA)")
    parser.add_argument("--dias", type=int, default=5, help="Quantidade de dias do período")
    return parser.parse_args()

@log_execution(modulo="Extranet UDI")
def main() -> None:
    args = parse_args()
    
    if args.data:
        try:
            target_date = datetime.strptime(args.data, "%d/%m/%Y")
            print(f"Data recebida via CLI: {target_date.strftime('%d/%m/%Y')}")
        except ValueError:
            print("Formato de data inválido recebido via CLI. Perguntando interativamente...")
            target_date = ask_target_date()
    else:
        target_date = ask_target_date()

    dias_intervalo = args.dias
    print(f"Período configurado via CLI: {dias_intervalo} dia(s)")

    url             = os.getenv("EXTRANET_URL", "https://extranet.grupoboticario.com.br/")
    user            = required_env("EXTRANET_USER")
    password        = required_env("EXTRANET_PASSWORD")
    headless        = env_bool("HEADLESS", default=False)
    browser_channel = optional_env("BROWSER_CHANNEL", "chrome")

    arquivos_para_importar: list[Path] = []

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
            login(page, url, user, password)
            open_reports_area(page)

            # Relatório de Vendas → para importação
            vendas = generate_sales_report(page, target_date, dias=dias_intervalo)
            validate_report_not_empty(vendas, "Relatório de Vendas")
            print(f"  Vendas concluído: {vendas.name}")
            arquivos_para_importar.append(vendas)

            # Relatório de Recebíveis → para importação
            recebiveis = generate_receivables_report(page, target_date, dias=dias_intervalo)
            validate_report_not_empty(recebiveis, "Relatório de Recebíveis")
            print(f"  Recebíveis concluído: {recebiveis.name}")
            arquivos_para_importar.append(recebiveis)

            # Pagamento a Maior → NÃO é importado para o FinançasGB
            overpayment = generate_overpayment_report(page, target_date)
            validate_report_not_empty(overpayment, "Pagamento a Maior")
            print(f"  Pagamento a Maior concluído: {overpayment.name}")
            print("  (Pagamento a Maior salvo em IMPORTAÇÃO FINANÇAS GB\\UDI — não importado para o FinançasGB)")

        except Exception as exc:
            try:
                page.screenshot(path=str(ROOT / "erro_debug.png"))
            except Exception:
                pass
            raise exc
        finally:
            print("\nMantendo o navegador aberto por 15 segundos para conferência visual...")
            try:
                page.wait_for_timeout(15_000)
            except Exception:
                time.sleep(15)
            context.close()
            browser.close()

    # Importação para o FinançasGB (após fechar o Playwright)
    if arquivos_para_importar:
        print("\n--- Iniciando importação para o FinançasGB... ---")
        upload_para_financas(arquivos=arquivos_para_importar, unidade=UNIDADE)
    else:
        print("\n[AVISO] Nenhum arquivo gerado — importação ignorada.")


if __name__ == "__main__":
    try:
        main()
        sys.exit(EXIT_OK)
    except RuntimeError as e:
        msg = str(e).upper()
        if "EM BRANCO" in msg or "VAZIO" in msg:
            sys.exit(EXIT_PERMANENT)
        sys.exit(EXIT_RETRYABLE)
    except Exception:
        sys.exit(EXIT_RETRYABLE)
