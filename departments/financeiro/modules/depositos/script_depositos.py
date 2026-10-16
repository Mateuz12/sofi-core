"""
Automação de Lançamento de Depósitos em Lote - Uberlândia
=========================================================

Lê os depósitos de uma aba da planilha de fechamento na rede,
confronta com o cadastro de lojas (lojas.xlsx),
calcula a data de crédito, verifica duplicidade no SQLite (sofi.db)
e envia para a API usando o token do Playwright.
"""

import os
import sys
import io
import json
import time
import sqlite3
import getpass
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

# ============================================================
# CONFIGURAÇÕES DE DIRETÓRIO E AMBIENTE SOFI
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

from core.database.logger import log_execution, DB_FILE
from capturar_token import capturar_autenticacao

LOG_DIR = BASE_DIR / "output" / "logs"
RELATORIO_DIR = BASE_DIR / "output" / "relatorios"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RELATORIO_DIR.mkdir(parents=True, exist_ok=True)

# Exit codes padrão SOFI
EXIT_OK              = 0
EXIT_RETRYABLE       = 1
EXIT_PERMANENT       = 2
EXIT_SEM_FATURAMENTO = 3

# URLs e Caminhos
API_URL = os.getenv(
    "DEPOSITOS_API_URL",
    os.getenv("API_URL", "https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/")
)
ARQUIVO_REDE = os.getenv(
    "DEPOSITOS_PLANILHA_UDI_PATH",
    r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\CONTROLE DE DEPÓSITO\UDI\2026\05-FIN.FECHAMENTO DE CAIXA.CONTROLE DE DEPÓSITO.UDI.2026.PLANILHA DE ACOMPANHAMENTO DE DEPÓSITOS LOJAS - VD.xlsx"
)
ARQUIVO_LOJAS = BASE_DIR / "lojas.xlsx"


# ============================================================
# CONTROLE DE DUPLICIDADE (SQLite - sofi.db)
# ============================================================

def init_depositos_db(db_path: Path | None = None) -> None:
    """Garante a existência da tabela depositos_lancados no banco SQLite."""
    target_db = Path(db_path) if db_path else Path(DB_FILE)
    target_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(target_db), timeout=10.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS depositos_lancados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave_unica TEXT UNIQUE NOT NULL,
                codigo_loja INTEGER NOT NULL,
                nome_loja TEXT,
                data_deposito TEXT NOT NULL,
                data_credito TEXT NOT NULL,
                valor REAL NOT NULL,
                usuario TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


def gerar_chave_unica(codigo_loja: int, data_deposito: datetime, valor: float) -> str:
    """Gera a chave canônica de idempotência: {codigo_loja}_{YYYY-MM-DD}_{valor:.2f}."""
    return f"{int(codigo_loja)}_{data_deposito.strftime('%Y-%m-%d')}_{float(valor):.2f}"


def verificar_duplicidade(chave_unica: str, db_path: Path | None = None) -> dict | None:
    """
    Consulta se a chave_unica já foi enviada com sucesso anteriormente.
    Retorna dict com os dados do lançamento anterior ou None.
    """
    target_db = Path(db_path) if db_path else Path(DB_FILE)
    init_depositos_db(target_db)
    with sqlite3.connect(str(target_db), timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT chave_unica, codigo_loja, nome_loja, data_deposito, data_credito, valor, usuario, timestamp "
            "FROM depositos_lancados WHERE chave_unica = ? LIMIT 1",
            (chave_unica,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def registrar_deposito_lancado(
    chave_unica: str,
    codigo_loja: int,
    nome_loja: str,
    data_deposito: str,
    data_credito: str,
    valor: float,
    db_path: Path | None = None,
) -> None:
    """Registra no SQLite um depósito enviado com SUCESSO na API."""
    target_db = Path(db_path) if db_path else Path(DB_FILE)
    init_depositos_db(target_db)
    usuario = getpass.getuser()
    with sqlite3.connect(str(target_db), timeout=10.0) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO depositos_lancados
                (chave_unica, codigo_loja, nome_loja, data_deposito, data_credito, valor, usuario, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (chave_unica, int(codigo_loja), str(nome_loja), str(data_deposito), str(data_credito), float(valor), usuario),
        )


# ============================================================
# LÓGICA DE DATAS E REGRAS DE CRÉDITO
# ============================================================

def normalizar_data_aba(data_str: str) -> tuple[datetime, str]:
    """
    Aceita datas nos formatos DD.MM.YYYY, DD/MM/YYYY ou YYYY-MM-DD.
    Retorna (datetime, 'DD.MM.YYYY' para busca da aba na planilha).
    """
    limpo = (data_str or "").strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(limpo, fmt)
            return dt, dt.strftime("%d.%m.%Y")
        except ValueError:
            continue
    raise ValueError(f"Data inválida '{data_str}'. Use DD.MM.YYYY ou DD/MM/YYYY.")


def calcular_credito_padrao(data_deposito: datetime) -> datetime:
    dia_semana = data_deposito.weekday()  # 0 = Seg, 6 = Dom
    if dia_semana == 0:  # Seg -> Qua
        return data_deposito + timedelta(days=2)
    elif dia_semana == 1:  # Ter -> Qua
        return data_deposito + timedelta(days=1)
    elif dia_semana == 2:  # Qua -> Sex
        return data_deposito + timedelta(days=2)
    elif dia_semana == 3:  # Qui -> Sex
        return data_deposito + timedelta(days=1)
    elif dia_semana == 4:  # Sex -> Seg
        return data_deposito + timedelta(days=3)
    elif dia_semana == 5:  # Sab -> Seg
        return data_deposito + timedelta(days=2)
    elif dia_semana == 6:  # Dom -> Seg
        return data_deposito + timedelta(days=1)
    return data_deposito


def calcular_credito_911557(data_deposito: datetime) -> datetime:
    dia_semana = data_deposito.weekday()
    if dia_semana == 0:  # Seg -> Qua
        return data_deposito + timedelta(days=2)
    elif dia_semana == 1:  # Ter -> Sex
        return data_deposito + timedelta(days=3)
    elif dia_semana == 2:  # Qua -> Sex
        return data_deposito + timedelta(days=2)
    elif dia_semana == 3:  # Qui -> Seg
        return data_deposito + timedelta(days=4)
    elif dia_semana == 4:  # Sex -> Seg
        return data_deposito + timedelta(days=3)
    elif dia_semana == 5:  # Sab -> Qua
        return data_deposito + timedelta(days=4)
    elif dia_semana == 6:  # Dom -> Qua
        return data_deposito + timedelta(days=3)
    return data_deposito


def formatar_data_api(data: datetime) -> str:
    """Formata a data para o padrão exigido no Payload da API."""
    return data.strftime("%Y-%m-%dT03:00:00.000Z")


# ============================================================
# EXTRAÇÃO E TRANSFORMAÇÃO DE DADOS
# ============================================================

def ler_cadastro_lojas() -> dict:
    """
    Lê o lojas.xlsx e retorna um dicionário onde a chave é o CODIGO_LOJA.
    """
    if not ARQUIVO_LOJAS.exists():
        print(f"❌ ARQUIVO NÃO ENCONTRADO: {ARQUIVO_LOJAS}")
        raise FileNotFoundError(f"Arquivo de cadastro de lojas não encontrado: {ARQUIVO_LOJAS}")

    df_lojas = pd.read_excel(ARQUIVO_LOJAS)
    lojas_dict = {}
    for _, row in df_lojas.iterrows():
        try:
            codigo = int(row["CODIGO_LOJA"])
            lojas_dict[codigo] = {
                "nome": str(row["NOME_LOJA"]),
                "conta_origem": str(row["CONTA_ORIGEM"]),
                "conta_destino": str(row["CONTA_DESTINO"]),
                "empresa_id": str(row["EMPRESA_ID"])
            }
        except Exception:
            continue
    return lojas_dict


def obter_arquivo_rede(data_deposito: datetime | None = None) -> str:
    """
    Retorna o caminho da planilha de controle de depósitos na rede.
    Se DEPOSITOS_PLANILHA_UDI_PATH estiver definido no .env, usa-o;
    caso contrário, resolve dinamicamente pelo ano de data_deposito.
    """
    env_path = os.getenv("DEPOSITOS_PLANILHA_UDI_PATH")
    if env_path:
        return env_path
    ano = data_deposito.year if data_deposito else 2026
    return (
        rf"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\CONTROLE DE DEPÓSITO\UDI\{ano}"
        rf"\05-FIN.FECHAMENTO DE CAIXA.CONTROLE DE DEPÓSITO.UDI.{ano}.PLANILHA DE ACOMPANHAMENTO DE DEPÓSITOS LOJAS - VD.xlsx"
    )


def ler_planilha_rede(data_str: str) -> list:
    """
    Lê a planilha da rede na aba referente à data informada.
    Extrai apenas a Tabela 1 (Uberlândia).
    Retorna uma lista de dicionários com os depósitos válidos.
    """
    try:
        dt_ref, _ = normalizar_data_aba(data_str)
    except ValueError:
        dt_ref = None
    caminho_rede = obter_arquivo_rede(dt_ref)
    print(f"Lendo aba '{data_str}' do arquivo: {caminho_rede}")
    try:
        # Tenta ler apenas a aba com o nome da data
        df = pd.read_excel(caminho_rede, sheet_name=data_str, header=None)
    except Exception as e:
        print(f"❌ Erro ao ler a aba '{data_str}'. Tem certeza que essa aba existe?")
        print(f"Detalhes: {e}")
        return []

    # Tabela 1 (Uberlândia) inicia na linha 3 (index 2).
    # Colunas: 1 (Código), 2 (Loja), 6 (Depósito)
    depositos_validos = []

    # Pulando as 2 primeiras linhas de cabeçalho e lendo linha a linha
    for i in range(2, len(df)):
        row = df.iloc[i]

        codigo_raw = row[1]
        nome_loja_raw = row[2]
        deposito_raw = row[6]

        # Parar se não tiver mais códigos e for o fim da tabela
        if pd.isna(codigo_raw) or str(codigo_raw).strip() == "":
            continue

        try:
            codigo = int(codigo_raw)
        except ValueError:
            # Se não conseguir converter para int, pula (ex: textos como "Total")
            continue

        # Tratar o valor do depósito
        try:
            # Substitui virgula por ponto se for string e converte para float
            if isinstance(deposito_raw, str):
                valor = float(deposito_raw.replace('R$', '').replace('.', '').replace(',', '.').strip())
            else:
                valor = float(deposito_raw)
        except Exception:
            valor = 0.0

        if valor <= 0 or pd.isna(valor):
            # Depositos zerados, negativos ou nulos são ignorados
            continue

        depositos_validos.append({
            "codigo": codigo,
            "nome_planilha": str(nome_loja_raw),
            "valor": valor
        })

    print(f"✔️ Encontrados {len(depositos_validos)} depósitos válidos na Tabela Uberlândia.")
    return depositos_validos


# ============================================================
# API E EXECUÇÃO
# ============================================================

def enviar_para_api(payload: dict, headers: dict) -> dict:
    """Envia requisição de depósito para a API."""
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=15)

        if response.status_code in [200, 201]:
            resp_json = response.json()
            if not resp_json.get("errors"):
                return {"status": "SUCESSO", "status_code": response.status_code, "msg": "Ok"}
            else:
                return {"status": "ERRO_NEGOCIO", "status_code": response.status_code, "msg": str(resp_json.get("errors"))}
        else:
            return {"status": "FALHA_HTTP", "status_code": response.status_code, "msg": response.text[:200]}
    except Exception as e:
        return {"status": "ERRO_REDE", "status_code": 0, "msg": str(e)}


def executar(data_str: str, is_dry_run: bool = False, forcar_reenvio: bool = False) -> int:
    # 1. Parse da data base
    try:
        data_deposito, aba_str = normalizar_data_aba(data_str)
    except ValueError as e:
        print(f"❌ {e}")
        return EXIT_PERMANENT

    print(f"--- INICIANDO PROCESSAMENTO: DATA {aba_str} ---")
    if is_dry_run:
        print("⚠️ MODO DRY-RUN: Nenhum dado será enviado para a API.")
    if forcar_reenvio:
        print("⚠️ MODO FORÇAR REENVIO: Trava de duplicidade ignorada nesta execução.")

    # Inicializa tabela de controle de duplicidade no SQLite
    init_depositos_db(DB_FILE)

    # 2. Carregar configurações
    try:
        cadastro_lojas = ler_cadastro_lojas()
    except FileNotFoundError:
        return EXIT_PERMANENT

    # 3. Ler planilha
    dados_planilha = ler_planilha_rede(aba_str)
    if not dados_planilha:
        print("Nenhum dado para processar. Encerrando.")
        return EXIT_SEM_FATURAMENTO

    # 4. Filtrar previamente se há algum item pendente de envio real antes de abrir o Playwright
    pendentes_envio_real = 0
    for item in dados_planilha:
        cod = item["codigo"]
        val = item["valor"]
        if cod not in cadastro_lojas:
            continue
        chave = gerar_chave_unica(cod, data_deposito, val)
        if forcar_reenvio or not verificar_duplicidade(chave, db_path=DB_FILE):
            pendentes_envio_real += 1

    # 5. Capturar token se não for dry-run e houver pelo menos 1 depósito pendente
    bearer, cookie = None, None
    if not is_dry_run and pendentes_envio_real > 0:
        print("\n--- CAPTURANDO TOKEN DE AUTENTICAÇÃO ---")
        bearer, cookie = capturar_autenticacao()
        if not bearer or not cookie:
            print("❌ Falha ao capturar token. Encerrando.")
            return EXIT_RETRYABLE

    headers = {
        "Content-Type": "application/json",
        "Authorization": bearer if bearer else "",
        "Cookie": cookie if cookie else ""
    }

    # 6. Processamento e montagem dos Payloads
    relatorio = []
    houve_falha_rede_ou_http = False

    for item in dados_planilha:
        codigo = item["codigo"]
        valor = item["valor"]

        linha_relatorio = {
            "Data Depósito": aba_str,
            "Código Loja": codigo,
            "Nome Planilha": item["nome_planilha"],
            "Valor R$": valor,
            "Regra Crédito": "N/A",
            "Data Crédito": "N/A",
            "Status": "IGNORADO",
            "Detalhe": ""
        }

        # Puxar dados de cadastro
        loja_cadastrada = cadastro_lojas.get(codigo)
        if not loja_cadastrada:
            linha_relatorio["Status"] = "ERRO"
            linha_relatorio["Detalhe"] = "Loja não encontrada no lojas.xlsx"
            relatorio.append(linha_relatorio)
            continue

        # Identificar Regra e Data de Crédito
        if codigo == 911557:
            regra = "ESPECIAL_911557"
            dt_credito = calcular_credito_911557(data_deposito)
        else:
            regra = "PADRÃO"
            dt_credito = calcular_credito_padrao(data_deposito)

        dt_credito_str = dt_credito.strftime("%d.%m.%Y")
        linha_relatorio["Regra Crédito"] = regra
        linha_relatorio["Data Crédito"] = dt_credito_str

        # Verificar Duplicidade no SQLite
        chave_unica = gerar_chave_unica(codigo, data_deposito, valor)
        registro_anterior = verificar_duplicidade(chave_unica, db_path=DB_FILE)
        if registro_anterior and not forcar_reenvio:
            ts_ant = registro_anterior.get("timestamp", "data anterior")
            print(f"⏭️ Loja {codigo} (R$ {valor:.2f}) ignorada por duplicidade (já enviado em {ts_ant}).")
            linha_relatorio["Status"] = "IGNORADO_DUPLICIDADE"
            linha_relatorio["Detalhe"] = f"Já lançado com sucesso em {ts_ant}"
            relatorio.append(linha_relatorio)
            continue

        nome_conta_origem = f"CAIXA LOJA - {codigo} - {loja_cadastrada['nome']}"

        # Montar Payload
        payload = {
            "_id": None,
            "ContaOrigem": loja_cadastrada["conta_origem"],
            "ContaDestino": loja_cadastrada["conta_destino"],
            "Data": formatar_data_api(data_deposito),
            "DataDoCredito": formatar_data_api(dt_credito),
            "Descricao": f"Depósito para CC em {data_deposito.strftime('%d/%m/%Y')}",
            "EmpresaId": loja_cadastrada["empresa_id"],
            "NomeContaDestino": None,
            "NomeContaOrigem": nome_conta_origem,
            "Valor": valor,
            "errors": []
        }

        # Disparo
        if is_dry_run:
            linha_relatorio["Status"] = "SIMULADO"
            linha_relatorio["Detalhe"] = "Não enviado (Dry-Run)"
        else:
            print(f"Enviando depósito - Loja: {codigo} | Valor: R$ {valor:.2f}...")
            resultado = enviar_para_api(payload, headers)
            linha_relatorio["Status"] = resultado["status"]
            linha_relatorio["Detalhe"] = resultado["msg"]

            if resultado["status"] == "SUCESSO":
                registrar_deposito_lancado(
                    chave_unica=chave_unica,
                    codigo_loja=codigo,
                    nome_loja=loja_cadastrada["nome"],
                    data_deposito=aba_str,
                    data_credito=dt_credito_str,
                    valor=valor,
                    db_path=DB_FILE,
                )
            elif resultado["status"] in ("FALHA_HTTP", "ERRO_REDE"):
                houve_falha_rede_ou_http = True

            # Pequena pausa entre requisições
            time.sleep(1)

        relatorio.append(linha_relatorio)

    # 7. Salvar Relatório
    df_relatorio = pd.DataFrame(relatorio)
    arq_relatorio = RELATORIO_DIR / f"relatorio_depositos_{aba_str}_{datetime.now().strftime('%H%M%S')}.xlsx"
    df_relatorio.to_excel(arq_relatorio, index=False)

    print(f"\n✅ Relatório salvo em: {arq_relatorio}")
    print("Resumo:")
    print(df_relatorio["Status"].value_counts().to_string())

    if houve_falha_rede_ou_http:
        return EXIT_RETRYABLE
    return EXIT_OK


@log_execution(modulo="Depósitos UDI")
def main(data_str: str, is_dry_run: bool = False, forcar_reenvio: bool = False) -> int:
    rc = executar(data_str, is_dry_run=is_dry_run, forcar_reenvio=forcar_reenvio)
    if rc in (EXIT_RETRYABLE, EXIT_PERMANENT):
        raise RuntimeError(f"Execução de Depósitos finalizada com código de erro {rc}.")
    return rc


if __name__ == "__main__":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Automação de Lançamento de Depósitos")
    parser.add_argument("--data", type=str, default=None, help="Data do depósito (DD.MM.YYYY ou DD/MM/YYYY)")
    parser.add_argument("--dry-run", help="Executa todo o cálculo, mas não envia nada para a API", action="store_true")
    parser.add_argument("--forcar-reenvio", help="Ignora trava de duplicidade e reenvia depósitos do dia", action="store_true")
    parser.add_argument("--dias", type=int, default=None, help="Parâmetro opcional de compatibilidade com o Scheduler")

    args = parser.parse_args()

    if args.data:
        data_input = args.data.strip()
    elif sys.stdin and sys.stdin.isatty():
        hoje = datetime.now().strftime("%d.%m.%Y")
        data_input = input(f"📅 Informe a data para processar (DD.MM.YYYY) [Enter = {hoje}]: ").strip() or hoje
    else:
        data_input = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")

    try:
        exit_code = main(data_input, is_dry_run=args.dry_run, forcar_reenvio=args.forcar_reenvio)
        sys.exit(exit_code)
    except Exception:
        sys.exit(EXIT_RETRYABLE)
