# Departamento Compras — SOFI

Agrupa todos os módulos e automações do setor de Compras.

## Estrutura

```
compras/
├── modules/
│   └── relatorio_mar/   # Gerador de Relatório MAR (migrado de RELATÓRIO_MAR/)
│       ├── extracao_mar.py
│       ├── extranet_reports.py
│       ├── main.py
│       ├── tratamento_mar.py
│       ├── build.py
│       └── templates/
├── dashboard/            # Dashboard do departamento (em desenvolvimento)
└── .env.local            # Variáveis exclusivas do compras
```

## Módulos

| Módulo | Descrição | Status |
|--------|-----------|--------|
| Relatório MAR | Extração e geração de relatórios de compras MAR | ✅ Ativo |
