# 📐 Convenções e Padrões de Engenharia do SOFI

Este documento define os padrões mandatórios de desenvolvimento, arquitetura e documentação para todo desenvolvedor ou agente de IA que atuar no ecossistema SOFI.

---

## 1. Padrões de Código Python

### 1.1 Resolução Canônica da Raiz do Projeto
Todo script executável ou módulo deve resolver dinamicamente o diretório raiz do repositório para inclusão no `sys.path`, permitindo execução tanto via CLI na pasta do script quanto pelo orquestrador central:

```python
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
```

### 1.2 Hierarquia de Carregamento de Ambiente (`sofi_env`)
É proibido ler diretamente arquivos `.env` com bibliotecas genéricas sem passar pelo carregador central:

```python
from core.sofi_env import load_sofi_env

# Carrega o .env global da raiz e sobrescreve com departments/<dept>/.env.local (se existir)
load_sofi_env(department="financeiro")
```

### 1.3 Registro de Logs e Auditoria (`@log_execution`)
Toda rotina principal (`main()`) deve ser decorada para captura de `stdout`/`stderr` e gravação no banco SQLite:

```python
from core.database.logger import log_execution

@log_execution(modulo="NomeDoModulo")
def main():
    print("Log formatado que será gravado no SQLite e exibido no console")
```

### 1.4 Padrão de Exit Codes para Jobs do Scheduler
Todo script executado de forma agendada deve expressar explicitamente sua condição de término via `sys.exit()`:

```python
import sys

EXIT_OK              = 0  # Sucesso total
EXIT_RETRYABLE       = 1  # Falha transitória (cabe retry automático pelo scheduler)
EXIT_PERMANENT       = 2  # Falha irreversível (sem retry)
EXIT_SEM_FATURAMENTO = 3  # Execução normal sem dados no dia

if __name__ == "__main__":
    try:
        main()
        sys.exit(EXIT_OK)
    except TimeoutError:
        sys.exit(EXIT_RETRYABLE)
    except Exception as err:
        sys.exit(EXIT_PERMANENT)
```

### 1.5 Regra de Acoplamento Zero entre Departamentos
- Pastas dentro de `departments/` representam unidades funcionais isoladas.
- **Proibido:** `import departments.financeiro...` dentro de `departments/compras/` ou vice-versa.
- **Permitido:** Módulos de departamento importam utilitários compartilhados de `core/`.

---

## 2. Padrões de Automação Web (Playwright / Selenium)

### 2.1 Stealth Anti-Bot
Scripts que interagem com os portais do Grupo Boticário (FinançasGB, Extranet, Retaguarda) devem adotar as rotinas de camuflagem padronizadas em `departments/financeiro/modules/importar_financas.py`:
- Injeção de `STEALTH_INIT_SCRIPT` (remoção de `navigator.webdriver`, simulação de `plugins` e `languages`).
- Configuração de `REALISTIC_USER_AGENT`.
- Uso de `browser_args()` com desativação de recursos de automação visíveis (`--disable-blink-features=AutomationControlled`).

### 2.2 Tratamento de Telas de Onboarding e Popups
Portais corporativos sofrem injeção recorrente de ferramentas de feedback (Maze, Zendesk) e modais de onboarding. Os scripts devem sempre prever blocos de captura silenciosa e fechamento desses elementos antes de iniciar ações em formulários.

---

## 3. Padrões de Automação Windows COM (Excel e Outlook)

- **Microsoft Excel:** Toda automação que utiliza `win32com.client` deve instanciar uma nova aplicação via `win32com.client.DispatchEx('Excel.Application')` e garantir o fechamento explícito (`workbook.Close()`, `excel.Quit()`) dentro de blocos `finally`, evitando processos fantasmas bloqueando arquivos na rede.
- **Microsoft Outlook:** Leitura de caixas de entrada deve ser somente leitura, sem exclusão destrutiva de e-mails, salvando cópia dos anexos com tratamento de nomes e conversão de formato quando exigido pelo Oracle.

---

## 4. Convenções do Vault Obsidian

### 4.1 Wikilinks Válidos e Significativos
- Utilize a sintaxe `[[nome_do_documento]]` apenas para representar relações conceituais, fluxos de dados ou dependências reais.
- Evite criar wikilinks para termos genéricos sem intenção de documentação.

### 4.2 Classificação Epistemológica Obrigatória
Ao redigir documentação arquitetural, respeite rigorosamente as categorias:
- **FATO:** Evidenciado diretamente em código-fonte, configurações ativas ou arquivos de dados.
- **INFERÊNCIA:** Dedução arquitetural lógica razoável sustentada pelo código.
- **NÃO DETERMINADO:** Quando uma regra ou motivo não puder ser comprovado, declarar explicitamente:
  > *Não determinado pelo código/documentação disponível.*

---

## 5. Padrões de Nomenclatura de Arquivos e Estrutura de Diretórios na Rede

Para todas as automações e relatórios corporativos gerados pelo ecossistema SOFI, deve-se seguir rigorosamente a especificação definida em `[[overview]]`:
- **Nomenclatura Canônica:** `[COD_DEPT]-[ABREV_DEPT].[SETOR].[PROJETO_OU_TEMA].[UNIDADE].[NOME_DO_RELATÓRIO].[DATA_OU_PERÍODO].[ext]`
  - Exemplo diário: `08-MKT.EVENTOS.ENERGIZATT.BH.PLANILHA DE ORÇAMENTOS.01-08-2025.xlsx`
  - Exemplo semanal: `13-PUB.XML.VD.CAPTACAO.20844.NOTA FISCAL DETALHADO.Semana 01-08 a 07-08.xlsx`
- **Árvore de Diretórios:** `<COD_DEPT>-<DEPARTAMENTO>/<SETOR>/<PROJETO>/<UNIDADE>/<ANO>/<MÊS_FORMATADO>/`

