"""
Automação Playwright - Extração de Relatório MAR
Portal Extranet Grupo Boticário

Este script realiza a extração automatizada do relatório de reposição
do MAR (Módulo de Abastecimento e Reposição) no portal do Grupo Boticário.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ─── Configurações ────────────────────────────────────────────────────────────

# Diretório do projeto (onde o script/EXE está)
if getattr(sys, 'frozen', False):
    DIRETORIO_PROJETO = Path(sys.executable).resolve().parent
else:
    DIRETORIO_PROJETO = Path(__file__).resolve().parent

# Pasta para salvar os downloads
PASTA_DOWNLOADS = DIRETORIO_PROJETO / "downloads"
PASTA_DOWNLOADS.mkdir(exist_ok=True)

# URL do portal
URL_PORTAL = "https://extranet.grupoboticario.com.br/home"

# Timeout padrão em milissegundos (60 segundos)
XPATHS = {
    "user": '//*[@id="signInName"]',
    "password": '//*[@id="password"]',
}

REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['pt-BR', 'pt', 'en-US', 'en'],
});
"""

TIMEOUT_PADRAO = 60_000

# Timeout para espera do download ser processado (5 minutos)
TIMEOUT_DOWNLOAD = 300_000


# ─── Funções auxiliares ───────────────────────────────────────────────────────

def log(mensagem: str) -> None:
    """Imprime mensagem com timestamp."""
    agora = datetime.now().strftime("%H:%M:%S")
    print(f"[{agora}] {mensagem}")


def carregar_credenciais() -> tuple[str, str]:
    """Carrega as credenciais do arquivo .env"""
    load_dotenv(DIRETORIO_PROJETO / ".env")

    usuario = os.getenv("USUARIO")
    senha = os.getenv("SENHA")

    if not usuario or not senha:
        print("=" * 60)
        print("ERRO: Credenciais não encontradas!")
        print("Edite o arquivo .env na pasta do projeto com:")
        print("  USUARIO=seu_usuario")
        print("  SENHA=sua_senha")
        print("=" * 60)
        sys.exit(1)

    return usuario, senha


# ─── Fluxo principal ─────────────────────────────────────────────────────────

def carregar_headless() -> bool:
    """Carrega a configuracao de navegador visivel/headless do .env."""
    valor = os.getenv("HEADLESS", "false").strip().lower()
    return valor in {"1", "true", "yes", "y", "sim", "s"}


def carregar_delay_antes_login() -> float:
    """Carrega a pausa antes de clicar em Entrar."""
    valor = os.getenv("DELAY_ANTES_LOGIN_SEGUNDOS", "3").strip()
    try:
        return max(0, float(valor.replace(",", ".")))
    except ValueError:
        log(
            "DELAY_ANTES_LOGIN_SEGUNDOS invalido no .env. "
            "Usando pausa padrao de 3 segundos."
        )
        return 3


def carregar_browser_channel() -> str | None:
    """Carrega o canal do navegador, como msedge ou chrome."""
    valor = os.getenv("BROWSER_CHANNEL", "chrome").strip()
    return valor or None


def carregar_desabilitar_http2() -> bool:
    """Carrega a opcao de desabilitar HTTP/2/QUIC no Chromium."""
    valor = os.getenv("DESABILITAR_HTTP2", "true").strip().lower()
    return valor in {"1", "true", "yes", "y", "sim", "s"}


def carregar_viewport() -> dict[str, int]:
    """Carrega o tamanho da janela do navegador."""
    largura = os.getenv("VIEWPORT_LARGURA", "1366").strip()
    altura = os.getenv("VIEWPORT_ALTURA", "768").strip()
    try:
        return {"width": int(largura), "height": int(altura)}
    except ValueError:
        log("VIEWPORT invalido no .env. Usando 1366x768.")
        return {"width": 1366, "height": 768}


def browser_args() -> list[str]:
    args = [
        "--disable-quic",
        "--ignore-certificate-errors",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    if carregar_desabilitar_http2():
        args.append("--disable-http2")

    return args


def by_xpath(page_or_locator, xpath: str):
    return page_or_locator.locator(f"xpath={xpath}")


def clicar_primeiro_visivel(locators, descricao: str, timeout: int = 30_000) -> None:
    """Clica no primeiro locator visivel de uma lista."""
    deadline = time.time() + (timeout / 1000)
    last_error = None

    while time.time() < deadline:
        for locator in locators:
            try:
                count = min(locator.count(), 10)
            except Exception:
                count = 1

            for index in range(count):
                item = locator.nth(index)
                try:
                    if item.is_visible(timeout=700):
                        item.scroll_into_view_if_needed(timeout=3_000)
                        item.click(timeout=5_000)
                        return
                except Exception as exc:
                    last_error = exc

        time.sleep(0.5)

    raise RuntimeError(f"Nao consegui clicar em {descricao}. Ultimo erro: {last_error}")


def pagina_erro_chromium(page) -> bool:
    """Detecta a tela de erro nativa do Chromium."""
    try:
        texto = page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        return False

    return any(
        trecho in texto
        for trecho in (
            "não é possível acessar esse site",
            "nao e possivel acessar esse site",
            "this site can't be reached",
            "err_",
        )
    )


def is_browser_error_page(page) -> bool:
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
        "NÃ£o Ã© possÃ­vel acessar esse site",
        "This site can't be reached",
        "ERR_",
    ]
    text = f"{title}\n{body_text}"
    return any(marker in text for marker in error_markers)


def safe_goto(page, url: str, retries: int = 3) -> None:
    """Navega para a URL com retry em caso de erro HTTP2 ou crash."""
    for attempt in range(1, retries + 1):
        try:
            log(f"Navegando para {url} (tentativa {attempt}/{retries})...")
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_PADRAO)
            if not is_browser_error_page(page):
                return
            log(f"Pagina de erro detectada na tentativa {attempt}. Esperando antes de tentar de novo...")
        except Exception as exc:
            log(f"Erro na navegacao (tentativa {attempt}): {exc}")
        time.sleep(5)

    page.goto(url, wait_until="commit", timeout=TIMEOUT_PADRAO)


def is_logged_in(page) -> bool:
    """Verifica se a pagina ja esta na area logada da extranet."""
    current = page.url
    return "extranet.grupoboticario.com.br" in current and "login." not in current


def wait_for_portal_after_login(page, url: str) -> None:
    log("Login enviado. Aguardando redirecionamento do portal...")

    max_wait = 90
    start = time.time()
    while time.time() - start < max_wait:
        current = page.url

        if is_logged_in(page):
            log(f"Login completado! URL: {current}")
            break

        if is_browser_error_page(page):
            log("Pagina de erro detectada. Forcando navegacao para a URL principal...")
            safe_goto(page, url)
            time.sleep(3)
            continue

        page.wait_for_timeout(2_000)
    else:
        log(f"Login nao redirecionou em {max_wait}s. Tentando navegar direto...")
        safe_goto(page, url)
        page.wait_for_timeout(5_000)

    log(f"URL final depois do login: {page.url}")
    log("Aguardando app principal carregar...")
    page.locator("#root").wait_for(state="attached", timeout=120_000)
    page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_PADRAO)
    page.wait_for_timeout(5_000)
    log("App principal carregado.")


def login(page, url: str, user: str, password: str, delay_antes_login: float) -> None:
    log("Abrindo extranet...")
    safe_goto(page, url)

    by_xpath(page, XPATHS["user"]).wait_for(state="visible", timeout=60_000)
    by_xpath(page, XPATHS["user"]).fill(user)
    by_xpath(page, XPATHS["password"]).fill(password)
    log(f"Credenciais preenchidas. Aguardando {delay_antes_login:g}s antes de enviar o login...")
    time.sleep(delay_antes_login)
    page.keyboard.press("Enter")
    wait_for_portal_after_login(page, url)


def aguardar_pagina_principal(page) -> None:
    """Aguarda o portal abrir apos o login e recupera callback com erro."""
    for tentativa in range(1, 4):
        try:
            page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_PADRAO)
        except PlaywrightTimeoutError:
            log("Timeout aguardando carregamento apos login.")

        page.wait_for_timeout(5000)
        log(f"URL atual apos login: {page.url}")

        menu_lateral = page.locator('//*[@id="root"]/div/div[2]/div[1]/aside')
        try:
            menu_lateral.wait_for(state="visible", timeout=10000)
            return
        except PlaywrightTimeoutError:
            pass

        if pagina_erro_chromium(page):
            screenshot_path = DIRETORIO_PROJETO / f"erro_callback_tentativa_{tentativa}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            log(f"Tela de erro do navegador detectada. Screenshot salvo em: {screenshot_path}")

            log("Tentando retomar a sessao abrindo a home do portal...")
            try:
                page.goto(URL_PORTAL, wait_until="domcontentloaded", timeout=TIMEOUT_PADRAO)
            except Exception as e:
                log(f"Falha ao reabrir a home do portal: {e}")
                page.wait_for_timeout(5000)
            continue

        log(f"Menu principal ainda nao apareceu. Tentativa {tentativa}/3.")
        page.goto(URL_PORTAL, wait_until="domcontentloaded", timeout=TIMEOUT_PADRAO)

    raise RuntimeError(
        "Portal nao carregou apos o login. Verifique VPN/rede corporativa/proxy "
        "e o ultimo screenshot erro_callback_tentativa_*.png."
    )


def executar_extracao():
    """Executa o fluxo completo de extração do relatório MAR."""

    usuario, senha = carregar_credenciais()
    headless = carregar_headless()
    delay_antes_login = carregar_delay_antes_login()
    browser_channel = carregar_browser_channel()
    viewport = carregar_viewport()
    log("Credenciais carregadas com sucesso.")
    log(f"Navegador em modo {'headless' if headless else 'visivel para debug'}.")
    log(f"Viewport configurado: {viewport['width']}x{viewport['height']}.")
    if browser_channel:
        log(f"Usando navegador: {browser_channel}.")

    with sync_playwright() as p:
        # Inicia o navegador (headed para acompanhamento visual)
        launch_options = {
            "headless": headless,
            "slow_mo": 250,
            "args": browser_args(),
        }
        launch_options["args"].append(f"--window-size={viewport['width']},{viewport['height']}")
        if browser_channel:
            launch_options["channel"] = browser_channel

        try:
            browser = p.chromium.launch(**launch_options)
        except Exception as e:
            if not browser_channel:
                raise

            log(f"Nao foi possivel abrir '{browser_channel}': {e}")
            log("Tentando abrir o Chromium instalado pelo Playwright...")
            launch_options.pop("channel", None)
            browser = p.chromium.launch(**launch_options)
        context = browser.new_context(
            accept_downloads=True,
            ignore_https_errors=True,
            user_agent=REALISTIC_USER_AGENT,
            viewport=viewport,
            locale="pt-BR",
        )
        page = context.new_page()
        page.add_init_script(STEALTH_INIT_SCRIPT)
        page.set_default_timeout(TIMEOUT_PADRAO)

        try:
            # ── 1. Acessa o portal ────────────────────────────────────────
            login(page, URL_PORTAL, usuario, senha, delay_antes_login)

            # ── 2. Faz login ──────────────────────────────────────────────
            
            

            # Aguarda a página principal carregar
            log("Aguardando página principal carregar...")
            log("Página principal carregada.")

            # ── 3. Abre o menu "Pedidos, abastecimento e estoque" ─────────
            log("Clicando em 'Pedidos, abastecimento e estoque'...")
            clicar_primeiro_visivel(
                [
                    page.get_by_text("Pedidos, abastecimento e estoque", exact=True),
                    page.locator("text=Pedidos, abastecimento e estoque"),
                    page.locator('//*[@id="root"]/div/div[2]/div[1]/aside/div/div[7]/div'),
                    page.locator('//*[@id="root"]/div/div[2]/div[1]/aside/div/div[2]/div/div[7]/div'),
                ],
                "Pedidos, abastecimento e estoque",
            )
            page.wait_for_timeout(2000)
            log("Menu lateral aberto.")

            # ── 4. Clica em "MAR" (na seção Opções) ──────────────────────
            log("Clicando em 'MAR'...")
            # Tenta localizar o link MAR na seção de Opções
            # Primeiro tenta por texto exato na seção de opções
            mar_link = page.locator("text=MAR").nth(1)  # O segundo "MAR" é o da seção Opções
            clicar_primeiro_visivel(
                [
                    page.get_by_text("MAR", exact=True),
                    page.locator("a:has-text('MAR')"),
                    page.locator("button:has-text('MAR')"),
                    page.locator("[role='menuitem']:has-text('MAR')"),
                    page.locator("text=MAR"),
                ],
                "MAR",
            )
            log("MAR selecionado.")

            # Aguarda a página do MAR carregar
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
            except PlaywrightTimeoutError:
                log("Pagina MAR ainda possui requisicoes ativas; seguindo apos espera visual.")
            page.wait_for_timeout(3000)
            log("Página MAR carregada.")

            # ── 5. Clica em "Pedidos" ─────────────────────────────────────
            log("Clicando em 'Pedidos'...")
            pedidos_btn = page.locator('//*[@id="radix-:r6k:"]')
            # Se o XPath exato não funcionar, tenta por texto
            try:
                pedidos_btn.wait_for(state="visible", timeout=10000)
                pedidos_btn.click()
            except PlaywrightTimeoutError:
                log("XPath exato não encontrado, tentando por texto...")
                pedidos_btn = page.get_by_text("Pedidos", exact=True).first
                pedidos_btn.wait_for(state="visible")
                pedidos_btn.click()
            page.wait_for_timeout(2000)
            log("Menu Pedidos aberto.")

            # ── 6. Clica em "Reposição" ───────────────────────────────────
            log("Clicando em 'Reposição'...")
            reposicao_btn = page.locator('//*[@id="radix-:r8j:"]/ul')
            try:
                reposicao_btn.wait_for(state="visible", timeout=10000)
                reposicao_btn.click()
            except PlaywrightTimeoutError:
                log("XPath exato não encontrado, tentando por texto...")
                reposicao_btn = page.get_by_text("Reposição", exact=True).first
                reposicao_btn.wait_for(state="visible")
                reposicao_btn.click()

            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            log("Página de Reposição carregada.")

            # ── 7. Seleciona PDVs ─────────────────────────────────────────
            log("Clicando em 'Selecione ou cole os PDVs'...")
            pdv_dropdown = page.locator('//*[@id="store-dropdown-button"]')
            pdv_dropdown.wait_for(state="visible")
            pdv_dropdown.click()
            page.wait_for_timeout(1500)

            # Marca checkbox "Lojas"
            log("Marcando checkbox 'Lojas'...")
            lojas_checkbox = page.locator(
                '//*[@id="radix-:raq:"]/span[1]/div/div/label/span'
            )
            try:
                lojas_checkbox.wait_for(state="visible", timeout=10000)
                lojas_checkbox.click()
            except PlaywrightTimeoutError:
                log("XPath exato de Lojas não encontrado, tentando alternativa...")
                page.get_by_text("Lojas", exact=True).first.click()
            page.wait_for_timeout(500)

            # Marca checkbox "Vendas Direta"
            log("Marcando checkbox 'Vendas Direta'...")
            vd_checkbox = page.locator(
                '//*[@id="radix-:ras:"]/span[1]/div/div/label/span'
            )
            try:
                vd_checkbox.wait_for(state="visible", timeout=10000)
                vd_checkbox.click()
            except PlaywrightTimeoutError:
                log("XPath exato de Vendas Direta não encontrado, tentando alternativa...")
                page.get_by_text("Vendas direta", exact=False).first.click()
            page.wait_for_timeout(1000)
            log("PDVs selecionados (Lojas + Vendas Direta).")

            # ── 7.1. Clica em "Analisar" (dentro do mesmo painel de PDVs) ─
            log("Clicando em 'Analisar'...")
            analisar_btn = page.locator(
                '//*[@id="dropdown-accordion-wrapper"]/div[2]/button/span'
            )
            try:
                analisar_btn.wait_for(state="visible", timeout=10000)
                analisar_btn.click()
            except PlaywrightTimeoutError:
                log("XPath exato de Analisar não encontrado, tentando por texto...")
                page.get_by_text("Analisar", exact=True).first.click()
            page.wait_for_timeout(3000)

            # Aguarda o carregamento da análise
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
            except PlaywrightTimeoutError:
                log("Análise ainda possui requisições ativas; seguindo após espera visual.")
            page.wait_for_timeout(2000)
            log("Análise concluída.")

            # ── 8. Clica em "Exportar" ────────────────────────────────────
            log("Clicando em 'Exportar'...")
            exportar_btn = page.locator(
                '//*[@id="table-wrapper"]/div/div[2]/div[2]/div[1]/button'
            )
            exportar_btn.wait_for(state="visible")
            exportar_btn.click()
            page.wait_for_timeout(2000)
            log("Popup de exportação aberto.")

            # ── 9. Seleciona "Últimos 6 ciclos" ──────────────────────────
            log("Selecionando informações para exportar...")
            seletor_info = page.locator('//*[@id="selector-dropdown"]')
            seletor_info.wait_for(state="visible")
            seletor_info.click()
            page.wait_for_timeout(1000)

            # Seleciona "Últimos 6 ciclos"
            log("Marcando 'Últimos 6 ciclos'...")
            ultimos_6 = page.get_by_text("Últimos 6 ciclos", exact=True)
            ultimos_6.wait_for(state="visible")
            ultimos_6.click()
            page.wait_for_timeout(1000)
            log("'Últimos 6 ciclos' selecionado.")

            # ── 10. Seleciona formato XLSX ────────────────────────────────
            log("Selecionando formato do arquivo...")
            seletor_formato = page.locator('//*[@id="selector-dropdown-format"]')
            seletor_formato.wait_for(state="visible")
            seletor_formato.click()
            page.wait_for_timeout(1000)

            # Seleciona "XLSX" (dentro do dropdown de formato já aberto)
            log("Marcando 'XLSX'...")
            try:
                # Busca a opção XLSX dentro do contexto do dropdown de formato
                xlsx_option = seletor_formato.locator("xpath=..").get_by_text("XLSX", exact=True)
                xlsx_option.wait_for(state="visible", timeout=5000)
                xlsx_option.click()
            except (PlaywrightTimeoutError, Exception):
                log("Fallback: tentando localizar XLSX por listbox/option...")
                try:
                    xlsx_option = page.locator("[role='listbox'] >> text=XLSX").first
                    xlsx_option.wait_for(state="visible", timeout=5000)
                    xlsx_option.click()
                except (PlaywrightTimeoutError, Exception):
                    log("Fallback: tentando último elemento visível com texto XLSX...")
                    xlsx_option = page.get_by_text("XLSX", exact=True).last
                    xlsx_option.wait_for(state="visible", timeout=5000)
                    xlsx_option.click()
            page.wait_for_timeout(1000)
            log("Formato XLSX selecionado.")

            # ── 11. Clica em "Exportar" no popup ─────────────────────────
            log("Clicando em 'Exportar' no popup...")
            modal = page.locator('#react-portal-modal-container')
            try:
                # Busca o botão "Exportar" pelo texto dentro do modal
                exportar_popup = modal.get_by_role("button", name="Exportar")
                exportar_popup.wait_for(state="visible", timeout=10000)
                exportar_popup.click()
            except (PlaywrightTimeoutError, Exception):
                log("Fallback: tentando localizar botão Exportar por texto...")
                # Busca todos os botões com texto "Exportar" dentro do modal e clica no último (que é o da ação, não o do cabeçalho)
                exportar_popup = modal.locator("button:has-text('Exportar')").last
                exportar_popup.wait_for(state="visible", timeout=10000)
                exportar_popup.click()
            page.wait_for_timeout(3000)
            log("Exportação solicitada com sucesso.")

            # ── 12. Abre o histórico de downloads ─────────────────────────
            log("Abrindo histórico de downloads...")
            historico_btn = page.locator(
                '//*[@id="table-wrapper"]/div/div[2]/div[2]/div[1]/div/div/button'
            )
            historico_btn.wait_for(state="visible")
            historico_btn.click()
            page.wait_for_timeout(2000)
            log("Histórico de downloads aberto.")

            # ── 13. Aguarda o PRIMEIRO item da lista ficar pronto ─────────
            log("Aguardando processamento do arquivo mais recente...")
            log("(O script monitora o 1° item da lista. Pode levar de 1 a 20 minutos.)")

            TIMEOUT_ESPERA_BOTAO = 20 * 60  # 20 minutos em segundos
            INTERVALO_POLLING = 3           # checa a cada 3 segundos
            CHECAGENS_ESTABILIDADE = 3      # botão deve estar visível N vezes consecutivas
            INTERVALO_ESTABILIDADE = 1      # intervalo entre checagens de estabilidade (s)
            MAX_TENTATIVAS_CLIQUE = 3       # retry caso o clique falhe

            inicio_espera = time.time()
            arquivo_baixado = False

            while not arquivo_baixado:
                tempo_decorrido = time.time() - inicio_espera

                # Verifica timeout geral
                if tempo_decorrido > TIMEOUT_ESPERA_BOTAO:
                    break

                minutos = int(tempo_decorrido // 60)
                segundos = int(tempo_decorrido % 60)

                # Localiza o PRIMEIRO item da lista de downloads (o mais recente)
                # Cada item da lista é um div/row. Precisamos pegar o primeiro e
                # verificar se dentro dele existe "Baixar arquivo" em vez de "Processando".
                primeiro_item = None
                btn_download = None

                try:
                    # Tenta encontrar todas as linhas do histórico de downloads
                    # e pegar apenas a primeira (mais recente)
                    linhas_historico = page.locator("div:has(> span:text('Processando')), div:has(> span:text('Baixar arquivo'))")

                    if linhas_historico.count() > 0:
                        primeiro_item = linhas_historico.first

                        # Verifica se o primeiro item já tem "Baixar arquivo"
                        link_baixar = primeiro_item.locator("text=Baixar arquivo")
                        if link_baixar.count() > 0 and link_baixar.first.is_visible(timeout=500):
                            btn_download = link_baixar.first
                except Exception:
                    pass

                # Se não encontrou pelo método acima, tenta abordagem alternativa
                if btn_download is None:
                    try:
                        # Pega todos os "Baixar arquivo" e todos os "Processando"
                        todos_baixar = page.get_by_text("Baixar arquivo", exact=False)
                        todos_processando = page.get_by_text("Processando", exact=False)

                        count_baixar = todos_baixar.count()
                        count_processando = todos_processando.count()

                        # Se não tem nenhum "Processando", o primeiro "Baixar arquivo" é o nosso
                        if count_processando == 0 and count_baixar > 0:
                            btn_download = todos_baixar.first
                        # Se o primeiro item da lista visual já é "Baixar arquivo"
                        # (verificamos comparando posições Y na tela)
                        elif count_baixar > 0 and count_processando > 0:
                            try:
                                pos_baixar = todos_baixar.first.bounding_box(timeout=500)
                                pos_processando = todos_processando.first.bounding_box(timeout=500)
                                if pos_baixar and pos_processando:
                                    # Se o "Baixar arquivo" está ACIMA do "Processando",
                                    # significa que o item mais recente já está pronto
                                    if pos_baixar["y"] < pos_processando["y"]:
                                        btn_download = todos_baixar.first
                            except Exception:
                                pass
                    except Exception:
                        pass

                if btn_download is None:
                    # Arquivo ainda processando — loga a cada 30s
                    if int(tempo_decorrido) % 30 < INTERVALO_POLLING:
                        log(f"Primeiro item ainda processando... ({minutos}m{segundos:02d}s decorridos)")
                    page.wait_for_timeout(INTERVALO_POLLING * 1000)
                    continue

                # Botão encontrado no primeiro item — verificação de estabilidade
                log(f"'Baixar arquivo' detectado no 1° item após {minutos}m{segundos:02d}s. Verificando estabilidade...")

                estavel = True
                for check in range(CHECAGENS_ESTABILIDADE):
                    page.wait_for_timeout(INTERVALO_ESTABILIDADE * 1000)
                    try:
                        if not btn_download.is_visible(timeout=1000):
                            log(f"Checagem de estabilidade {check + 1}/{CHECAGENS_ESTABILIDADE}: botão sumiu. Voltando a aguardar...")
                            estavel = False
                            break
                    except Exception:
                        log(f"Checagem de estabilidade {check + 1}/{CHECAGENS_ESTABILIDADE}: erro ao verificar. Voltando a aguardar...")
                        estavel = False
                        break
                    log(f"Checagem de estabilidade {check + 1}/{CHECAGENS_ESTABILIDADE}: OK ✓")

                if not estavel:
                    page.wait_for_timeout(INTERVALO_POLLING * 1000)
                    continue

                # Botão estável — tenta clicar com retry
                log("Botão estável confirmado no 1° item. Iniciando download...")

                for tentativa_clique in range(1, MAX_TENTATIVAS_CLIQUE + 1):
                    try:
                        with page.expect_download(timeout=TIMEOUT_DOWNLOAD) as download_info:
                            btn_download.scroll_into_view_if_needed(timeout=3_000)
                            btn_download.click(timeout=5_000)

                        download = download_info.value

                        nome_arquivo = download.suggested_filename
                        if not nome_arquivo:
                            nome_arquivo = f"relatorio_mar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

                        caminho_destino = PASTA_DOWNLOADS / nome_arquivo
                        download.save_as(str(caminho_destino))

                        log(f"Arquivo baixado com sucesso!")
                        log(f"Salvo em: {caminho_destino}")
                        arquivo_baixado = True
                        break

                    except Exception as e:
                        log(f"Tentativa de clique {tentativa_clique}/{MAX_TENTATIVAS_CLIQUE} falhou: {e}")
                        if tentativa_clique < MAX_TENTATIVAS_CLIQUE:
                            log("Aguardando antes de tentar novamente...")
                            page.wait_for_timeout(3000)
                        else:
                            log("Todas as tentativas de clique falharam. Voltando a aguardar o botão...")
                            page.wait_for_timeout(5000)

            if not arquivo_baixado:
                tempo_total = time.time() - inicio_espera
                minutos_total = int(tempo_total // 60)
                log(f"ERRO: Tempo limite de {minutos_total} minutos excedido aguardando o download.")
                log("O arquivo pode ainda estar sendo processado no portal.")
                screenshot_path = DIRETORIO_PROJETO / "erro_timeout_download.png"
                page.screenshot(path=str(screenshot_path), full_page=True)
                log(f"Screenshot salvo em: {screenshot_path}")
                sys.exit(1)

            log("")
            log("=" * 60)
            log("  EXTRAÇÃO CONCLUÍDA COM SUCESSO!")
            log(f"  Arquivo: {caminho_destino}")
            log("=" * 60)

        except PlaywrightTimeoutError as e:
            log(f"ERRO: Timeout - {e}")
            screenshot_path = DIRETORIO_PROJETO / "erro_timeout.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            log(f"Screenshot de erro salvo em: {screenshot_path}")
            sys.exit(1)

        except Exception as e:
            log(f"ERRO inesperado: {e}")
            screenshot_path = DIRETORIO_PROJETO / "erro_geral.png"
            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
                log(f"Screenshot de erro salvo em: {screenshot_path}")
            except Exception:
                pass
            raise

        finally:
            log("Fechando navegador...")
            context.close()
            browser.close()
            log("Navegador fechado.")


# ─── Ponto de entrada ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   Automação - Extração Relatório MAR                    ║")
    print("║   Portal Extranet Grupo Boticário                       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    executar_extracao()
