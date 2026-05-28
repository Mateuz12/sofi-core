"""
Automação de Lançamento de Depósitos em Lote - Uberlândia
=========================================================

Lê os depósitos de uma aba da planilha de fechamento na rede,
confronta com o cadastro de lojas (lojas.xlsx),
calcula a data de crédito e envia para a API usando o token do Playwright.
"""

import os
import sys
import io
import json
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Garante que o terminal do Windows aceite emojis/UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import requests

# Importa a função de captura de token feita no Playwright
from capturar_token import capturar_autenticacao

# ============================================================
# CONFIGURAÇÕES DE DIRETÓRIO E ARQUIVOS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "output" / "logs"
RELATORIO_DIR = BASE_DIR / "output" / "relatorios"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RELATORIO_DIR.mkdir(parents=True, exist_ok=True)

# Carrega o .env global do SOFI + .env.local do departamento
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

# URLs e Caminhos
API_URL = os.getenv("DEPOSITOS_API_URL", "https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/")
ARQUIVO_REDE = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\CONTROLE DE DEPÓSITO\UDI\2026\05-FIN.FECHAMENTO DE CAIXA.CONTROLE DE DEPÓSITO.UDI.2026.PLANILHA DE ACOMPANHAMENTO DE DEPÓSITOS LOJAS - VD.xlsx"
ARQUIVO_LOJAS = BASE_DIR / "lojas.xlsx"


# ============================================================
# LÓGICA DE DATAS DE CRÉDITO
# ============================================================

def calcular_credito_padrao(data_deposito: datetime) -> datetime:
    dia_semana = data_deposito.weekday() # 0 = Seg, 6 = Dom
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
        sys.exit(1)
        
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

def ler_planilha_rede(data_str: str) -> list:
    """
    Lê a planilha da rede na aba referente à data informada.
    Extrai apenas a Tabela 1 (Uberlândia).
    Retorna uma lista de dicionários com os depósitos válidos.
    """
    print(f"Lendo aba '{data_str}' do arquivo: {ARQUIVO_REDE}")
    try:
        # Tenta ler apenas a aba com o nome da data
        df = pd.read_excel(ARQUIVO_REDE, sheet_name=data_str, header=None)
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

def executar(data_str: str, is_dry_run: bool):
    # 1. Parse da data base
    try:
        data_deposito = datetime.strptime(data_str, "%d.%m.%Y")
    except ValueError:
        print("❌ Data inválida. Use o formato DD.MM.YYYY")
        sys.exit(1)
        
    print(f"--- INICIANDO PROCESSAMENTO: DATA {data_str} ---")
    if is_dry_run:
        print("⚠️ MODO DRY-RUN: Nenhum dado será enviado para a API.")

    # 2. Carregar configurações
    cadastro_lojas = ler_cadastro_lojas()
    
    # 3. Ler planilha
    dados_planilha = ler_planilha_rede(data_str)
    if not dados_planilha:
        print("Nenhum dado para processar. Encerrando.")
        return
        
    # 4. Capturar token se não for dry-run
    bearer, cookie = None, None
    if not is_dry_run:
        print("\n--- CAPTURANDO TOKEN DE AUTENTICAÇÃO ---")
        bearer, cookie = capturar_autenticacao()
        if not bearer or not cookie:
            print("❌ Falha ao capturar token. Encerrando.")
            sys.exit(1)
            
    headers = {
        "Content-Type": "application/json",
        "Authorization": bearer if bearer else "",
        "Cookie": cookie if cookie else ""
    }
    
    # 5. Processamento e montagem dos Payloads
    relatorio = []
    
    for item in dados_planilha:
        codigo = item["codigo"]
        valor = item["valor"]
        
        linha_relatorio = {
            "Data Depósito": data_str,
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
            
        linha_relatorio["Regra Crédito"] = regra
        linha_relatorio["Data Crédito"] = dt_credito.strftime("%d.%m.%Y")
        
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
            # Pequena pausa entre requisições
            time.sleep(1)
            
        relatorio.append(linha_relatorio)

    # 6. Salvar Relatório
    df_relatorio = pd.DataFrame(relatorio)
    arq_relatorio = RELATORIO_DIR / f"relatorio_depositos_{data_str}_{datetime.now().strftime('%H%M%S')}.xlsx"
    df_relatorio.to_excel(arq_relatorio, index=False)
    
    print(f"\n✅ Relatório salvo em: {arq_relatorio}")
    print("Resumo:")
    print(df_relatorio["Status"].value_counts())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automação de Lançamento de Depósitos")
    parser.add_argument("--dry-run", help="Executa todo o cálculo, mas não envia nada para a API", action="store_true")
    
    args = parser.parse_args()
    
    hoje = datetime.now().strftime("%d.%m.%Y")
    data_input = input(f"📅 Informe a data para processar (DD.MM.YYYY) [Enter = {hoje}]: ").strip()
    
    if not data_input:
        data_input = hoje
    
    executar(data_input, args.dry_run)
