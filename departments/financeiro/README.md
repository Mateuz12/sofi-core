# Departamento Financeiro — SOFI

Agrupa todos os módulos e automações do setor financeiro.

## Estrutura

```
financeiro/
├── modules/
│   ├── conciliacao_venda/   # Robôs de conciliação de vendas (Playwright)
│   ├── depositos/           # Automação de depósitos identificados
│   ├── emails_vd/           # Monitor e processador de e-mails de Venda Direta
│   ├── extranet/            # Extrator de relatórios da Extranet GB
│   ├── retaguarda/          # Extrator do Portal de Finanças GB (Retaguarda)
│   └── xml/                 # Leitor de XMLs e gerador de relatórios Cálamo
├── dashboard/               # Dashboard do departamento (em desenvolvimento)
└── .env.local               # Variáveis exclusivas do financeiro
```

## Como usar o `sofi_env`

Todo script deste departamento deve carregar o ambiente assim:

```python
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")
```

## Módulos Ativos

| Módulo | Descrição | Status |
|--------|-----------|--------|
| XML | Baixa XMLs via API MeuDanfe e gera relatórios Cálamo | ✅ Ativo |
| Retaguarda | Extrai relatórios financeiros do Portal GB | ✅ Ativo |
| Extranet | Integração com extranet de parceiros | ✅ Ativo |
| Emails VD | Monitor de e-mails de Venda Direta | ✅ Ativo |
| Depósitos | Automação de depósitos identificados | 🚧 Em desenvolvimento |
| Conciliação Venda | Validação cruzada de cartões e recebíveis | 🚧 Em desenvolvimento |
