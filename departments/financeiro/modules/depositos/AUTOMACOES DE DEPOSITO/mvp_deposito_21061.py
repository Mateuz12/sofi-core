"""
MVP - Lançamento de Depósito via API
=====================================
Loja de teste: 21061 - CENTER SH

Este script solicita no terminal:
  1. Valor do depósito
  2. Data do depósito (DD/MM/AAAA)
  3. Data do crédito (DD/MM/AAAA)

E envia o lançamento para a API do portal financeiro.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

import requests

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
# ============================================================
# DADOS FIXOS DA LOJA 21061 - CENTER SH
# ============================================================

LOJA = {
    "codigo": 21061,
    "nome": "CENTER SH",
    "conta_origem": "5cf569d0955f602ab43d2c31",
    "conta_destino": "5cf56826c2d57a0a6067d6c2",
    "empresa_id": "5cf57096955f602ab43d5d68",
}


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "output" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

API_URL = os.getenv(
    "DEPOSITOS_API_URL",
    "https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/"
)

# TODO: Neste script o AUTHORIZATION e COOKIE eram passados via .env, 
# se ele for usado no futuro, deve importar capturar_token.py
AUTHORIZATION = os.getenv("AUTHORIZATION", "")
COOKIE = os.getenv("COOKIE", "")

# ============================================================
# LOGGING
# ============================================================

data_log = datetime.now().strftime("%Y%m%d")
log_file = LOG_DIR / f"mvp_deposito_{data_log}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def exibir_cabecalho():
    print("=" * 60)
    print("  AUTOMAÇÃO DE DEPÓSITOS - MVP")
    print("  Loja de Teste: 21061 - CENTER SH")
    print("=" * 60)
    print()


def solicitar_valor() -> float:
    """Solicita o valor do depósito ao usuário."""
    while True:
        entrada = input("💰 Digite o VALOR do depósito (ex: 1500.50): R$ ").strip()
        # Aceita vírgula como separador decimal
        entrada = entrada.replace(",", ".")
        try:
            valor = float(entrada)
            if valor <= 0:
                print("   ⚠️  O valor precisa ser maior que zero.\n")
                continue
            return valor
        except ValueError:
            print("   ⚠️  Valor inválido. Use apenas números (ex: 1500.50 ou 1500,50).\n")


def solicitar_data(label: str) -> datetime:
    """Solicita uma data ao usuário no formato DD/MM/AAAA."""
    while True:
        entrada = input(f"📅 Digite a {label} (DD/MM/AAAA): ").strip()
        try:
            data = datetime.strptime(entrada, "%d/%m/%Y")
            return data
        except ValueError:
            print("   ⚠️  Data inválida. Use o formato DD/MM/AAAA (ex: 07/05/2026).\n")


def formatar_data_api(data: datetime) -> str:
    """Formata a data para o padrão esperado pela API."""
    return data.strftime("%Y-%m-%dT03:00:00.000Z")


def montar_headers() -> dict:
    """Monta os headers de autenticação."""
    headers = {"Content-Type": "application/json"}

    if AUTHORIZATION:
        headers["Authorization"] = AUTHORIZATION
    if COOKIE:
        headers["Cookie"] = COOKIE

    return headers


def construir_payload(valor: float, data_deposito: datetime, data_credito: datetime) -> dict:
    """Constrói o payload para a API baseado nos dados da loja 21061."""
    return {
        "_id": None,
        "ContaOrigem": LOJA["conta_origem"],
        "ContaDestino": LOJA["conta_destino"],
        "Data": formatar_data_api(data_deposito),
        "DataDoCredito": formatar_data_api(data_credito),
        "Descricao": f"Depósito para CC em {data_deposito.strftime('%d/%m/%Y')}",
        "EmpresaId": LOJA["empresa_id"],
        "NomeContaDestino": None,
        "NomeContaOrigem": f"CAIXA LOJA - {LOJA['codigo']} - {LOJA['nome']}",
        "Valor": valor,
        "errors": [],
    }


def enviar_deposito(payload: dict, headers: dict, tentativas: int = 3) -> dict:
    """Envia o depósito para a API com retry."""
    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):
        try:
            logger.info(f"Tentativa {tentativa}/{tentativas} de envio...")

            response = requests.post(
                API_URL,
                json=payload,
                headers=headers,
                timeout=30,
                allow_redirects=False,
            )

            # Redirect = autenticação expirada/inválida
            if response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = response.headers.get("Location", "desconhecido")
                logger.error(f"Redirect detectado ({response.status_code}) → {redirect_url}")
                return {
                    "status": "autenticacao_invalida",
                    "status_code": response.status_code,
                    "erro": (
                        f"A API retornou redirect ({response.status_code}). "
                        "Isso indica que o token/cookie no .env está expirado ou inválido. "
                        "Capture novos valores no DevTools do navegador (F12 → Network)."
                    ),
                }

            if response.status_code in [200, 201]:
                try:
                    resposta_json = response.json()
                except Exception:
                    resposta_json = {"resposta_texto": response.text}

                errors = resposta_json.get("errors", [])

                if not errors:
                    return {
                        "status": "sucesso",
                        "status_code": response.status_code,
                        "resposta": resposta_json,
                    }

                return {
                    "status": "erro_negocio",
                    "status_code": response.status_code,
                    "erros": errors,
                    "resposta": resposta_json,
                }

            ultimo_erro = f"HTTP {response.status_code}: {response.text[:500]}"
            logger.warning(f"Tentativa {tentativa}/{tentativas} falhou: {ultimo_erro}")

        except Exception as erro:
            ultimo_erro = str(erro)
            logger.warning(f"Tentativa {tentativa}/{tentativas} gerou exceção: {ultimo_erro}")

        if tentativa < tentativas:
            espera = 2 ** tentativa
            logger.info(f"Aguardando {espera}s antes da próxima tentativa...")
            time.sleep(espera)

    return {
        "status": "falha_comunicacao",
        "status_code": None,
        "erro": ultimo_erro,
    }


# ============================================================
# FLUXO PRINCIPAL
# ============================================================

@log_execution(modulo="Depósitos (MVP 21061)")
def main():
    limpar_tela()
    exibir_cabecalho()

    # --- Verificar credenciais ---
    headers = montar_headers()

    placeholders = ["COLE_SEU_TOKEN_AQUI", "COLE_SEU_COOKIE_AQUI"]
    auth_val = headers.get("Authorization", "")
    cookie_val = headers.get("Cookie", "")

    tem_auth = auth_val and not any(p in auth_val for p in placeholders)
    tem_cookie = cookie_val and not any(p in cookie_val for p in placeholders)

    if not tem_auth and not tem_cookie:
        print("⛔ ATENÇÃO: Nenhum token ou cookie VÁLIDO configurado no .env!")
        print()
        print("   Para capturar suas credenciais:")
        print("   1. Abra o portal no Chrome e faça login")
        print("   2. Pressione F12 → aba Network")
        print("   3. Faça um depósito manual no portal")
        print("   4. Encontre a requisição 'RealizarDeposito'")
        print("   5. Copie os headers Authorization e/ou Cookie")
        print("   6. Cole no arquivo .env")
        print()
        input("Pressione ENTER para sair...")
        sys.exit(1)

    # --- Coleta de dados ---
    valor = solicitar_valor()
    print()
    data_deposito = solicitar_data("DATA DO DEPÓSITO")
    print()
    data_credito = solicitar_data("DATA DO CRÉDITO")
    print()

    # --- Montagem do payload ---
    payload = construir_payload(valor, data_deposito, data_credito)

    # --- Confirmação ---
    print("-" * 60)
    print("  RESUMO DO LANÇAMENTO")
    print("-" * 60)
    print(f"  Loja:            {LOJA['codigo']} - {LOJA['nome']}")
    print(f"  Valor:           R$ {valor:,.2f}")
    print(f"  Data Depósito:   {data_deposito.strftime('%d/%m/%Y')}")
    print(f"  Data Crédito:    {data_credito.strftime('%d/%m/%Y')}")
    print(f"  Descrição:       {payload['Descricao']}")
    print("-" * 60)
    print()

    confirmacao = input("✅ Confirmar envio? (S/N): ").strip().upper()

    if confirmacao != "S":
        print("\n❌ Lançamento cancelado pelo usuário.")
        logger.info("Lançamento cancelado pelo usuário.")
        input("\nPressione ENTER para sair...")
        return

    # --- Envio ---
    print()
    logger.info(f"Iniciando envio de depósito para loja {LOJA['codigo']} - {LOJA['nome']}")
    logger.info(f"Valor: R$ {valor:,.2f} | Depósito: {data_deposito.strftime('%d/%m/%Y')} | Crédito: {data_credito.strftime('%d/%m/%Y')}")
    logger.info(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    resultado = enviar_deposito(payload, headers)

    # --- Resultado ---
    print()
    print("=" * 60)

    if resultado["status"] == "sucesso":
        print("  ✅ DEPÓSITO LANÇADO COM SUCESSO!")
        logger.info(f"Sucesso! Resposta: {resultado.get('resposta')}")
    elif resultado["status"] == "erro_negocio":
        print("  ⚠️  ERRO DE NEGÓCIO RETORNADO PELA API")
        print(f"  Erros: {resultado.get('erros')}")
        logger.error(f"Erro de negócio: {resultado.get('erros')}")
    else:
        print("  ❌ FALHA NO ENVIO DO DEPÓSITO")
        print(f"  Erro: {resultado.get('erro')}")
        logger.error(f"Falha de comunicação: {resultado.get('erro')}")

    print(f"  Status Code: {resultado.get('status_code')}")
    print("=" * 60)
    print()

    input("Pressione ENTER para sair...")


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Execução interrompida pelo usuário.")
        sys.exit(0)
    except Exception as erro:
        logger.exception(f"Erro crítico na execução: {erro}")
        input("\nPressione ENTER para sair...")
        sys.exit(1)
