"""
Tratamento de Dados - Relatório MAR
Filtra a planilha por PDV e gera arquivos individuais usando o template de cada loja.

Regras:
  - Cada PDV possui seu próprio template em templates/{PDV}_template.xlsx.
  - Cada PDV gera um arquivo "{PDV}.xlsx" com os dados de BOTICARIO
    (primeiro) e QUEM_DISSE_BERENICE (abaixo), empilhados na mesma aba.
  - PDVs que aparecem na aba EUDORA geram, além do arquivo normal,
    um segundo arquivo "{PDV}_eudora.xlsx" com somente os dados de EUDORA.
  - Os dados são colados na aba "Analise de Compras" do template a partir da linha 9.
  - Se o template do PDV não for encontrado, o PDV é pulado com um aviso.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

import pandas as pd
import xlwings as xw

# ─── Configurações do ambiente ───────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    DIRETORIO_PROJETO = Path(sys.executable).resolve().parent
else:
    DIRETORIO_PROJETO = Path(__file__).resolve().parent
PASTA_DOWNLOADS = DIRETORIO_PROJETO / "downloads"
PASTA_RELATORIOS = DIRETORIO_PROJETO / "relatorios"
PASTA_TEMPLATES = DIRETORIO_PROJETO / "templates"

ABA_TEMPLATE = "Analise de Compras"
LINHA_INICIO_DADOS = 9

# Nomes das abas na planilha original
ABA_EUDORA = "EUDORA"
ABA_BOTICARIO = "BOTICARIO"
ABA_QDB = "QUEM_DISSE_BERENICE"

# Nome da coluna que contém o código do PDV
COLUNA_PDV = "PDV"


# ─── Funções auxiliares ───────────────────────────────────────────────────────

def log(mensagem: str) -> None:
    """Imprime mensagem com timestamp."""
    agora = datetime.now().strftime("%H:%M:%S")
    print(f"[{agora}] {mensagem}")


def buscar_template(pdv: int) -> Path | None:
    """Busca o template padrão/normal do PDV na pasta de templates.
    
    Retorna o caminho do template se encontrado, ou None se não existir.
    O nome esperado é: {PDV}_template.xlsx (ex: 20843_template.xlsx)
    """
    template = PASTA_TEMPLATES / f"{pdv}_template.xlsx"
    if template.exists():
        return template
    return None


def buscar_template_eudora(pdv: int) -> Path | None:
    """Busca o template de Eudora para o PDV.
    
    Tenta primeiro {PDV}_eudora_template.xlsx.
    Se não encontrar, busca o template padrão {PDV}_template.xlsx.
    """
    template_eudora = PASTA_TEMPLATES / f"{pdv}_eudora_template.xlsx"
    if template_eudora.exists():
        return template_eudora
    return buscar_template(pdv)


def encontrar_planilha_mais_recente(pasta: Path) -> Path:
    """Retorna o arquivo .xlsx mais recente na pasta de downloads."""
    arquivos = [
        f for f in pasta.glob("*.xlsx")
        if not f.name.startswith("~$")
    ]

    if not arquivos:
        print("=" * 60)
        print("ERRO: Nenhum arquivo .xlsx encontrado na pasta 'downloads'.")
        sys.exit(1)

    arquivos.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return arquivos[0]


def salvar_com_template_xlwings(app: xw.App, df: pd.DataFrame, caminho_destino: Path, template_arquivo: Path) -> None:
    """Salva o DataFrame usando o template da loja, colando a partir da linha 9 usando Excel via COM.
    
    Limpa e cola dados apenas até a coluna AQ (43 colunas).
    Todas as fórmulas da coluna AR em diante são preservadas intactas.
    """
    # Copia o template da loja para o destino
    shutil.copy(template_arquivo, caminho_destino)

    if df.empty:
        return

    # Limite fixo: colar somente até a coluna AQ (coluna 43)
    ULTIMA_COLUNA_DADOS = "AQ"
    MAX_COLUNAS = 43

    # Abre a cópia do arquivo usando o Excel em background
    wb = app.books.open(str(caminho_destino))
    
    try:
        # Busca a aba ignorando maiúsculas/minúsculas
        ws = None
        for sheet in wb.sheets:
            if sheet.name.lower() == ABA_TEMPLATE.lower():
                ws = sheet
                break
                
        if not ws:
            raise ValueError(f"Aba '{ABA_TEMPLATE}' não encontrada no template.")

        # Determina a última linha usada no template
        ultima_linha = ws.range(f'A{ws.cells.last_cell.row}').end('up').row

        # Limpa somente de A até AQ — fórmulas de AR em diante ficam intactas
        if ultima_linha >= LINHA_INICIO_DADOS:
            ws.range(f"A{LINHA_INICIO_DADOS}:{ULTIMA_COLUNA_DADOS}{ultima_linha}").clear_contents()

        # Trunca o DataFrame para no máximo 43 colunas (A até AQ)
        df_truncado = df.iloc[:, :MAX_COLUNAS]

        # Cola os dados como valores a partir da linha 9
        ws.range(f"A{LINHA_INICIO_DADOS}").options(index=False, header=False).value = df_truncado

        wb.save()
    finally:
        wb.close()


# ─── Fluxo principal ─────────────────────────────────────────────────────────

def executar_tratamento():
    """Executa o tratamento completo da planilha MAR."""
    log("Iniciando tratamento de dados do relatório MAR com TEMPLATE por loja (Colar 123)...")

    arquivo_origem = encontrar_planilha_mais_recente(PASTA_DOWNLOADS)
    log(f"Planilha encontrada: {arquivo_origem.name}")
    log(f"Pasta de templates: {PASTA_TEMPLATES}")

    if not PASTA_TEMPLATES.exists():
        log("ERRO: Pasta 'templates' não encontrada no diretório do projeto.")
        sys.exit(1)

    templates_encontrados = list(PASTA_TEMPLATES.glob("*_template.xlsx"))
    log(f"Templates encontrados: {len(templates_encontrados)}")

    log("Lendo abas da planilha (isso pode levar alguns segundos)...")
    try:
        # O Pandas continua lendo com openpyxl porque é muito rápido só para leitura
        xls = pd.ExcelFile(arquivo_origem, engine="openpyxl")
    except Exception as e:
        log(f"ERRO ao abrir a planilha original: {e}")
        sys.exit(1)

    abas_disponiveis = xls.sheet_names

    df_boticario = pd.DataFrame()
    df_qdb = pd.DataFrame()
    df_eudora = pd.DataFrame()

    if ABA_BOTICARIO in abas_disponiveis:
        df_boticario = pd.read_excel(xls, sheet_name=ABA_BOTICARIO)
        if "Categoria" in df_boticario.columns:
            df_boticario = df_boticario[df_boticario["Categoria"].fillna("").astype(str).str.strip().str.upper() != "SUPORTE À VENDA"]

    if ABA_QDB in abas_disponiveis:
        df_qdb = pd.read_excel(xls, sheet_name=ABA_QDB)
        if "Categoria" in df_qdb.columns:
            df_qdb = df_qdb[df_qdb["Categoria"].fillna("").astype(str).str.strip().str.upper() != "SUPORTE À VENDA"]

    if ABA_EUDORA in abas_disponiveis:
        df_eudora = pd.read_excel(xls, sheet_name=ABA_EUDORA)
        if "Categoria" in df_eudora.columns:
            df_eudora = df_eudora[df_eudora["Categoria"].fillna("").astype(str).str.strip().str.upper() != "EMBALAGENS"]

    pdvs_boticario = set(df_boticario[COLUNA_PDV].dropna().unique()) if not df_boticario.empty else set()
    pdvs_qdb = set(df_qdb[COLUNA_PDV].dropna().unique()) if not df_qdb.empty else set()
    pdvs_eudora = set(df_eudora[COLUNA_PDV].dropna().unique()) if not df_eudora.empty else set()

    todos_pdvs = sorted(pdvs_boticario | pdvs_qdb)

    log(f"Total de PDVs normais a processar: {len(todos_pdvs)}")
    
    PASTA_RELATORIOS.mkdir(exist_ok=True)
    arquivos_gerados = 0
    erros = 0
    pdvs_sem_template = []

    log("Abrindo Excel em background para realizar a colagem...")
    
    # Usa uma única instância do Excel invisível para ser muito mais rápido
    with xw.App(visible=False) as app:
        app.display_alerts = False
        app.screen_updating = False

        # 1. Gera arquivos normais (Boticário + QDB)
        for pdv in todos_pdvs:
            pdv_int = int(pdv)
            
            # Gera relatório normal se tiver template normal
            template_normal = buscar_template(pdv_int)
            if template_normal is not None:
                try:
                    dados_bot = df_boticario[df_boticario[COLUNA_PDV] == pdv] if not df_boticario.empty else pd.DataFrame()
                    dados_qdb = df_qdb[df_qdb[COLUNA_PDV] == pdv] if not df_qdb.empty else pd.DataFrame()

                    partes = []
                    if not dados_bot.empty: partes.append(dados_bot)
                    if not dados_qdb.empty: partes.append(dados_qdb)

                    if partes:
                        df_combinado = pd.concat(partes, ignore_index=True)
                        caminho_arquivo = PASTA_RELATORIOS / f"{pdv_int}.xlsx"
                        salvar_com_template_xlwings(app, df_combinado, caminho_arquivo, template_normal)
                        arquivos_gerados += 1
                        log(f"  ✓ {pdv_int}.xlsx ({len(df_combinado)} linhas | template: {template_normal.name})")
                except Exception as e:
                    log(f"  ✗ ERRO no PDV {pdv}: {e}")
                    erros += 1
            else:
                pdvs_sem_template.append(pdv_int)
                log(f"  ⚠ PDV {pdv_int}: template normal não encontrado ({pdv_int}_template.xlsx). Pulando relatório normal...")

            # Gera arquivo Eudora se for o caso
            if pdv in pdvs_eudora:
                template_eudora = buscar_template_eudora(pdv_int)
                if template_eudora is not None:
                    try:
                        dados_eud = df_eudora[df_eudora[COLUNA_PDV] == pdv]
                        if not dados_eud.empty:
                            caminho_eudora = PASTA_RELATORIOS / f"{pdv_int}_eudora.xlsx"
                            salvar_com_template_xlwings(app, dados_eud, caminho_eudora, template_eudora)
                            arquivos_gerados += 1
                            log(f"  ✓ {pdv_int}_eudora.xlsx ({len(dados_eud)} linhas | template: {template_eudora.name})")
                    except Exception as e:
                        log(f"  ✗ ERRO no PDV Eudora {pdv}: {e}")
                        erros += 1
                else:
                    if pdv_int not in pdvs_sem_template:
                        pdvs_sem_template.append(pdv_int)
                    log(f"  ⚠ PDV {pdv_int} (Eudora): nenhum template encontrado (nem eudora_template, nem normal). Pulando relatório Eudora...")

        # 2. PDVs que só existem em Eudora
        pdvs_somente_eudora = pdvs_eudora - (pdvs_boticario | pdvs_qdb)
        for pdv in sorted(pdvs_somente_eudora):
            pdv_int = int(pdv)
            template_eudora = buscar_template_eudora(pdv_int)
            if template_eudora is None:
                pdvs_sem_template.append(pdv_int)
                log(f"  ⚠ PDV {pdv_int} (Eudora): nenhum template encontrado (nem eudora_template, nem normal). Pulando...")
                continue

            try:
                dados_eud = df_eudora[df_eudora[COLUNA_PDV] == pdv]
                if not dados_eud.empty:
                    caminio_eudora = PASTA_RELATORIOS / f"{pdv_int}_eudora.xlsx"
                    salvar_com_template_xlwings(app, dados_eud, caminio_eudora, template_eudora)
                    arquivos_gerados += 1
                    log(f"  ✓ {pdv_int}_eudora.xlsx ({len(dados_eud)} linhas | template: {template_eudora.name}) [somente Eudora]")
            except Exception as e:
                log(f"  ✗ ERRO no PDV Eudora {pdv}: {e}")
                erros += 1

    print("=" * 60)
    print(f"  TRATAMENTO CONCLUÍDO!")
    print(f"  Arquivos gerados: {arquivos_gerados} (usando template por loja)")
    if pdvs_sem_template:
        print(f"  PDVs pulados (sem template): {len(pdvs_sem_template)}")
        print(f"    → {', '.join(str(p) for p in sorted(set(pdvs_sem_template)))}")
    if erros: print(f"  Erros: {erros}")
    print("=" * 60)

if __name__ == "__main__":
    executar_tratamento()
