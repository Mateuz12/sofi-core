# Plano de Ação – Automação de Lançamento de Depósitos via API HTTP

## 1. Objetivo do Projeto

Criar uma automação para realizar, diariamente, o lançamento de depósitos em um portal financeiro por meio de requisições HTTP diretamente na API utilizada pelo sistema.

A automação deverá ler os dados necessários dos depósitos, montar o payload correto para cada loja e enviar as requisições para o endpoint de lançamento, reduzindo trabalho manual, diminuindo risco de erro operacional e gerando rastreabilidade por meio de logs e relatórios.

---

## 2. Contexto

Atualmente, o lançamento dos depósitos é feito manualmente no portal.

Durante a análise do portal, foi identificado que o sistema utiliza uma API para realizar o lançamento dos depósitos. A requisição possui um payload com informações como:

- Conta de origem
- Conta de destino
- Data do depósito
- Data do crédito
- Descrição
- Empresa
- Nome da conta de origem
- Valor do depósito

Como os dados necessários já foram levantados, o próximo passo é estruturar a automação em formato de script.

---

## 3. Endpoint Identificado

```http
POST https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/
```

Esse endpoint será utilizado para enviar os lançamentos de depósito.

---

## 4. Exemplo de Payload Base

```json
{
  "_id": null,
  "ContaOrigem": "6699063f60701d773569cee7",
  "ContaDestino": "5cf56826c2d57a0a6067d6c2",
  "Data": "2026-05-04T03:00:00.000Z",
  "DataDoCredito": "2026-05-06T03:00:00.000Z",
  "Descricao": "Depósito para CC em 04/05/2026",
  "EmpresaId": "66990ab816070463395ee860",
  "NomeContaDestino": null,
  "NomeContaOrigem": "CAIXA LOJA - 23263 - CENTRO - TPC",
  "Valor": 1115,
  "errors": []
}
```

---

## 5. Campos do Payload

| Campo | Tipo | Descrição | Obrigatório |
|---|---:|---|---|
| `_id` | null/string | Identificador do lançamento. Para novo lançamento, enviar como `null`. | Sim |
| `ContaOrigem` | string | ID da conta/loja de origem do depósito. | Sim |
| `ContaDestino` | string | ID da conta de destino. | Sim |
| `Data` | string | Data do depósito em formato ISO. | Sim |
| `DataDoCredito` | string | Data em que o crédito será considerado. | Sim |
| `Descricao` | string | Texto descritivo do lançamento. | Sim |
| `EmpresaId` | string | ID da empresa vinculada ao lançamento. | Sim |
| `NomeContaDestino` | null/string | Nome da conta de destino. Pode ser enviado como `null`. | Não |
| `NomeContaOrigem` | string | Nome da loja/conta de origem. | Sim |
| `Valor` | number | Valor do depósito. | Sim |
| `errors` | array | Lista de erros. Para envio inicial, enviar como lista vazia. | Sim |

---

## 6. Dados Necessários para a Automação

Como os dados necessários já foram obtidos, a automação deverá trabalhar com duas bases principais.

### 6.1 Cadastro de Lojas

Arquivo sugerido:

```ojas.xlsx
```

Colunas recomendadas:

| coluna | descrição |
|---|---|
| `codigo_loja` | Código interno da loja, caso exista. |
| `NomeContaOrigem` | Nome da loja/conta de origem. |
| `ContaOrigem` | ID da conta de origem. |
| `ContaDestino` | ID da conta de destino. |
| `EmpresaId` | ID da empresa. |

Exemplo:

| codigo_loja | NomeContaOrigem | ContaOrigem | ContaDestino | EmpresaId |
|---:|---|---|---|---|
| 23263 | CAIXA LOJA - 23263 - CENTRO - TPC | 6699063f60701d773569cee7 | 5cf56826c2d57a0a6067d6c2 | 66990ab816070463395ee860 |

---

### 6.2 Arquivo de Depósitos do Dia

Arquivo sugerido:

```text
input/depositos_YYYY-MM-DD.xlsx
```

Colunas recomendadas:

| coluna | descrição |
|---|---|
| `codigo_loja` ou `ContaOrigem` | Identificador para relacionar o depósito à loja. |
| `Valor` | Valor do depósito a ser lançado. |

Exemplo usando `codigo_loja`:

| codigo_loja | Valor |
|---:|---:|
| 23263 | 1115.00 |

Exemplo usando `ContaOrigem`:

| ContaOrigem | Valor |
|---|---:|
| 6699063f60701d773569cee7 | 1115.00 |

---

## 7. Estrutura Recomendada de Pastas

```text
automacao_depositos/
│
├── config/
│   └── lojas.xlsx
│
├── input/
│   └── depositos_2026-05-07.xlsx
│
├── output/
│   ├── logs/
│   └── relatorios/
│
├── script_depositos.py
├── requirements.txt
└── README.md
```

---

## 8. Bibliotecas Necessárias

Arquivo `requirements.txt`:

```txt
requests
pandas
openpyxl
python-dotenv
```

Instalação:

```bash
pip install -r requirements.txt
```

---

## 9. Segurança e Autenticação

A autenticação da API provavelmente dependerá de headers capturados no navegador, como:

- `Authorization`
- `Cookie`
- `Content-Type`
- Possíveis tokens de sessão

### 9.1 Recomendação de Segurança

Não deixar tokens, cookies ou senhas fixos diretamente no código.

Usar um arquivo `.env`:

```env
API_URL=https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/
AUTHORIZATION=Bearer SEU_TOKEN_AQUI
COOKIE=SEU_COOKIE_AQUI
```

No script, carregar esses dados com `python-dotenv`.

---

## 10. Fluxo Geral da Automação

```text
1. Iniciar script
2. Carregar configurações e credenciais
3. Carregar cadastro de lojas
4. Carregar arquivo de depósitos do dia
5. Validar colunas obrigatórias
6. Cruzar depósitos com cadastro de lojas
7. Filtrar depósitos com valor maior que zero
8. Montar payload de cada loja
9. Enviar requisição POST para a API
10. Registrar sucesso ou erro de cada envio
11. Gerar relatório final em Excel
12. Encerrar execução
```

---

## 11. Regras de Negócio

### 11.1 Lançar apenas valores positivos

O script deve ignorar linhas com:

- Valor vazio
- Valor igual a zero
- Valor negativo
- Valor inválido

### 11.2 Evitar duplicidade

Antes de enviar em produção, é importante validar se a API permite lançamentos duplicados.

Medidas recomendadas:

- Gerar log de tudo que foi enviado.
- Criar uma chave de controle com `ContaOrigem + Data + Valor`.
- Não reenviar automaticamente um lançamento que já consta no log como sucesso.
- Ter um modo de teste antes do envio real.

### 11.3 Datas

A data deve seguir o padrão esperado pela API:

```text
YYYY-MM-DDT03:00:00.000Z
```

Exemplo:

```text
2026-05-04T03:00:00.000Z
```

A descrição pode ser gerada automaticamente:

```text
Depósito para CC em DD/MM/YYYY
```

---

## 12. Script Base

```python
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from dotenv import load_dotenv


# ============================================================
# CONFIGURAÇÕES INICIAIS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_DIR = BASE_DIR / "config"
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = OUTPUT_DIR / "logs"
RELATORIO_DIR = OUTPUT_DIR / "relatorios"

for pasta in [CONFIG_DIR, INPUT_DIR, OUTPUT_DIR, LOG_DIR, RELATORIO_DIR]:
    pasta.mkdir(parents=True, exist_ok=True)

load_dotenv()

API_URL = os.getenv(
    "API_URL",
    "https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/"
)

AUTHORIZATION = os.getenv("AUTHORIZATION")
COOKIE = os.getenv("COOKIE")


# ============================================================
# LOGGING
# ============================================================

data_log = datetime.now().strftime("%Y%m%d")
log_file = LOG_DIR / f"depositos_{data_log}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


# ============================================================
# HEADERS
# ============================================================

def montar_headers() -> dict:
    headers = {
        "Content-Type": "application/json"
    }

    if AUTHORIZATION:
        headers["Authorization"] = AUTHORIZATION

    if COOKIE:
        headers["Cookie"] = COOKIE

    return headers


# ============================================================
# CARGA DE DADOS
# ============================================================

def carregar_lojas() -> pd.DataFrame:
    caminho = CONFIG_DIR / "lojas.xlsx"

    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de lojas não encontrado: {caminho}")

    df = pd.read_excel(caminho)

    colunas_obrigatorias = [
        "ContaOrigem",
        "ContaDestino",
        "EmpresaId",
        "NomeContaOrigem"
    ]

    for coluna in colunas_obrigatorias:
        if coluna not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente no cadastro de lojas: {coluna}")

    return df


def encontrar_arquivo_depositos() -> Path:
    hoje = datetime.now().strftime("%Y-%m-%d")
    caminho = INPUT_DIR / f"depositos_{hoje}.xlsx"

    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de depósitos do dia não encontrado: {caminho}")

    return caminho


def carregar_depositos() -> pd.DataFrame:
    caminho = encontrar_arquivo_depositos()
    df = pd.read_excel(caminho)

    if "Valor" not in df.columns:
        raise ValueError("Arquivo de depósitos precisa conter a coluna 'Valor'.")

    if "ContaOrigem" not in df.columns and "codigo_loja" not in df.columns:
        raise ValueError("Arquivo de depósitos precisa conter 'ContaOrigem' ou 'codigo_loja'.")

    return df


# ============================================================
# TRATAMENTO E INTEGRAÇÃO
# ============================================================

def integrar_dados(lojas: pd.DataFrame, depositos: pd.DataFrame) -> pd.DataFrame:
    if "ContaOrigem" in depositos.columns:
        df = pd.merge(lojas, depositos, on="ContaOrigem", how="inner")
    else:
        if "codigo_loja" not in lojas.columns:
            raise ValueError(
                "Para cruzar por codigo_loja, o cadastro de lojas também precisa ter a coluna 'codigo_loja'."
            )

        df = pd.merge(lojas, depositos, on="codigo_loja", how="inner")

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    df = df.dropna(subset=["Valor"])
    df = df[df["Valor"] > 0]

    return df


# ============================================================
# PAYLOAD
# ============================================================

def formatar_data_api(data: datetime) -> str:
    return data.strftime("%Y-%m-%dT03:00:00.000Z")


def construir_payload(row: pd.Series, data_deposito: datetime, data_credito: datetime) -> dict:
    return {
        "_id": None,
        "ContaOrigem": str(row["ContaOrigem"]),
        "ContaDestino": str(row["ContaDestino"]),
        "Data": formatar_data_api(data_deposito),
        "DataDoCredito": formatar_data_api(data_credito),
        "Descricao": f"Depósito para CC em {data_deposito.strftime('%d/%m/%Y')}",
        "EmpresaId": str(row["EmpresaId"]),
        "NomeContaDestino": None,
        "NomeContaOrigem": str(row["NomeContaOrigem"]),
        "Valor": float(row["Valor"]),
        "errors": []
    }


# ============================================================
# ENVIO PARA API
# ============================================================

def enviar_deposito(payload: dict, headers: dict, tentativas: int = 3) -> dict:
    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):
        try:
            response = requests.post(
                API_URL,
                json=payload,
                headers=headers,
                timeout=30
            )

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
                        "resposta": resposta_json
                    }

                return {
                    "status": "erro_negocio",
                    "status_code": response.status_code,
                    "erros": errors,
                    "resposta": resposta_json
                }

            ultimo_erro = f"HTTP {response.status_code}: {response.text[:500]}"
            logger.warning(f"Tentativa {tentativa}/{tentativas} falhou: {ultimo_erro}")

        except Exception as erro:
            ultimo_erro = str(erro)
            logger.warning(f"Tentativa {tentativa}/{tentativas} gerou exceção: {ultimo_erro}")

        if tentativa < tentativas:
            time.sleep(2 ** tentativa)

    return {
        "status": "falha_comunicacao",
        "status_code": None,
        "erro": ultimo_erro
    }


# ============================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================

def processar():
    logger.info("Iniciando automação de lançamento de depósitos.")

    headers = montar_headers()

    if not headers.get("Authorization") and not headers.get("Cookie"):
        logger.warning("Nenhum Authorization ou Cookie foi carregado. Verifique o arquivo .env.")

    lojas = carregar_lojas()
    depositos = carregar_depositos()

    df_envio = integrar_dados(lojas, depositos)

    if df_envio.empty:
        logger.warning("Nenhum depósito válido encontrado para envio.")
        return

    data_deposito = datetime.now(timezone.utc)
    data_credito = data_deposito + timedelta(days=2)

    resultados = []

    logger.info(f"Total de depósitos para envio: {len(df_envio)}")

    for _, row in df_envio.iterrows():
        payload = construir_payload(row, data_deposito, data_credito)

        nome_loja = row["NomeContaOrigem"]
        valor = row["Valor"]

        logger.info(f"Enviando depósito | Loja: {nome_loja} | Valor: R$ {valor:.2f}")

        resultado = enviar_deposito(payload, headers)

        registro = {
            "data_execucao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "NomeContaOrigem": nome_loja,
            "ContaOrigem": row["ContaOrigem"],
            "ContaDestino": row["ContaDestino"],
            "EmpresaId": row["EmpresaId"],
            "Valor": valor,
            "status": resultado.get("status"),
            "status_code": resultado.get("status_code"),
            "erro": resultado.get("erro"),
            "erros_negocio": str(resultado.get("erros")),
            "payload": str(payload),
            "resposta": str(resultado.get("resposta"))
        }

        resultados.append(registro)

        if resultado.get("status") == "sucesso":
            logger.info(f"Sucesso | Loja: {nome_loja}")
        else:
            logger.error(f"Falha | Loja: {nome_loja} | Resultado: {resultado}")

    salvar_relatorio(resultados)

    logger.info("Automação finalizada.")


# ============================================================
# RELATÓRIO
# ============================================================

def salvar_relatorio(resultados: list):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = RELATORIO_DIR / f"relatorio_depositos_{timestamp}.xlsx"

    df = pd.DataFrame(resultados)
    df.to_excel(caminho, index=False)

    logger.info(f"Relatório salvo em: {caminho}")


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    try:
        processar()
    except Exception as erro:
        logger.exception(f"Erro crítico na execução: {erro}")
        sys.exit(1)
```

---

## 13. Arquivo `.env`

Criar um arquivo chamado `.env` na pasta principal do projeto:

```env
API_URL=https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/
AUTHORIZATION=Bearer COLE_SEU_TOKEN_AQUI
COOKIE=COLE_SEU_COOKIE_AQUI_SE_NECESSARIO
```

Caso a API funcione apenas com cookie de sessão, preencher o campo `COOKIE`.

Caso funcione com token Bearer, preencher `AUTHORIZATION`.

Caso use os dois, preencher ambos.

---

## 14. Modo de Teste Recomendado

Antes de rodar para todas as lojas, criar uma versão de teste com apenas uma loja no arquivo de depósitos.

### Checklist de teste

- [ ] A planilha `lojas.xlsx` está preenchida corretamente.
- [ ] A planilha de depósitos do dia está na pasta `input`.
- [ ] O arquivo `.env` possui token/cookie válido.
- [ ] O script roda sem erro de coluna.
- [ ] O payload gerado bate com o payload observado no navegador.
- [ ] A API retorna sucesso.
- [ ] O lançamento aparece corretamente no portal.
- [ ] O relatório é gerado na pasta `output/relatorios`.

---

## 15. Logs e Auditoria

A automação deve gerar dois tipos de registro:

### 15.1 Log técnico

Local:

```text
output/logs/
```

Exemplo:

```text
depositos_20260507.log
```

Esse arquivo deve conter:

- Data e hora da execução
- Quantidade de depósitos enviados
- Sucessos
- Falhas
- Erros de conexão
- Erros retornados pela API

### 15.2 Relatório operacional

Local:

```text
output/relatorios/
```

Exemplo:

```text
relatorio_depositos_20260507_090000.xlsx
```

Esse relatório deve conter:

- Loja
- Conta de origem
- Conta de destino
- Valor
- Status do envio
- Código HTTP
- Payload enviado
- Resposta da API
- Erros, se houver

---

## 16. Controle Contra Duplicidade

Para evitar lançamentos duplicados, implementar uma validação adicional em uma próxima versão.

Estratégia sugerida:

1. Criar uma coluna/chave única:
   ```text
   ContaOrigem + Data + Valor
   ```

2. Antes de enviar, consultar o histórico de relatórios anteriores.

3. Se a chave já tiver status `sucesso`, bloquear novo envio.

4. Criar um parâmetro de execução forçada apenas para casos excepcionais.

Exemplo de chave:

```text
6699063f60701d773569cee7_2026-05-07_1115.00
```

---

## 17. Agendamento da Automação

### 17.1 Windows

Usar o Agendador de Tarefas.

Programa:

```text
python
```

Argumentos:

```text
C:\caminho\automacao_depositos\script_depositos.py
```

Iniciar em:

```text
C:\caminho\automacao_depositos
```

Horário sugerido:

```text
09:00
```

### 17.2 Linux

Usar `cron`:

```bash
0 9 * * * cd /home/usuario/automacao_depositos && /usr/bin/python3 script_depositos.py
```

---

## 18. Possíveis Problemas e Soluções

| Problema | Possível causa | Solução |
|---|---|---|
| Erro 401 | Token expirado | Atualizar token/cookie ou automatizar login |
| Erro 403 | Sessão sem permissão | Validar usuário logado e permissões |
| Erro 400 | Payload inválido | Comparar payload do script com payload real do navegador |
| Arquivo não encontrado | Nome da planilha diferente | Conferir padrão `depositos_YYYY-MM-DD.xlsx` |
| Loja não enviada | Falha no cruzamento dos dados | Validar `codigo_loja` ou `ContaOrigem` |
| Duplicidade | Script rodou mais de uma vez | Implementar controle por chave única |
| Timeout | API instável | Manter tentativas com retry e backoff |

---

## 19. Evoluções Futuras

### Versão 1.1

- Implementar modo teste/simulação.
- Gerar prévia dos payloads antes do envio.
- Criar validação contra duplicidade.
- Criar painel simples em interface gráfica.

### Versão 1.2

- Automatizar renovação de token/cookie.
- Integrar com e-mail para envio de relatório final.
- Adicionar notificação de falha crítica.

### Versão 2.0

- Transformar o script em um módulo dentro de um HUB de automações.
- Criar interface única para selecionar data, arquivo e executar o processo.
- Criar tela de histórico de execuções.
- Criar controle de permissões por usuário.

---

## 20. Critérios de Sucesso

O projeto será considerado concluído quando:

- [ ] O script ler corretamente o cadastro de lojas.
- [ ] O script ler corretamente os depósitos do dia.
- [ ] O script montar o payload conforme o padrão da API.
- [ ] O script enviar os depósitos para a API.
- [ ] O script registrar sucesso e erro por loja.
- [ ] O script gerar relatório final da execução.
- [ ] O processo for validado com uma loja.
- [ ] O processo for validado com todas as lojas.
- [ ] O processo puder ser executado de forma segura e repetível.

---

## 21. Próximos Passos Práticos

1. Criar a pasta do projeto.
2. Criar a estrutura de diretórios.
3. Criar o arquivo `requirements.txt`.
4. Criar o arquivo `.env`.
5. Criar a planilha `config/lojas.xlsx`.
6. Criar a planilha `input/depositos_YYYY-MM-DD.xlsx`.
7. Colar o script em `script_depositos.py`.
8. Rodar teste com uma loja.
9. Validar lançamento no portal.
10. Rodar teste com lote completo.
11. Implementar proteção contra duplicidade.
12. Agendar execução diária.

---

## 22. Observação Importante

Essa automação utiliza uma API interna observada pelo comportamento do portal. Por isso, é importante tratar o processo com cautela:

- Testar primeiro com poucos registros.
- Não expor credenciais.
- Registrar tudo em log.
- Validar com a empresa a melhor forma de armazenar e manter esse ativo.
- Documentar o funcionamento para que a automação não dependa apenas de uma pessoa.

---

## 23. Conclusão

A automação de lançamento de depósitos via HTTP request é viável e tende a ser mais rápida e direta do que uma automação visual via navegador, desde que os tokens, cookies e payloads sejam tratados corretamente.

Como os dados principais já foram obtidos, o foco agora deve ser:

1. Construir o script com segurança.
2. Validar o payload em ambiente real.
3. Criar logs e relatórios.
4. Prevenir duplicidade.
5. Integrar futuramente ao HUB de automações.

---

**Versão:** 1.0  
**Data:** 07/05/2026  
**Projeto:** Automação de Lançamento de Depósitos via API HTTP
