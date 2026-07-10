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
    
    # Validar API Key
    if not API_KEY:
        print("\n" + "=" * 70)
        print(" AVISO IMPORTANTE ".center(70, "!"))
        print("=" * 70)
        print("Você precisa configurar a API Key do MeuDanfe!")
        print("1. Acesse: https://web.meudanfe.com.br")
        print("2. Vá em: API / Integração")
        print("3. Crie ou copie sua API Key")
        print("4. Cole no arquivo .env: MEUDANFE_API_KEY=sua_chave_aqui")
        print("=" * 70)
        sys.exit(1)
    
    log(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    log(f"Base URL: {BASE_URL}")
    log(f"Delay entre requests: {DELAY_ENTRE_REQUESTS}s")
    sep("-")
    
    # 0. Limpar a pasta temporária de XMLs locais
    if os.path.exists(args.pasta_saida):
        shutil.rmtree(args.pasta_saida)
    os.makedirs(args.pasta_saida, exist_ok=True)
    log(f"Pasta temporária local '{args.pasta_saida}' limpa com sucesso.")
    sep("-")
    
    # 1. Definir e ler chaves da planilha
    caminho_planilha = args.planilha
    if not caminho_planilha:
        caminho_planilha = obter_planilha_recente()
        if not caminho_planilha:
            log("AVISO: Pasta na rede Z: indisponível ou vazia.", "AVISO")
            if os.path.exists(PLANILHA_ENTRADA_FALLBACK):
                caminho_planilha = PLANILHA_ENTRADA_FALLBACK
                log(f"Usando fallback local: {caminho_planilha}")
            else:
                log("Nenhuma planilha base encontrada. Encerrando.", "ERRO")
                sys.exit(1)
        else:
            log(f"Planilha mais recente encontrada na Z:: {os.path.basename(caminho_planilha)}")
            
    chaves = ler_chaves_planilha(caminho_planilha)
    
    if not chaves:
        log("Nenhuma chave válida encontrada na planilha!", "ERRO")
        sys.exit(1)
    
    # Aplicar limite se especificado
    if args.limite > 0:
        chaves = chaves[:args.limite]
        log(f"Limitado a {args.limite} chaves para processamento")
    
    sep("-")
    
    # 2. Adicionar notas (se não for apenas-baixar)
    resultados_add = {}
    
    if not args.apenas_baixar:
        log(f"ETAPA 1: Adicionando {len(chaves)} notas via API...")
        sep("-")
        
        for i, chave in enumerate(chaves, 1):
            log(f"[{i}/{len(chaves)}] Adicionando chave: {chave}")
            resultado = adicionar_nota(chave)
            
            if resultado:
                status = resultado.get("status", "")
                resultados_add[chave] = status
                
                # Se está em processamento, aguardar
                if status in ("WAITING", "SEARCHING"):
                    sucesso = aguardar_processamento(chave)
                    resultados_add[chave] = "OK" if sucesso else "TIMEOUT"
            else:
                resultados_add[chave] = "ERRO_REQUEST"
                
                # Se deu erro 401, parar tudo
                if resultado is None and i == 1:
                    log("Primeira requisição falhou. Verifique a API Key.", "ERRO")
                    # Continuar para tentar as outras, pode ser problema temporário
            
            # Rate limiting
            if i < len(chaves):
                time.sleep(DELAY_ENTRE_REQUESTS)
        
        sep("-")
        
        # Resumo da etapa de adição
        ok_count = sum(1 for s in resultados_add.values() if s == "OK")
        fail_count = len(resultados_add) - ok_count
        log(f"RESUMO ADIÇÃO: {ok_count} OK | {fail_count} falhas")
        
        if fail_count > 0:
            log("Chaves com falha:")
            for chave, status in resultados_add.items():
                if status != "OK":
                    log(f"  {chave} -> {status}", "AVISO")
        
        sep("-")
    
    # 3. Baixar XMLs
    log(f"ETAPA 2: Baixando XMLs para '{args.pasta_saida}'...")
    sep("-")
    
    xmls_baixados = 0
    xmls_falha = 0
    chaves_falha_xml = []
    
    for i, chave in enumerate(chaves, 1):
        # Se temos resultado da adição e não foi OK, pular
        if chave in resultados_add and resultados_add[chave] not in ("OK", "WAITING", "SEARCHING"):
            log(f"[{i}/{len(chaves)}] Pulando {chave[-10:]}... (status add: {resultados_add[chave]})")
            xmls_falha += 1
            chaves_falha_xml.append(chave)
            continue
        
        log(f"[{i}/{len(chaves)}] Baixando XML: {chave}")
        resultado_xml = baixar_xml(chave)
        
        if resultado_xml:
            caminho = salvar_xml(resultado_xml["nome"], resultado_xml["xml"], args.pasta_saida)
            log(f"  -> Salvo: {caminho}")
            xmls_baixados += 1
        else:
            xmls_falha += 1
            chaves_falha_xml.append(chave)
        
        # Rate limiting
        if i < len(chaves):
            time.sleep(DELAY_ENTRE_REQUESTS)
    
    sep("=")
    print(" RESULTADO FINAL ".center(70, "="))
    sep("=")
    log(f"Total de chaves processadas: {len(chaves)}")
    log(f"XMLs baixados com sucesso:   {xmls_baixados}")
    log(f"XMLs com falha:              {xmls_falha}")
    log(f"Pasta de saída:              {args.pasta_saida}")
    
    if chaves_falha_xml:
        print()
        log("Chaves que falharam no download:")
        for chave in chaves_falha_xml:
            log(f"  {chave}", "AVISO")
    
    sep("=")
    
    # 4. Gerar relatório (opcional)
    if args.gerar_relatorio and xmls_baixados > 0:
        log("ETAPA 3: Gerando relatório final...")
        try:
            # Importa a função de geração de relatório do leitor_xml
            from leitor_xml import gerar_relatorio
            
            # Temporariamente muda a pasta de XMLs para a do MeuDanfe
            import leitor_xml
            pasta_original = 'xmls_recebidos'
            leitor_xml.gerar_relatorio.__globals__  # acessar apenas para verificar
            
            # Copia XMLs para pasta padrão do leitor
            pasta_temp = "xmls_recebidos"
            os.makedirs(pasta_temp, exist_ok=True)
            
            for arquivo in os.listdir(args.pasta_saida):
                if arquivo.lower().endswith('.xml'):
                    shutil.copy2(
                        os.path.join(args.pasta_saida, arquivo),
                        os.path.join(pasta_temp, arquivo)
                    )
            
            gerar_relatorio()
            log("Relatório gerado com sucesso!")
        except Exception as e:
            log(f"Erro ao gerar relatório: {e}", "ERRO")
            log("Você pode gerar manualmente executando: python leitor_xml.py")
    
    elif xmls_baixados > 0:
        print()
        log("Para gerar o relatório final, execute:")
        log(f"  python debug_meudanfe.py --apenas-baixar --gerar-relatorio")
        log("  ou")
        log(f"  python leitor_xml.py")
    
    print()


if __name__ == "__main__":
    main()
