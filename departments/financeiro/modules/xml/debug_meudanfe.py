# -*- coding: utf-8 -*-
"""
Debug: Busca XMLs de NF-e via API MeuDanfe (v2) usando chaves de acesso
Lê as chaves da planilha sintética e baixa os XMLs para gerar o relatório.

Uso:
    python debug_meudanfe.py                        (processa todas as chaves)
    python debug_meudanfe.py --limite 5             (processa apenas as 5 primeiras)
    python debug_meudanfe.py --apenas-baixar        (pula a etapa de adicionar, só baixa XMLs)
"""
import os
import sys
import re
import time
import argparse
import requests
import xlrd
import glob
import shutil
from datetime import datetime
from pathlib import Path

# Localiza a raiz do projeto SOFI-core buscando onde existe o pacote 'core'.
# Não pode usar .env como marcador pois subpastas também possuem .env local.
_ROOT = Path(__file__).resolve().parent
while _ROOT != _ROOT.parent:
    if (_ROOT / "core" / "sofi_env.py").exists():
        break
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

# Importa o logger (mesma raiz já resolvida acima)
from core.database.logger import log_execution

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================
API_KEY = os.getenv("MEUDANFE_API_KEY", "")
BASE_URL = "https://api.meudanfe.com.br/v2"

# Rede T: Planilhas Base
PASTA_PLANILHAS_REDE = r"T:\13-Publica\XMLS CÁLAMO\PLANILHAS_RETAGUARDA"
PREFIXO_PLANILHA = "relatorioSinteticoDeNotasFiscaisCompra"

# Fallback
PLANILHA_ENTRADA_FALLBACK = "relatorioSinteticoDeNotasFiscaisCompra (2).xls"
COLUNA_CHAVE = 7          # Coluna H = índice 7 (0-based)
LINHA_INICIO = 10         # Primeira linha com dados (0-based)

# Pasta de saída temporária para os XMLs baixados (preferencialmente na rede)
if os.path.exists(r"T:\13-Publica\XMLS CÁLAMO"):
    PASTA_XMLS = r"T:\13-Publica\XMLS CÁLAMO\XML BAIXADOS\TEMP_PROCESSAMENTO"
else:
    PASTA_XMLS = "xmls_meudanfe"

# Rate limiting (conforme docs: começar com 2/seg, máx 10/seg)
DELAY_ENTRE_REQUESTS = 0.6  # ~1.7 req/seg (seguro)

# Retry: máximo de tentativas por chave
MAX_TENTATIVAS_ADD = 3      # Tentativas para adicionar a nota
MAX_TENTATIVAS_XML = 3      # Tentativas para baixar o XML
DELAY_RETRY = 2             # Segundos entre retries

# Aguardar processamento (WAITING -> SEARCHING -> OK)
MAX_ESPERA_PROCESSAMENTO = 30  # Segundos máx de espera pelo processamento
INTERVALO_POLLING = 2          # Intervalo entre verificações de status

# ============================================================================
# HEADERS
# ============================================================================
HEADERS = {
    "api-key": API_KEY,
    "Accept": "application/json",
}


def sep(char="=", tamanho=70):
    print(char * tamanho)


def log(msg, tipo="INFO"):
    """Log com timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{tipo}] {msg}")


def obter_planilha_recente():
    """Encontra a planilha mais recente que começa com o prefixo dado na pasta da rede."""
    if not os.path.exists(PASTA_PLANILHAS_REDE):
        return None
        
    # Busca tanto arquivos Excel (.xls, .xlsx) quanto CSV (.csv)
    padroes = [
        os.path.join(PASTA_PLANILHAS_REDE, f"{PREFIXO_PLANILHA}*.xls*"),
        os.path.join(PASTA_PLANILHAS_REDE, f"{PREFIXO_PLANILHA}*.csv")
    ]
    
    arquivos = []
    for padrao in padroes:
        arquivos.extend(glob.glob(padrao))
    
    if not arquivos:
        return None
        
    # Retorna o arquivo com data de modificação mais recente
    arquivo_mais_recente = max(arquivos, key=os.path.getmtime)
    return arquivo_mais_recente


def validar_chave(chave):
    """Valida se a chave NFe tem 44 dígitos numéricos."""
    return bool(re.match(r"^\d{44}$", str(chave).strip()))


def ler_chaves_planilha(caminho_planilha):
    """Lê as chaves NFe da planilha sintética (suporta Excel e CSV)."""
    log(f"Lendo planilha: {caminho_planilha}")
    
    if not os.path.exists(caminho_planilha):
        log(f"ERRO: Arquivo não encontrado: {caminho_planilha}", "ERRO")
        return []
    
    valores = []
    
    # 1. Tratamento para arquivos CSV
    if caminho_planilha.lower().endswith('.csv'):
        try:
            import csv
            # Tenta ler com cp1252/latin-1 que é comum no Windows
            with open(caminho_planilha, 'r', encoding='latin-1') as f:
                # Detectar o delimitador (geralmente ; ou ,)
                linha = f.readline()
                delimiter = ';' if ';' in linha else ','
                f.seek(0)
                
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    # Procura robustamente por uma chave NFe em todas as colunas
                    chave_encontrada = False
                    for cell in row:
                        val_limpo = str(cell).strip()
                        if validar_chave(val_limpo):
                            valores.append(val_limpo)
                            chave_encontrada = True
                            break
                    
                    # Se não encontrou varrendo tudo, tenta pegar da coluna H (índice 7) por compatibilidade
                    if not chave_encontrada and len(row) > COLUNA_CHAVE:
                        valores.append(row[COLUNA_CHAVE])
            log(f"Planilha CSV carregada com sucesso.")
        except Exception as e:
            log(f"ERRO ao abrir planilha CSV: {e}", "ERRO")
            return []
            
    # 2. Tratamento para arquivos Excel (.xls, .xlsx)
    else:
        try:
            wb = xlrd.open_workbook(caminho_planilha)
            sheet = wb.sheet_by_index(0)
            log(f"Planilha carregada: {sheet.nrows} linhas x {sheet.ncols} colunas (xlrd)")
            for i in range(LINHA_INICIO, sheet.nrows):
                valores.append(sheet.cell_value(i, COLUNA_CHAVE))
        except Exception as e:
            if "xlsx" in str(e).lower() or "not supported" in str(e).lower():
                try:
                    import openpyxl
                    # Passamos um objeto de arquivo para contornar a verificação restrita de extensão do openpyxl
                    with open(caminho_planilha, 'rb') as f:
                        wb = openpyxl.load_workbook(f, data_only=True)
                    sheet = wb.active
                    log(f"Planilha carregada: {sheet.max_row} linhas x {sheet.max_column} colunas (openpyxl)")
                    # openpyxl is 1-indexed
                    for i in range(LINHA_INICIO + 1, sheet.max_row + 1):
                        valores.append(sheet.cell(row=i, column=COLUNA_CHAVE + 1).value)
                except Exception as e2:
                    log(f"ERRO ao abrir planilha com openpyxl: {e2}", "ERRO")
                    return []
            else:
                log(f"ERRO ao abrir planilha com xlrd: {e}", "ERRO")
                return []
    
    chaves = []
    chaves_duplicadas = 0
    chaves_invalidas = 0
    chaves_vistas = set()
    
    for valor in valores:
        if not valor:
            continue
        
        # Converter para string e limpar
        chave = str(valor).strip()
        
        # Se veio como float (ex: 3.126E+43), converter
        if "." in chave or "E" in chave.upper():
            try:
                chave = str(int(float(chave)))
            except (ValueError, OverflowError):
                pass
        
        if not validar_chave(chave):
            chaves_invalidas += 1
            continue
        
        if chave in chaves_vistas:
            chaves_duplicadas += 1
            continue
        
        chaves_vistas.add(chave)
        chaves.append(chave)
    
    log(f"Chaves encontradas: {len(chaves)} válidas | "
        f"{chaves_duplicadas} duplicadas | {chaves_invalidas} inválidas")
        
    # Adiciona aviso caso a planilha seja um CSV e não contenha chaves válidas
    if caminho_planilha.lower().endswith('.csv') and not chaves:
        sep("!")
        log(" AVISO IMPORTANTE: ARQUIVO CSV SEM CHAVES NFE ".center(70, "!"), "AVISO")
        sep("!")
        log("O relatório mais recente encontrado na rede é um arquivo CSV,", "AVISO")
        log("mas ele NÃO contém nenhuma chave de acesso NFe de 44 dígitos.", "AVISO")
        log("Geralmente, o sistema ERP exporta colunas reduzidas em CSV.", "AVISO")
        log("Para corrigir isso, por favor:", "AVISO")
        log("  1. Acesse o sistema retaguarda/ERP", "AVISO")
        log("  2. Exporte o relatório no formato EXCEL (.xls ou .xlsx) em vez de CSV", "AVISO")
        log("  3. Salve-o na pasta: T:\\13-Publica\\XMLS CÁLAMO\\PLANILHAS_RETAGUARDA", "AVISO")
        sep("!")
    
    return chaves


def adicionar_nota(chave, tentativa=1):
    """
    PUT /fd/add/{Chave-Acesso}
    Busca e adiciona a NF-e na Área do Cliente usando a chave de acesso.
    Retorna o status da operação.
    """
    url = f"{BASE_URL}/fd/add/{chave}"
    
    try:
        response = requests.put(url, headers=HEADERS, timeout=120)
        
        if response.status_code == 200:
            dados = response.json()
            status = dados.get("status", "UNKNOWN")
            status_msg = dados.get("statusMessage", "")
            tipo = dados.get("type", "")
            log(f"  ADD [{chave[-10:]}...] -> {status} ({status_msg}) | Tipo: {tipo}")
            return dados
        
        elif response.status_code == 401:
            log(f"  ERRO 401: API Key inválida ou expirada!", "ERRO")
            return None
        
        elif response.status_code == 429:
            log(f"  ERRO 429: Rate limit atingido! Aguardando...", "AVISO")
            time.sleep(5)
            if tentativa < MAX_TENTATIVAS_ADD:
                return adicionar_nota(chave, tentativa + 1)
            return None
        
        else:
            log(f"  ERRO HTTP {response.status_code}: {response.text[:200]}", "ERRO")
            if tentativa < MAX_TENTATIVAS_ADD:
                time.sleep(DELAY_RETRY)
                return adicionar_nota(chave, tentativa + 1)
            return None
    
    except requests.exceptions.RequestException as e:
        log(f"  ERRO de conexão: {e}", "ERRO")
        if tentativa < MAX_TENTATIVAS_ADD:
            time.sleep(DELAY_RETRY)
            return adicionar_nota(chave, tentativa + 1)
        return None


def aguardar_processamento(chave):
    """
    Após adicionar, a nota pode ficar com status WAITING ou SEARCHING.
    Faz polling até o status virar OK, NOT_FOUND ou ERROR.
    """
    inicio = time.time()
    
    while (time.time() - inicio) < MAX_ESPERA_PROCESSAMENTO:
        time.sleep(INTERVALO_POLLING)
        
        # Re-chama o PUT para verificar status
        url = f"{BASE_URL}/fd/add/{chave}"
        try:
            response = requests.put(url, headers=HEADERS, timeout=120)
            if response.status_code == 200:
                dados = response.json()
                status = dados.get("status", "")
                
                if status == "OK":
                    log(f"  PROCESSADO [{chave[-10:]}...] -> OK")
                    return True
                elif status in ("NOT_FOUND", "ERROR"):
                    msg = dados.get("statusMessage", "")
                    log(f"  FALHA [{chave[-10:]}...] -> {status}: {msg}", "AVISO")
                    return False
                else:
                    elapsed = int(time.time() - inicio)
                    log(f"  AGUARDANDO [{chave[-10:]}...] -> {status} ({elapsed}s)")
        except requests.exceptions.RequestException:
            pass
    
    log(f"  TIMEOUT [{chave[-10:]}...] -> Excedeu {MAX_ESPERA_PROCESSAMENTO}s", "AVISO")
    return False


def baixar_xml(chave, tentativa=1):
    """
    GET /fd/get/xml/{Chave-Acesso}
    Baixa o XML da NF-e já adicionada à Área do Cliente.
    Retorna o conteúdo XML como string, ou None se falhar.
    """
    url = f"{BASE_URL}/fd/get/xml/{chave}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=120)
        
        if response.status_code == 200:
            dados = response.json()
            nome = dados.get("name", f"NFe_{chave}.xml")
            tipo = dados.get("type", "")
            formato = dados.get("format", "")
            xml_data = dados.get("data", "")
            
            if xml_data:
                log(f"  XML [{chave[-10:]}...] -> OK ({nome} | {tipo} | {formato})")
                return {"nome": nome, "xml": xml_data, "tipo": tipo}
            else:
                log(f"  XML [{chave[-10:]}...] -> Resposta vazia!", "AVISO")
                return None
        
        elif response.status_code == 404:
            log(f"  XML [{chave[-10:]}...] -> Nota não encontrada (404)", "AVISO")
            return None
        
        elif response.status_code == 429:
            log(f"  ERRO 429: Rate limit! Aguardando...", "AVISO")
            time.sleep(5)
            if tentativa < MAX_TENTATIVAS_XML:
                return baixar_xml(chave, tentativa + 1)
            return None
        
        else:
            log(f"  ERRO HTTP {response.status_code}: {response.text[:200]}", "ERRO")
            if tentativa < MAX_TENTATIVAS_XML:
                time.sleep(DELAY_RETRY)
                return baixar_xml(chave, tentativa + 1)
            return None
    
    except requests.exceptions.RequestException as e:
        log(f"  ERRO de conexão ao baixar XML: {e}", "ERRO")
        if tentativa < MAX_TENTATIVAS_XML:
            time.sleep(DELAY_RETRY)
            return baixar_xml(chave, tentativa + 1)
        return None


def salvar_xml(nome_arquivo, conteudo_xml, pasta):
    """Salva o conteúdo XML em arquivo na pasta especificada."""
    os.makedirs(pasta, exist_ok=True)
    
    # Sanitizar nome do arquivo
    nome_limpo = re.sub(r'[<>:"/\\|?*]', '_', nome_arquivo)
    if not nome_limpo.lower().endswith('.xml'):
        nome_limpo += '.xml'
    
    caminho = os.path.join(pasta, nome_limpo)
    
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo_xml)
    
    return caminho


def executar_download_chaves(
    caminho_planilha: str | Path | None = None,
    pasta_saida: str | Path | None = None,
    apenas_baixar: bool = False,
    limite: int = 0,
    gerar_relatorio_ao_final: bool = False
) -> tuple[int, int]:
    """
    Executa a leitura da planilha, adiciona as notas na API MeuDanfe e baixa os XMLs.
    
    Returns:
        tuple[int, int]: (total_chaves_encontradas, total_xmls_baixados)
    """
    if not API_KEY:
        log("API Key do MeuDanfe não configurada no .env (MEUDANFE_API_KEY)!", "ERRO")
        return (0, 0)
        
    pasta_destino = str(pasta_saida) if pasta_saida else PASTA_XMLS

    # 0. Limpar pasta temporária
    if os.path.exists(pasta_destino):
        shutil.rmtree(pasta_destino)
    os.makedirs(pasta_destino, exist_ok=True)
    log(f"Pasta temporária '{pasta_destino}' pronta.")

    # 1. Localizar planilha
    planilha_alvo = str(caminho_planilha) if caminho_planilha else obter_planilha_recente()
    if not planilha_alvo or not os.path.exists(planilha_alvo):
        if os.path.exists(PLANILHA_ENTRADA_FALLBACK):
            planilha_alvo = PLANILHA_ENTRADA_FALLBACK
            log(f"Usando fallback local: {planilha_alvo}")
        else:
            log("Nenhuma planilha base encontrada para processar.", "AVISO")
            return (0, 0)
            
    chaves = ler_chaves_planilha(planilha_alvo)
    if not chaves:
        log(f"Nenhuma chave NFe válida encontrada na planilha: {planilha_alvo}", "AVISO")
        return (0, 0)

    if limite > 0:
        chaves = chaves[:limite]
        log(f"Processamento limitado a {limite} chaves.")

    # 2. Adicionar notas via API (se não for apenas-baixar)
    resultados_add = {}
    if not apenas_baixar:
        log(f"ETAPA 1: Adicionando {len(chaves)} notas via API MeuDanfe...")
        for i, chave in enumerate(chaves, 1):
            log(f"[{i}/{len(chaves)}] Adicionando chave: {chave}")
            resultado = adicionar_nota(chave)
            if resultado:
                status = resultado.get("status", "")
                resultados_add[chave] = status
                if status in ("WAITING", "SEARCHING"):
                    sucesso = aguardar_processamento(chave)
                    resultados_add[chave] = "OK" if sucesso else "TIMEOUT"
            else:
                resultados_add[chave] = "ERRO_REQUEST"

            if i < len(chaves):
                time.sleep(DELAY_ENTRE_REQUESTS)

    # 3. Baixar XMLs
    log(f"ETAPA 2: Baixando XMLs para '{pasta_destino}'...")
    xmls_baixados = 0
    for i, chave in enumerate(chaves, 1):
        if chave in resultados_add and resultados_add[chave] not in ("OK", "WAITING", "SEARCHING"):
            log(f"[{i}/{len(chaves)}] Pulando {chave[-10:]}... (status add: {resultados_add[chave]})")
            continue

        log(f"[{i}/{len(chaves)}] Baixando XML: {chave}")
        resultado_xml = baixar_xml(chave)
        if resultado_xml:
            caminho = salvar_xml(resultado_xml["nome"], resultado_xml["xml"], pasta_destino)
            log(f"  -> Salvo: {caminho}")
            xmls_baixados += 1

        if i < len(chaves):
            time.sleep(DELAY_ENTRE_REQUESTS)

    log(f"Resumo MeuDanfe: {len(chaves)} chaves | {xmls_baixados} XMLs baixados.")

    # 4. Geração de relatório opcional
    if gerar_relatorio_ao_final and xmls_baixados > 0:
        try:
            from gerador_relatorio import gerar_relatorio_calamo
            gerar_relatorio_calamo()
        except Exception as e:
            log(f"Erro ao gerar relatórios finais: {e}", "ERRO")

    return (len(chaves), xmls_baixados)


@log_execution(modulo="XML (MeuDanfe Debug)")
def main():
    parser = argparse.ArgumentParser(description="Debug MeuDanfe - Busca XMLs via API")
    parser.add_argument("--limite", type=int, default=0,
                        help="Limitar quantidade de chaves a processar (0 = todas)")
    parser.add_argument("--apenas-baixar", action="store_true",
                        help="Pular a etapa de adicionar, só baixar XMLs de notas já adicionadas")
    parser.add_argument("--planilha", type=str, default="",
                        help="Caminho da planilha de entrada (se vazio, busca a mais recente na Z:)")
    parser.add_argument("--pasta-saida", type=str, default=PASTA_XMLS,
                        help=f"Pasta de saída temporária para XMLs (padrão: {PASTA_XMLS})")
    parser.add_argument("--gerar-relatorio", action="store_true",
                        help="Após baixar XMLs, gerar o relatório final automaticamente")
    args = parser.parse_args()
    
    sep()
    print(" DEBUG - MeuDanfe API v2 ".center(70, "="))
    sep()
    
    executar_download_chaves(
        caminho_planilha=args.planilha or None,
        pasta_saida=args.pasta_saida,
        apenas_baixar=args.apenas_baixar,
        limite=args.limite,
        gerar_relatorio_ao_final=args.gerar_relatorio
    )


if __name__ == "__main__":
    main()
