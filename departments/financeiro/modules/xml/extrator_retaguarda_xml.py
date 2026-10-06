# -*- coding: utf-8 -*-
"""
extrator_retaguarda_xml.py — Extração automatizada do Relatório Base de Notas Fiscais de Entrada (Cálamo)
via Playwright no Portal Retaguarda do Grupo Boticário.

Fluxo:
1. Faz login no portal Retaguarda com credenciais do .env.
2. Navega para Compra -> Nota fiscal entrada.
3. No iframe legadoFrame:
   - Adiciona lojas de BH e UDI (BH LOJAS, BH VD, UDI LOJAS, UDI VD).
   - Adiciona filtro de fornecedor 'calamo' e marca todos.
   - Aplica intervalo de datas de Segunda-feira a Domingo da semana corrente.
   - Seleciona formato XLS e gera o relatório.
4. Salva o arquivo baixado no diretório configurado (rede ou fallback local).

Uso via CLI:
    python extrator_retaguarda_xml.py
    python extrator_retaguarda_xml.py --data-inicio 17/08/2026 --data-fim 23/08/2026
    python extrator_retaguarda_xml.py --headless
"""

from __future__ import annotations

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

# ─────────────────────────────────────────────
# Configuração de Ambiente e Raiz do SOFI-core
# ─────────────────────────────────────────────
_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
from core.database.logger import log_execution

load_sofi_env(department="financeiro")

# ─────────────────────────────────────────────
# Constantes & Configurações
# ─────────────────────────────────────────────
DIRETORIO_ATUAL = Path(__file__).resolve().parent

RETAGUARDA_URL  = os.getenv("RETAGUARDA_URL", "https://cp10488.retaguarda.grupoboticario.com.br/")
RETAGUARDA_USER = os.getenv("RETAGUARDA_USER", "")
RETAGUARDA_PASS = os.getenv("RETAGUARDA_PASS", "")

# Pastas de saída
PASTA_REDE_PLANILHAS = Path(r"T:\13-Publica\XMLS CÁLAMO\PLANILHAS_RETAGUARDA")
PASTA_LOCAL_PLANILHAS = DIRETORIO_ATUAL / "downloads_retaguarda"

HOLDINGS_LOJAS = ["BH LOJAS", "BH VD", "UDI LOJAS", "UDI VD"]

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


def calcular_periodo_semana_corrente(data_base: datetime | None = None) -> tuple[str, str, datetime, datetime]:
    """
    Calcula as datas de início (Segunda-feira) e término (Domingo) da semana referente.
    
    Returns:
        tuple[str, str, datetime, datetime]:
            (data_inicio_str, data_fim_str, data_inicio_obj, data_fim_obj) no formato 'DD/MM/YYYY'
    """
    if data_base is None:
        data_base = datetime.now()
    
    # Segunda-feira da semana corrente
    segunda = data_base - timedelta(days=data_base.weekday())
    # Domingo da semana corrente
    domingo = segunda + timedelta(days=6)
    
    return (
        segunda.strftime("%d/%m/%Y"),
        domingo.strftime("%d/%m/%Y"),
        segunda,
        domingo
    )


def obter_pasta_destino() -> Path:
    """Retorna a pasta de destino para a planilha baixada (prioriza rede T:, fallback local)."""
    if PASTA_REDE_PLANILHAS.exists():
        return PASTA_REDE_PLANILHAS
    PASTA_LOCAL_PLANILHAS.mkdir(parents=True, exist_ok=True)
    return PASTA_LOCAL_PLANILHAS


def browser_args() -> list[str]:
    args = [
        "--disable-quic",
        "--ignore-certificate-errors",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if os.getenv("DISABLE_HTTP2", "true").lower() in ("1", "true", "yes", "sim"):
        args.append("--disable-http2")
    return args


def wait_click(locator, timeout: int = 15_000, delay_after: float = 1.5):
    """Aguarda o elemento estar visível e habilitado, clica e aguarda estabilização."""
    locator.wait_for(state="visible", timeout=timeout)
    locator.scroll_into_view_if_needed()
    locator.click()
    time.sleep(delay_after)


def fazer_login(page: Page, max_tentativas: int = 3) -> None:
    """Efetua login no portal Retaguarda com retry robusto.
    
    O portal usa reCAPTCHA v3 que gera um token unico por carregamento de pagina.
    Quando o login falha ('Nao autorizado'), e necessario recarregar a pagina
    inteira para que o reCAPTCHA gere um novo token valido.
    """
    url_login = RETAGUARDA_URL
    if not url_login.endswith("/app/#/login") and "#" not in url_login:
        url_login = f"{url_login.rstrip('/')}/app/#/login"

    for tentativa in range(1, max_tentativas + 1):
        print(f"[RETAGUARDA] Tentativa de login {tentativa}/{max_tentativas}...")
        print(f"[RETAGUARDA] Acessando URL: {url_login}")
        page.goto(url_login, wait_until="networkidle", timeout=60_000)

        # Espera progressiva para carregamento do reCAPTCHA v3
        wait_secs = 15 + (tentativa - 1) * 5
        print(f"[RETAGUARDA] Aguardando {wait_secs}s para inicializacao dos scripts de autenticacao (reCAPTCHA)...")
        page.wait_for_timeout(wait_secs * 1_000)

        try:
            user_input = page.get_by_role("textbox", name="Usuário")
            user_input.wait_for(state="visible", timeout=15_000)

            print("[RETAGUARDA] Preenchendo credenciais...")
            user_input.fill("")
            page.get_by_role("textbox", name="Senha").fill("")
            page.wait_for_timeout(500)
            user_input.fill(RETAGUARDA_USER)
            page.wait_for_timeout(500)
            page.get_by_role("textbox", name="Senha").fill(RETAGUARDA_PASS)
            page.wait_for_timeout(1_000)

            btn_entrar = page.get_by_role("button", name="Entrar")
            btn_entrar.wait_for(state="visible", timeout=10_000)
            btn_entrar.click()
            print("[RETAGUARDA] Botao Entrar acionado. Aguardando estabilizacao do portal...")
            page.wait_for_timeout(5_000)
        except Exception as e:
            print(f"[RETAGUARDA] Tela de login nao encontrada ou ja autenticado: {e}")

        # Verificar se o login foi bem-sucedido (procura menu lateral ou URL sem /login)
        if "login" not in page.url.lower():
            print("[RETAGUARDA] Login realizado com sucesso!")
            page.wait_for_timeout(3_000)
            return

        # Checar se tem conteudo de dashboard carregado
        try:
            page.locator("div.sidemenu, div[class*='sidemenu']").first.wait_for(state="visible", timeout=10_000)
            print("[RETAGUARDA] Login realizado com sucesso!")
            page.wait_for_timeout(3_000)
            return
        except Exception:
            pass

        print(f"[RETAGUARDA] Login nao confirmado na tentativa {tentativa}.")
        if tentativa < max_tentativas:
            print(f"[RETAGUARDA] Aguardando 5s antes de recarregar para nova tentativa...")
            page.wait_for_timeout(5_000)
        else:
            print("[RETAGUARDA] Todas as tentativas falharam. Prosseguindo mesmo assim...")
            page.wait_for_timeout(3_000)


def navegar_para_nota_fiscal_entrada(page: Page) -> None:
    """Navega pelo menu até o módulo de Nota Fiscal Entrada aguardando transições do menu."""
    print("[RETAGUARDA] Navegando para o módulo 'Compra' -> 'Nota fiscal entrada'...")
    
    # 1. Menu lateral Compra
    try:
        menu_compra = page.locator("div").filter(has_text="Compra").nth(5)
        menu_compra.wait_for(state="visible", timeout=20_000)
        menu_compra.click()
    except Exception:
        page.locator('//div[contains(text(), "Compra")]').first.click()

    page.wait_for_timeout(2_000)
    
    # 2. Submenu item de Nota fiscal
    try:
        submenu_item = page.locator("#sidemenu-item-107 > .flora-sidemenu-submenu__item-label > .flora-sidemenu-submenu__item-label-content")
        submenu_item.wait_for(state="visible", timeout=10_000)
        submenu_item.click()
    except Exception:
        page.locator('//span[contains(text(), "Nota fiscal")]').first.click()

    page.wait_for_timeout(2_000)
    
    # 3. Link Nota fiscal entrada
    link_entrada = page.get_by_role("link", name="Nota fiscal entrada")
    link_entrada.wait_for(state="visible", timeout=15_000)
    link_entrada.click()
    print("[RETAGUARDA] Tela 'Nota fiscal entrada' acionada. Aguardando carregamento do iframe...")
    page.wait_for_timeout(4_000)


def obter_frame_legado(page: Page):
    """Aguarda e retorna a instância real de Frame do legadoFrame."""
    print("[RETAGUARDA] Localizando iframe legadoFrame...")
    page.wait_for_selector("#legadoFrame, iframe[name='legadoFrame']", state="attached", timeout=30_000)
    page.wait_for_timeout(3_000)

    frame = page.frame(name="legadoFrame")
    if frame is None:
        for f in page.frames:
            if f != page.main_frame and f.url and "legado" in f.url.lower():
                frame = f
                break
    if frame is None:
        raise RuntimeError("Não foi possível acessar o iframe legadoFrame.")
    
    print("[RETAGUARDA] Iframe legadoFrame carregado e acessível.")
    return frame


def marcar_todos_e_confirmar_popup(frame) -> None:
    """Garante que todos os registros do popup estão selecionados e confirma."""
    frame.wait_for_timeout(1_500)

    # 1. Verifica e marca o checkbox 'Marcar Todos' se ainda não estiver marcado
    try:
        frame.evaluate("""() => {
            var cb = document.getElementById('marcaTodosPopupPesquisa');
            if (cb && !cb.checked) {
                cb.click();
            }
        }""")
    except Exception as e:
        print(f"[RETAGUARDA] Detalhe JS marcar todos: {e}")

    frame.wait_for_timeout(1_000)

    # 2. Clica no botão de confirmação (tenta o botão verde de concluir do jqGrid ou o botão Confirmar)
    confirmado = False
    for seletor in [
        "#botaoConcluirSelecaoPopupPesquisa",
        "#btnConcluirSelecaoPopupPesquisa",
        "button:has-text('Confirmar')",
        "button:has-text(' Confirmar')",
        "a.btn-confirmar",
        ".ui-dialog-buttonpane button:first-child",
        "//button[contains(text(), 'Confirmar')]",
        "//a[contains(@id, 'Concluir') or contains(@id, 'Confirmar')]"
    ]:
        try:
            btn = frame.locator(seletor).first
            if btn.is_visible():
                btn.click()
                confirmado = True
                print(f"[RETAGUARDA] Popup confirmado via seletor: {seletor}")
                break
        except Exception:
            continue

    if not confirmado:
        # Tenta clique direto via get_by_role
        try:
            frame.get_by_role("button", name=" Confirmar").click()
            confirmado = True
        except Exception:
            try:
                frame.get_by_role("button", name="Confirmar").click()
                confirmado = True
            except Exception:
                pass

    frame.wait_for_timeout(2_000)


def selecionar_lojas(frame) -> None:
    """Adiciona e seleciona todos os grupos de lojas (BH LOJAS, BH VD, UDI LOJAS, UDI VD)."""
    print("[RETAGUARDA] Aplicando filtros de Loja...")
    
    filtro_loja = frame.locator("#filtros").get_by_text("Loja")
    if filtro_loja.is_visible():
        filtro_loja.click()
    frame.wait_for_timeout(2_000)

    for holding in HOLDINGS_LOJAS:
        print(f"[RETAGUARDA] Adicionando holding: {holding}...")
        btn_adicionar = frame.get_by_role("link", description="Adicionar", exact=True)
        btn_adicionar.wait_for(state="visible", timeout=15_000)
        btn_adicionar.click()
        frame.wait_for_timeout(2_000)

        # Seleciona holding no select2 / dropdown
        try:
            dropdown = frame.get_by_role("textbox", name="[Selecione]")
            dropdown.wait_for(state="visible", timeout=10_000)
            dropdown.click()
            frame.wait_for_timeout(1_000)

            opcao = frame.get_by_role("option", name=holding)
            opcao.wait_for(state="visible", timeout=10_000)
            opcao.click()
        except Exception:
            # Fallback via select2 ou XPath
            frame.locator("//span[contains(@class, 'select2-selection')]").click()
            frame.wait_for_timeout(500)
            frame.locator(f"//li[contains(text(), '{holding}')]").click()

        frame.wait_for_timeout(1_000)

        # Pesquisar
        btn_pesquisar = frame.get_by_role("button", name="Pesquisar")
        btn_pesquisar.wait_for(state="visible", timeout=10_000)
        btn_pesquisar.click()
        frame.wait_for_timeout(3_000)

        # Marca todos e confirma o popup
        marcar_todos_e_confirmar_popup(frame)

    print("[RETAGUARDA] Todos os filtros de loja foram configurados com sucesso.")


def selecionar_fornecedor_calamo(frame) -> None:
    """Aplica o filtro do fornecedor Cálamo."""
    print("[RETAGUARDA] Aplicando filtro de Fornecedor (Cálamo)...")
    
    filtro_fornecedor = frame.locator("#filtros").get_by_text("Fornecedor")
    filtro_fornecedor.wait_for(state="visible", timeout=15_000)
    filtro_fornecedor.click()
    frame.wait_for_timeout(2_000)

    btn_adicionar = frame.get_by_role("link", description="Adicionar", exact=True)
    btn_adicionar.wait_for(state="visible", timeout=15_000)
    btn_adicionar.click()
    frame.wait_for_timeout(2_000)

    campo_nome = frame.locator("input[name=\"filtro.nome\"]")
    campo_nome.wait_for(state="visible", timeout=10_000)
    campo_nome.click()
    campo_nome.fill("calamo")
    frame.wait_for_timeout(1_000)

    btn_pesquisar = frame.get_by_role("button", name="Pesquisar")
    btn_pesquisar.wait_for(state="visible", timeout=10_000)
    btn_pesquisar.click()
    frame.wait_for_timeout(3_000)

    marcar_todos_e_confirmar_popup(frame)
    print("[RETAGUARDA] Fornecedor Cálamo selecionado com sucesso.")


def preencher_datas(frame, data_inicio: str, data_fim: str, data_ini_obj: datetime, data_fim_obj: datetime) -> None:
    """Preenche o intervalo de datas de emissão (Segunda a Domingo) no formulário de Nota Fiscal de Entrada."""
    print(f"[RETAGUARDA] Configurando período de emissão: {data_inicio} até {data_fim}...")
    
    # Preenchimento direto via IDs exatos dos campos de emissão (deixando entrada vazio)
    try:
        frame.evaluate(f"""([dtIni, dtFim]) => {{
            var elemEmissaoIni = document.getElementById('periodo_emissao_inicio');
            var elemEmissaoFim = document.getElementById('periodo_emissao_termino');
            var elemEntradaIni = document.getElementById('periodo_entrada_inicio');
            var elemEntradaFim = document.getElementById('periodo_entrada_termino');

            // Limpa os campos de período de entrada (não devem ser preenchidos)
            if (elemEntradaIni) {{
                elemEntradaIni.value = '';
                elemEntradaIni.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            if (elemEntradaFim) {{
                elemEntradaFim.value = '';
                elemEntradaFim.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            // Preenche APENAS os campos de período de emissão
            if (elemEmissaoIni) {{
                elemEmissaoIni.value = dtIni;
                elemEmissaoIni.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            if (elemEmissaoFim) {{
                elemEmissaoFim.value = dtFim;
                elemEmissaoFim.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            // Atualização complementar via jQuery datepicker se ativo
            if (typeof $ !== 'undefined' && $.fn) {{
                if (elemEntradaIni) $('#periodo_entrada_inicio').val('');
                if (elemEntradaFim) $('#periodo_entrada_termino').val('');
                if (elemEmissaoIni && $.fn.datepicker) $('#periodo_emissao_inicio').datepicker('setDate', dtIni);
                if (elemEmissaoFim && $.fn.datepicker) $('#periodo_emissao_termino').datepicker('setDate', dtFim);
            }}
        }}""", [data_inicio, data_fim])
    except Exception as e:
        print(f"[RETAGUARDA] Aviso na configuração de datas: {e}")

    frame.wait_for_timeout(1_500)


def exportar_relatorio(page: Page, frame, pasta_destino: Path, prefixo_saida: str = "relatorioSinteticoDeNotasFiscaisCompra") -> Path:
    """Marca formato XLS, clica em Gerar e aguarda o download do arquivo."""
    print("[RETAGUARDA] Selecionando formato XLS...")
    radio_xls = frame.get_by_role("radio", name="XLS")
    radio_xls.wait_for(state="visible", timeout=15_000)
    radio_xls.check()
    frame.wait_for_timeout(2_000)

    print("[RETAGUARDA] Acionando 'Gerar' e aguardando processamento e download...")
    btn_gerar = frame.get_by_role("button", name="Gerar")
    btn_gerar.wait_for(state="visible", timeout=15_000)

    with page.expect_download(timeout=180_000) as download_info:
        btn_gerar.click()

    download = download_info.value
    nome_original = download.suggested_filename
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extensao = Path(nome_original).suffix or ".xls"
    nome_final = f"{prefixo_saida}_{timestamp}{extensao}"
    
    pasta_destino.mkdir(parents=True, exist_ok=True)
    caminho_final = pasta_destino / nome_final
    download.save_as(str(caminho_final))
    
    print(f"[RETAGUARDA] Download concluído com sucesso: {caminho_final}")
    return caminho_final


@log_execution(modulo="XML (Extrator Retaguarda)")
def executar_extracao(
    data_inicio: str | None = None,
    data_fim: str | None = None,
    headless: bool = False
) -> Path | None:
    """
    Função principal que executa toda a extração automatizada de notas fiscais de entrada.
    
    Args:
        data_inicio: Data inicial 'DD/MM/YYYY' (se None, usa Segunda-feira da semana atual)
        data_fim: Data final 'DD/MM/YYYY' (se None, usa Domingo da semana atual)
        headless: Executar navegador em modo headless (padrão False)
        
    Returns:
        Path do arquivo baixado ou None em caso de falha.
    """
    if not RETAGUARDA_USER or not RETAGUARDA_PASS:
        raise ValueError("Credenciais RETAGUARDA_USER e/ou RETAGUARDA_PASS não encontradas no .env")

    if not data_inicio or not data_fim:
        dt_ini_str, dt_fim_str, dt_ini_obj, dt_fim_obj = calcular_periodo_semana_corrente()
    else:
        dt_ini_str, dt_fim_str = data_inicio, data_fim
        dt_ini_obj = datetime.strptime(dt_ini_str, "%d/%m/%Y")
        dt_fim_obj = datetime.strptime(dt_fim_str, "%d/%m/%Y")

    print("=" * 70)
    print(f"  EXTRAÇÃO RELATÓRIO RETAGUARDA — XML ENTRADA")
    print(f"  Período de Emissão: {dt_ini_str} até {dt_fim_str} (Segunda a Domingo)")
    print(f"  Modo Headless: {headless}")
    print("=" * 70)

    pasta_destino = obter_pasta_destino()
    print(f"[RETAGUARDA] Destino dos arquivos: {pasta_destino}")

    with sync_playwright() as playwright:
        channel = os.getenv("BROWSER_CHANNEL", "chrome")
        launch_kwargs = {
            "headless": headless,
            "args": browser_args(),
        }
        try:
            browser = playwright.chromium.launch(channel=channel, **launch_kwargs)
        except Exception:
            browser = playwright.chromium.launch(**launch_kwargs)

        context = browser.new_context(
            user_agent=REALISTIC_USER_AGENT,
            viewport={"width": 1440, "height": 900},
            accept_downloads=True
        )
        context.add_init_script(STEALTH_INIT_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(30_000)

        try:
            # 1. Login
            fazer_login(page)

            # 2. Navegação
            navegar_para_nota_fiscal_entrada(page)

            # 3. Obter frame real (legadoFrame)
            frame = obter_frame_legado(page)

            # 4. Seleção de Lojas
            selecionar_lojas(frame)

            # 5. Seleção de Fornecedor
            selecionar_fornecedor_calamo(frame)

            # 6. Preenchimento de Datas
            preencher_datas(frame, dt_ini_str, dt_fim_str, dt_ini_obj, dt_fim_obj)

            # 7. Exportação e Download
            caminho_arquivo = exportar_relatorio(page, frame, pasta_destino)

            return caminho_arquivo

        except Exception as e:
            print(f"[RETAGUARDA] ERRO durante o processo de extração: {e}")
            try:
                debug_img = DIRETORIO_ATUAL / "erro_extracao_retaguarda.png"
                page.screenshot(path=str(debug_img), full_page=True)
                print(f"[RETAGUARDA] Screenshot do erro salva em: {debug_img}")
            except Exception:
                pass
            raise e

        finally:
            context.close()
            browser.close()


# Exit status codes para integração com o Scheduler SOFI
EXIT_OK = 0
EXIT_RETRYABLE = 1
EXIT_PERMANENT = 2
EXIT_SEM_FATURAMENTO = 3


def processar_pipeline_completo(caminho_planilha: Path) -> int:
    """
    Lê as chaves da planilha extraída do Retaguarda.
    - Se houver novas notas faturadas: baixa os XMLs via MeuDanfe e dispara a geração dos relatórios finais. Retorna 0 (EXIT_OK).
    - Se não houver notas faturadas (planilha vazia / sem chaves): remove a planilha temporária e encerra. Retorna 3 (EXIT_SEM_FATURAMENTO).
    - Em caso de erro: retorna 1 (EXIT_RETRYABLE) ou 2 (EXIT_PERMANENT).
    """
    print("\n" + "=" * 70)
    print("  VERIFICAÇÃO DE NOVAS NOTAS FISCAIS FATURADAS")
    print("=" * 70)

    if not caminho_planilha or not caminho_planilha.exists():
        print("[XML Pipeline] Arquivo de planilha não encontrado para validação.")
        return EXIT_RETRYABLE

    try:
        from debug_meudanfe import ler_chaves_planilha, executar_download_chaves
        from gerador_relatorio import gerar_relatorio_calamo
    except ImportError as err:
        print(f"[XML Pipeline] Erro ao importar módulos de XML: {err}")
        return EXIT_RETRYABLE

    chaves = ler_chaves_planilha(str(caminho_planilha))
    if not chaves:
        print("[XML Pipeline] Nenhuma nova nota fiscal faturada encontrada no período.")
        print("[XML Pipeline] Excluindo planilha temporária para evitar arquivos vazios...")
        try:
            os.remove(caminho_planilha)
            print(f"[XML Pipeline] Arquivo temporário removido: {caminho_planilha.name}")
        except Exception as e:
            print(f"[XML Pipeline] Erro ao remover planilha temporária: {e}")
        print("[XML Pipeline] Processo finalizado com SUCESSO (sem novas notas para processar no período).")
        return EXIT_SEM_FATURAMENTO

    print(f"[XML Pipeline] {len(chaves)} nota(s) faturada(s) identificada(s) na planilha!")
    print("[XML Pipeline] Disparando busca e download de XMLs via API MeuDanfe...")

    total_chaves, xmls_baixados = executar_download_chaves(
        caminho_planilha=str(caminho_planilha),
        gerar_relatorio_ao_final=False
    )

    if xmls_baixados > 0:
        print(f"[XML Pipeline] {xmls_baixados} XML(s) baixado(s) com sucesso!")
        print("[XML Pipeline] Disparando geração dos relatórios finais da Cálamo e organização por PDV...")
        total_validas = gerar_relatorio_calamo()
        if total_validas == 0:
            print("[XML Pipeline] Todos os XMLs baixados foram ignorados por não possuírem vencimento (ex: devoluções).")
            print("[XML Pipeline] Retornando status SEM FATURAMENTO.")
            return EXIT_SEM_FATURAMENTO
        print("[XML Pipeline] Pipeline completo concluído com SUCESSO!")
        return EXIT_OK
    else:
        print(f"[XML Pipeline] Aviso: Nenhum XML pôde ser baixado pela API MeuDanfe para as {len(chaves)} chaves encontradas.")
        return EXIT_RETRYABLE


def main():
    parser = argparse.ArgumentParser(description="Automação Retaguarda — Relatório de Notas Fiscais de Entrada (XMLs Cálamo)")
    parser.add_argument("--data-inicio", type=str, help="Data inicial (DD/MM/YYYY)")
    parser.add_argument("--data-fim", type=str, help="Data final (DD/MM/YYYY)")
    parser.add_argument("--data", type=str, help="Data de referência (DD/MM/YYYY) para calcular a semana")
    parser.add_argument("--dias", type=int, default=0, help="Dias retroativos (compatibilidade com scheduler)")
    parser.add_argument("--headless", action="store_true", help="Executar em modo headless")
    parser.add_argument("--apenas-extrair", action="store_true", help="Apenas extrai a planilha do portal sem disparar MeuDanfe/relatórios")

    args = parser.parse_args()

    headless_env = os.getenv("HEADLESS", "false").lower() in ("1", "true", "yes", "sim")
    headless_final = args.headless or headless_env

    dt_ini = args.data_inicio
    dt_fim = args.data_fim

    # Se recebeu --data do scheduler, calcula a semana a partir dessa data de referência
    if not dt_ini and not dt_fim and args.data:
        try:
            data_ref = datetime.strptime(args.data, "%d/%m/%Y")
            dt_ini, dt_fim, _, _ = calcular_periodo_semana_corrente(data_ref)
        except ValueError:
            print(f"[AVISO] Formato de --data inválido ({args.data}). Usando data atual.")

    try:
        arquivo_gerado = executar_extracao(
            data_inicio=dt_ini,
            data_fim=dt_fim,
            headless=headless_final
        )
        if arquivo_gerado and arquivo_gerado.exists():
            print(f"\n[RETAGUARDA] Planilha gerada em: {arquivo_gerado}")
            if not args.apenas_extrair:
                res_code = processar_pipeline_completo(arquivo_gerado)
                sys.exit(res_code)
            else:
                print("[AVISO] Parâmetro --apenas-extrair ativo. Etapa de XMLs/relatórios não executada.")
                sys.exit(EXIT_OK)
        else:
            print("\n[AVISO] Processo de extração concluído, mas o arquivo de saída não foi localizado.")
            sys.exit(EXIT_PERMANENT)
    except Exception as exc:
        print(f"\n[FALHA] Falha na execução da extração: {exc}")
        sys.exit(EXIT_RETRYABLE)


if __name__ == "__main__":
    main()

