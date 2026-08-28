"""
extrator_picking.py - Automação para extração de OP Picking via API do Grupo Boticário.

Fluxo:
1. Obtém as notas fiscais e PDVs do relatório final de notas faturadas (.xlsx ou .xls)
   ou parâmetros via linha de comando/interativo.
2. Efetua login no Extranet do Grupo Boticário via Playwright utilizando as credenciais
   centrais do .env.
3. Captura os tokens de autorização (Bearer JWT) e cookies de sessão.
4. Realiza requisições espaçadas (delay >= 5s com jitter) no endpoint:
   https://list-api.prd.demanda-abastecimento.grupoboticario.digital/invoice-number/{n_da_nota}/store/{pdv}
5. Converte as respostas JSON em uma planilha XLSX formatada no padrão exato
   do template op_piking.xlsx (aba 'data', 9 colunas na ordem estrita).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
import requests
import xlrd
from playwright.sync_api import (
    BrowserContext,
    Locator,
    Page,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

# ─────────────────────────────────────────────
# Localização de Raiz e Carregamento de Ambiente
# ─────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parent
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from core.sofi_env import load_sofi_env
    load_sofi_env(department="financeiro")
except Exception as _env_err:
    print(f"[Aviso SOFI Env] {_env_err}")

from core.database.logger import log_execution

# ─────────────────────────────────────────────
# Constantes e Configurações
# ─────────────────────────────────────────────

DIRETORIO_ATUAL = Path(__file__).resolve().parent
CAMINHO_TEMPLATE = DIRETORIO_ATUAL / "op_piking.xlsx"
API_BASE_URL = "https://list-api.prd.demanda-abastecimento.grupoboticario.digital"

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
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
"""

COLUNAS_OP_PIKING = [
    "volume",
    "itemNumber",
    "handlingUnitCode",
    "quantity",
    "batchCode",
    "volumeIdentifier",
    "materialCode",
    "materialDescription",
    "expirationDate",
]

# ─────────────────────────────────────────────
# Funções Utilitárias de Ambiente
# ─────────────────────────────────────────────

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "s"}


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Preencha a variável {name} no arquivo .env antes de executar.")
    return value


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
# 1. Leitura de Notas e PDVs do Relatório Faturado
# ─────────────────────────────────────────────

def encontrar_relatorio_mais_recente() -> Optional[Path]:
    """Procura pelo relatório de notas faturadas mais recente no drive de rede ou pasta local."""
    candidatos: List[Path] = []
    
    # 1. Busca na rede corporativa T:
    pasta_rede = Path(r"T:\05-FIN\XMLS CÁLAMO\RELATÓRIOS COMPLETOS")
    if pasta_rede.exists():
        for ext in ("*.xls", "*.xlsx"):
            candidatos.extend(pasta_rede.rglob(ext))
            
    # 2. Busca local na pasta do módulo
    for ext in ("*.xls", "*.xlsx"):
        for f in DIRETORIO_ATUAL.glob(ext):
            if "op_piking" not in f.name.lower() and not f.name.startswith("~$"):
                candidatos.append(f)
                
    # 3. Busca em subpastas locais
    pasta_local_rel = DIRETORIO_ATUAL / "Relatórios Cálamo"
    if pasta_local_rel.exists():
        for ext in ("*.xls", "*.xlsx"):
            candidatos.extend(pasta_local_rel.rglob(ext))

    # Filtra arquivos temporários do Excel
    candidatos = [c for c in candidatos if not c.name.startswith("~$") and "op_piking" not in c.name.lower()]

    if not candidatos:
        return None

    # Retorna o arquivo mais recentemente modificado
    return max(candidatos, key=lambda f: f.stat().st_mtime)


def extrair_notas_de_planilha(caminho_arquivo: Path | str) -> List[Tuple[str, str]]:
    """
    Lê a planilha de relatório de notas faturadas (.xlsx ou .xls) e extrai
    a lista de pares únicos (nota, pdv).
    """
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de relatório não encontrado: {caminho}")

    pares_encontrados: List[Tuple[str, str]] = []
    pares_vistos = set()

    print(f"Lendo relatório de notas: {caminho.name}...")

    # Formato .XLSX
    if caminho.suffix.lower() == ".xlsx":
        wb = openpyxl.load_workbook(caminho, data_only=True)
        
        # 1. Tenta extrair da aba 'Base' (Coluna A = PDV, Coluna D = Nº DOC)
        if "Base" in wb.sheetnames:
            ws = wb["Base"]
            for r in range(2, ws.max_row + 1):
                pdv_raw = ws.cell(r, 1).value
                ndoc_raw = ws.cell(r, 4).value
                if pdv_raw and ndoc_raw:
                    pdv = str(int(float(pdv_raw))) if isinstance(pdv_raw, (int, float)) else str(pdv_raw).strip()
                    nota = str(int(float(ndoc_raw))) if isinstance(ndoc_raw, (int, float)) else str(ndoc_raw).strip()
                    chave = (nota, pdv)
                    if pdv and nota and chave not in pares_vistos:
                        pares_vistos.add(chave)
                        pares_encontrados.append(chave)
                        
        # 2. Se não achou na 'Base', tenta na aba 'Notas Fiscais'
        if not pares_encontrados and "Notas Fiscais" in wb.sheetnames:
            ws = wb["Notas Fiscais"]
            for r in range(4, ws.max_row + 1):
                ndoc_raw = ws.cell(r, 1).value
                dest_raw = ws.cell(r, 6).value  # Ex: "20843-ALFI-ATT-UDI SHOP"
                if ndoc_raw and dest_raw:
                    nota = str(int(float(ndoc_raw))) if isinstance(ndoc_raw, (int, float)) else str(ndoc_raw).strip()
                    dest_str = str(dest_raw).strip()
                    match_pdv = re.match(r"^(\d+)", dest_str)
                    pdv = match_pdv.group(1) if match_pdv else ""
                    chave = (nota, pdv)
                    if pdv and nota and chave not in pares_vistos:
                        pares_vistos.add(chave)
                        pares_encontrados.append(chave)

    # Formato .XLS
    elif caminho.suffix.lower() == ".xls":
        wb = xlrd.open_workbook(caminho)
        
        # 1. Tenta extrair da aba 'Base'
        if "Base" in wb.sheet_names():
            ws = wb.sheet_by_name("Base")
            for r in range(1, ws.nrows):
                row = ws.row_values(r)
                if len(row) >= 4:
                    pdv_raw = row[0]
                    ndoc_raw = row[3]
                    if pdv_raw and ndoc_raw:
                        pdv = str(int(float(pdv_raw))) if isinstance(pdv_raw, (int, float)) else str(pdv_raw).strip()
                        nota = str(int(float(ndoc_raw))) if isinstance(ndoc_raw, (int, float)) else str(ndoc_raw).strip()
                        chave = (nota, pdv)
                        if pdv and nota and chave not in pares_vistos:
                            pares_vistos.add(chave)
                            pares_encontrados.append(chave)

        # 2. Tenta na aba 'Notas Fiscais'
        if not pares_encontrados and "Notas Fiscais" in wb.sheet_names():
            ws = wb.sheet_by_name("Notas Fiscais")
            for r in range(3, ws.nrows):
                row = ws.row_values(r)
                if len(row) >= 6:
                    ndoc_raw = row[0]
                    dest_raw = row[5]
                    if ndoc_raw and dest_raw:
                        nota = str(int(float(ndoc_raw))) if isinstance(ndoc_raw, (int, float)) else str(ndoc_raw).strip()
                        dest_str = str(dest_raw).strip()
                        match_pdv = re.match(r"^(\d+)", dest_str)
                        pdv = match_pdv.group(1) if match_pdv else ""
                        chave = (nota, pdv)
                        if pdv and nota and chave not in pares_vistos:
                            pares_vistos.add(chave)
                            pares_encontrados.append(chave)

    print(f"Total de pares (Nota, PDV) únicos extraídos: {len(pares_encontrados)}")
    return pares_encontrados


# ─────────────────────────────────────────────
# 2. Autenticação Extranet e Captura de Tokens
# ─────────────────────────────────────────────

def _tratar_popup_avaliacao(page: Page) -> None:
    """Verifica se há popup de avaliação (Maze widget) e fecha se houver."""
    try:
        if page.locator("#maze-contextual-widget-host").first.is_visible(timeout=500):
            page.evaluate("""() => {
                var host = document.querySelector('#maze-contextual-widget-host');
                if (host && host.shadowRoot) {
                    var btn = host.shadowRoot.querySelector('button[aria-label*="close" i], button[aria-label*="fechar" i], [class*="close" i]');
                    if (btn) btn.click();
                }
            }""")
    except Exception:
        pass


def autenticar_extranet_e_obter_sessao() -> Dict[str, Any]:
    """
    Efetua login no Extranet do Boticário e captura tokens de autorização (Bearer)
    e cookies de sessão para comunicação com a API.
    """
    url = os.getenv("EXTRANET_URL", "https://extranet.grupoboticario.com.br/")
    user = required_env("EXTRANET_USER")
    password = required_env("EXTRANET_PASSWORD")
    headless = env_bool("HEADLESS", default=False)
    browser_channel = os.getenv("BROWSER_CHANNEL", "chrome")

    print("\n--- [Extranet] Iniciando autenticação no portal ---")
    
    auth_headers: Dict[str, str] = {
        "User-Agent": REALISTIC_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://extranet.grupoboticario.com.br",
        "Referer": "https://extranet.grupoboticario.com.br/",
    }
    bearer_token: Optional[str] = None
    captured_cookies: List[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            slow_mo=200,
            channel=browser_channel,
            args=browser_args(),
        )
        context: BrowserContext = browser.new_context(
            accept_downloads=True,
            ignore_https_errors=True,
            user_agent=REALISTIC_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )
        page: Page = context.new_page()
        page.add_init_script(STEALTH_INIT_SCRIPT)
        page.set_default_timeout(45_000)

        # Intercepta requisições de rede para capturar tokens JWT enviados nas APIs
        def on_request(req):
            nonlocal bearer_token
            auth_val = req.headers.get("authorization") or req.headers.get("Authorization")
            if auth_val and "bearer " in auth_val.lower():
                token = auth_val.split(" ", 1)[1].strip()
                if token and len(token) > 20 and not bearer_token:
                    bearer_token = token
                    print("  ✔ Token de autorização capturado via tráfego de rede!")

        page.on("request", on_request)

        try:
            print("Navegando para o portal Extranet...")
            page.goto(url, wait_until="networkidle", timeout=60_000)
            
            # Aguarda e preenche login
            by_xpath(page, XPATHS["user"]).wait_for(state="visible", timeout=60_000)
            by_xpath(page, XPATHS["user"]).fill(user)
            by_xpath(page, XPATHS["password"]).fill(password)
            
            print("Credenciais preenchidas. Submetendo login...")
            time.sleep(2)
            page.keyboard.press("Enter")

            # Aguarda a página carregar após login
            print("Aguardando confirmação de sessão...")
            start_wait = time.time()
            while time.time() - start_wait < 60:
                _tratar_popup_avaliacao(page)
                if bearer_token:
                    break
                page.wait_for_timeout(1_500)

            # Extração suplementar via localStorage / sessionStorage caso não capturado
            if not bearer_token:
                try:
                    storage_tokens = page.evaluate("""() => {
                        let tokens = [];
                        for (let i = 0; i < localStorage.length; i++) {
                            let k = localStorage.key(i);
                            let v = localStorage.getItem(k);
                            if (v && (v.includes('eyJ') || k.toLowerCase().includes('token') || k.toLowerCase().includes('auth'))) {
                                tokens.push(v);
                            }
                        }
                        for (let i = 0; i < sessionStorage.length; i++) {
                            let k = sessionStorage.key(i);
                            let v = sessionStorage.getItem(k);
                            if (v && (v.includes('eyJ') || k.toLowerCase().includes('token') || k.toLowerCase().includes('auth'))) {
                                tokens.push(v);
                            }
                        }
                        return tokens;
                    }""")
                    for t in storage_tokens:
                        if isinstance(t, str):
                            # Tenta parsear caso seja um JSON salvo no storage
                            try:
                                parsed = json.loads(t)
                                if isinstance(parsed, dict):
                                    cand = parsed.get("accessToken") or parsed.get("access_token") or parsed.get("idToken") or parsed.get("secret")
                                    if cand and isinstance(cand, str) and cand.startswith("eyJ"):
                                        bearer_token = cand
                                        print("  ✔ Token de autorização extraído do Storage do navegador!")
                                        break
                            except Exception:
                                if t.startswith("eyJ"):
                                    bearer_token = t
                                    print("  ✔ Token JWT extraído do Storage do navegador!")
                                    break
                except Exception as e:
                    print(f"  [Aviso] Falha ao inspecionar Web Storage: {e}")

            captured_cookies = context.cookies()
            print(f"Sessão validada. Total de cookies capturados: {len(captured_cookies)}")

        finally:
            page.wait_for_timeout(2_000)
            context.close()
            browser.close()

    if bearer_token:
        auth_headers["Authorization"] = f"Bearer {bearer_token}"
    
    # Cria uma sessão do Requests com os cookies capturados
    session = requests.Session()
    session.headers.update(auth_headers)
    for c in captured_cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

    return {
        "session": session,
        "token": bearer_token,
        "headers": auth_headers,
    }


# ─────────────────────────────────────────────
# 3. Requisições na API de Picking com Rate Limiter
# ─────────────────────────────────────────────

def consultar_api_picking(
    session_data: Dict[str, Any],
    nota: str,
    pdv: str,
    timeout_segundos: int = 30,
) -> Optional[List[Dict[str, Any]]]:
    """
    Consulta o endpoint de picking para uma nota fiscal e PDV específicos.
    Endpoint: /invoice-number/{nota}/store/{pdv}
    """
    url = f"{API_BASE_URL}/invoice-number/{nota}/store/{pdv}"
    session: requests.Session = session_data["session"]
    headers = session_data["headers"]

    max_tentativas = 3
    for tentativa in range(1, max_tentativas + 1):
        try:
            resp = session.get(url, headers=headers, timeout=timeout_segundos)
            
            # Se a API exigir retry por rate limit (429)
            if resp.status_code == 429:
                wait_time = 10 * tentativa
                print(f"  [Rate Limit 429] Aguardando {wait_time}s para tentar novamente...")
                time.sleep(wait_time)
                continue

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # Normaliza retorno para lista de itens
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        # Caso venha encapsulado em { "items": [...] } ou { "data": [...] }
                        if "items" in data and isinstance(data["items"], list):
                            return data["items"]
                        if "data" in data and isinstance(data["data"], list):
                            return data["data"]
                        if "volumes" in data and isinstance(data["volumes"], list):
                            # Se for aninhado por volumes, achata
                            itens_achatados = []
                            for vol in data["volumes"]:
                                vol_id = vol.get("volume") or vol.get("volumeIdentifier")
                                for it in vol.get("items", [vol]):
                                    it_copy = dict(it)
                                    if "volume" not in it_copy and vol_id:
                                        it_copy["volume"] = vol_id
                                    itens_achatados.append(it_copy)
                            return itens_achatados
                        return [data]
                except Exception as ex_json:
                    print(f"  [Erro JSON] Resposta inválida para Nota {nota} / PDV {pdv}: {ex_json}")
                    return None

            elif resp.status_code == 404:
                print(f"  [404 Não Encontrado] Nota {nota} / PDV {pdv} sem registros de picking.")
                return None
            else:
                print(f"  [Aviso] Nota {nota} / PDV {pdv} retornou HTTP {resp.status_code}: {resp.text[:120]}")

        except requests.RequestException as e:
            print(f"  [Erro de Rede] Tentativa {tentativa}/{max_tentativas} para Nota {nota} / PDV {pdv}: {e}")
            time.sleep(3)

    return None


# ─────────────────────────────────────────────
# 4. Geração do XLSX Padronizado (op_piking.xlsx)
# ─────────────────────────────────────────────

def formatar_item_para_colunas(item: Dict[str, Any]) -> Dict[str, Any]:
    """Mapeia os campos do JSON para as 9 colunas exatas do template."""
    return {
        "volume": item.get("volume") or item.get("volumeIdentifier"),
        "itemNumber": str(item.get("itemNumber", "")).zfill(6) if item.get("itemNumber") is not None else "",
        "handlingUnitCode": str(item.get("handlingUnitCode", "")),
        "quantity": item.get("quantity") if item.get("quantity") is not None else 0,
        "batchCode": str(item.get("batchCode", "")) if item.get("batchCode") is not None else "",
        "volumeIdentifier": item.get("volumeIdentifier") or item.get("volume"),
        "materialCode": str(item.get("materialCode", "")).zfill(18) if item.get("materialCode") is not None else "",
        "materialDescription": str(item.get("materialDescription", "")),
        "expirationDate": str(item.get("expirationDate", "")) if item.get("expirationDate") is not None else "",
    }


def gerar_planilha_op_picking(
    itens: List[Dict[str, Any]],
    caminho_saida: Path | str,
) -> Path:
    """
    Gera o arquivo XLSX final exatamente no layout de op_piking.xlsx (aba 'data' e 9 colunas).
    """
    caminho = Path(caminho_saida)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "data"

    # Escreve a linha de cabeçalho
    for col_idx, col_name in enumerate(COLUNAS_OP_PIKING, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = Font(name="Calibri", size=11, bold=False)
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 13.0

    # Escreve os registros de dados
    for row_idx, item in enumerate(itens, start=2):
        row_dict = formatar_item_para_colunas(item)
        for col_idx, col_name in enumerate(COLUNAS_OP_PIKING, start=1):
            val = row_dict.get(col_name)
            cell = ws.cell(row=row_idx, column=col_idx)
            
            # Formatação específica por tipo
            if col_name == "quantity":
                try:
                    cell.value = float(val) if "." in str(val) else int(val)
                except Exception:
                    cell.value = val
            elif col_name in ("itemNumber", "handlingUnitCode", "materialCode", "expirationDate", "batchCode"):
                # Força formato texto para preservar zeros à esquerda
                cell.number_format = "@"
                cell.value = str(val) if val is not None else ""
            else:
                cell.value = val

    wb.save(caminho)
    print(f"\n[OK] Planilha OP Picking salva com sucesso ({len(itens)} linhas): {caminho}")
    return caminho


# ─────────────────────────────────────────────
# 5. Execução Principal (Orquestração)
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Extração de OP Picking via API do Grupo Boticário")
    parser.add_argument("--relatorio", type=str, default=None, help="Caminho do relatório de notas faturadas (.xls ou .xlsx)")
    parser.add_argument("--nota", type=str, default=None, help="Número da nota fiscal única para consulta")
    parser.add_argument("--pdv", type=str, default=None, help="Código do PDV / Store único para consulta")
    parser.add_argument("--saida", type=str, default=None, help="Caminho do arquivo XLSX de saída")
    parser.add_argument("--delay", type=float, default=5.0, help="Intervalo mínimo em segundos entre chamadas (padrão: 5.0s)")
    return parser.parse_args()


@log_execution(modulo="XML Picking")
def main() -> None:
    args = parse_args()
    print("================================================================")
    print("        SOFI — AUTOMAÇÃO DE EXTRAÇÃO OP PICKING (MÓDULO XML)   ")
    print("================================================================")

    pares_consulta: List[Tuple[str, str]] = []

    # 1. Modo direto (Nota e PDV informados na linha de comando)
    if args.nota and args.pdv:
        pares_consulta.append((args.nota.strip(), args.pdv.strip()))
        print(f"Modo direto ativado: Nota={args.nota}, PDV={args.pdv}")

    # 2. Modo relatório informado via CLI
    elif args.relatorio:
        caminho_rel = Path(args.relatorio)
        pares_consulta = extrair_notas_de_planilha(caminho_rel)

    # 3. Modo automático: busca o relatório faturado mais recente
    else:
        rel_recente = encontrar_relatorio_mais_recente()
        if rel_recente:
            print(f"Relatório de notas faturadas detectado automaticamente: {rel_recente}")
            pares_consulta = extrair_notas_de_planilha(rel_recente)
        else:
            print("\nNenhum relatório de notas encontrado automaticamente.")
            print("Digite manualmente a nota e o PDV ou informe o caminho do arquivo:")
            nota_input = input("Número da Nota Fiscal (ou ENTER para cancelar): ").strip()
            if not nota_input:
                print("Operação cancelada.")
                return
            pdv_input = input("Código do PDV / Loja: ").strip()
            pares_consulta.append((nota_input, pdv_input))

    if not pares_consulta:
        print("Nenhuma nota fiscal para consultar. Finalizando.")
        return

    print(f"\nTotal de requisições a serem realizadas: {len(pares_consulta)}")
    delay_base = max(5.0, args.delay)
    print(f"Controle de taxa ativo: delay mínimo de {delay_base:.1f}s (+ jitter) entre requisições.")

    # 4. Autenticação e obtenção da sessão
    session_data = autenticar_extranet_e_obter_sessao()

    # 5. Loop de consultas na API
    todos_os_itens: List[Dict[str, Any]] = []
    total = len(pares_consulta)

    print("\n--- Iniciando consultas na API de Demanda e Abastecimento ---")
    for idx, (nota, pdv) in enumerate(pares_consulta, start=1):
        print(f"\n[{idx}/{total}] Consultando Nota: {nota} | PDV: {pdv}...")
        itens_resp = consultar_api_picking(session_data, nota, pdv)

        if itens_resp:
            print(f"  ✔ Sucesso: {len(itens_resp)} itens de picking encontrados.")
            todos_os_itens.extend(itens_resp)
        else:
            print(f"  ℹ Sem dados para Nota {nota} / PDV {pdv}.")

        # Delay respeitoso partindo de 5 segundos + variação randômica (jitter)
        if idx < total:
            tempo_espera = delay_base + random.uniform(0.5, 1.5)
            print(f"  Aguardando {tempo_espera:.1f}s antes da próxima requisição...")
            time.sleep(tempo_espera)

    # 6. Geração da planilha final
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.saida:
        caminho_final = Path(args.saida)
    else:
        caminho_final = DIRETORIO_ATUAL / f"op_piking_extraido_{timestamp_str}.xlsx"

    if todos_os_itens:
        gerar_planilha_op_picking(todos_os_itens, caminho_final)
    else:
        print("\n[AVISO] Nenhum item de picking retornado pelas consultas. Gerando planilha de estrutura vazia...")
        gerar_planilha_op_picking([], caminho_final)

    print("\n================================================================")
    print(f"Processamento concluído! Arquivo gerado em: {caminho_final}")
    print("================================================================")


if __name__ == "__main__":
    main()
