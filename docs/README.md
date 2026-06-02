# SOFI — Sistema Operacional Financeiro Integrado

> Auxiliar corporativo autônomo — opera, importa, concilia e entrega processos automatizados por departamento, sem intervenção manual.

![Versão](https://img.shields.io/badge/vers%C3%A3o-2.2.0-45B57B?style=flat-square)
![Ambiente](https://img.shields.io/badge/ambiente-produção-45B57B?style=flat-square)
![Stack](https://img.shields.io/badge/stack-Python%20%7C%20Streamlit%20%7C%20Playwright-7CD884?style=flat-square)
![Status](https://img.shields.io/badge/status-ativo-45B57B?style=flat-square)

---

## Índice

- [Sobre o projeto](#sobre-o-projeto)
- [Resultados](#resultados)
- [Arquitetura](#arquitetura)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Departamentos e módulos](#departamentos-e-módulos)
- [Fluxo de dados](#fluxo-de-dados)
- [Configuração do ambiente](#configuração-do-ambiente)
- [Como rodar](#como-rodar)
- [Deploy no servidor](#deploy-no-servidor)
- [Roadmap](#roadmap)
- [Governança e documentação](#governança-e-documentação)

---

## Sobre o projeto

O SOFI nasceu como uma solução para eliminar o trabalho manual repetitivo do setor financeiro de uma empresa franqueada do Grupo Boticário (43 lojas, unidades UDI e BH). O que começou como automação de relatórios evoluiu para um **hub corporativo** que centraliza processos automatizados de múltiplos departamentos em uma única interface web.

O sistema é um **ativo da empresa** — totalmente documentado, versionado no repositório corporativo e independente de qualquer pessoa específica para operar.

---

## Novidades da Versão 2.2.0

Nesta atualização, o sistema passou por uma grande reformulação técnica e estética para unificar e alinhar o fluxo de processos:

### 🎨 Rebranding Visual (Padrão Sage)
- **Identidade Visual:** Alinhamento de cabeçalho e rodapé usando as cores padrão do sistema Sage:
  - Barra superior em azul `#1d87b3` (altura de 41px, fonte `PT Sans`, texto branco).
  - Barra inferior em azul `#268bb5` (texto branco).
- **Alinhamento de Layout:** Expansão da interface para a largura total da tela, com todo o conteúdo e títulos alinhados ao canto superior esquerdo da página.
- **Títulos minimalistas:** Ajustados para 14px bold minimalista no topo esquerdo, removendo as linhas decorativas antigas.
- **Cards de Módulos:** Redesenhados no tamanho exato de 425x138px, com `border-radius: 16px` e display flex horizontal (ícone à esquerda e nome em azul `rgb(42, 100, 150)` à direita).

### 🚀 Novas Funcionalidades (Novas Features)
- **Integração do Módulo Extranet (BH e UDI):** Operação dos scripts automáticos de extração de relatórios e de importação automática para o FinançasGB.
- **Módulo Retaguarda:** Página do Streamlit criada para gerenciar relatórios de vendas e conciliação integrando processos.
- **Módulo de Importação Financeira:** Utilitário `importar_financas.py` criado sob o departamento financeiro para otimizar os fluxos de arquivos locais/Oracle.
- **Banco de Dados e Console em Tempo Real:** Logs e histórico de execuções integrados com SQLite e exibidos na tela.

---

## Resultados

| Métrica | Antes | Depois |
|---|---|---|
| Tempo diário de geração de relatórios | 2h ~ 3h | 5 minutos |
| Redução de tempo operacional | — | **95%** |
| Atividades do Assistente Financeiro automatizadas | 0% | **80%** |
| Tempo de processamento de emails VD | Manual | **2 minutos automáticos** |
| Lojas com extrato processado automaticamente | 0 | **42 lojas** |

---

## Arquitetura

```
Usuário
  │
  ▼
Dashboard SOFI (Streamlit)
  │
  ├── Departamento: Financeiro
  │     ├── Módulos de coleta (Retaguarda, Emails VD, Extranet, Mooz, VD+)
  │     ├── Módulo de importação (pasta/diretório)
  │     └── Motor de conciliação (SOFI Concilia)
  │
  ├── Departamento: RH (em breve)
  │     └── Módulo de triagem de currículos
  │
  └── Departamento: Compras (em breve)
        └── Módulos a mapear
  │
  ▼
SQLite (logs + histórico de execuções)
  │
  ▼
Servidor Oracle (arquivos de saída via caminho de rede)
```

**Stack técnica:**

| Camada | Tecnologia |
|---|---|
| Interface | Streamlit |
| Automação de portais | Python + Playwright |
| Banco de logs | SQLite |
| Orquestração de workflows | N8N |
| Integrações | REST APIs (Bearer, Cookie, OAuth2) |
| Servidor | Windows Server dedicado (32GB RAM, i7 12ª gen) |
| Arquivos | Servidor Oracle via caminho de rede |
| Repositório | GitHub — organização corporativa |

---

## Estrutura de pastas

```
sofi-core/
│
├── core/                          # Utilitários compartilhados por todos os departamentos
│   ├── sofi_env.py                # Carregador centralizado de variáveis de ambiente
│   ├── logger.py                  # Logging centralizado
│   └── database/
│       └── sofi.db                # Banco SQLite de logs e histórico
│
├── departments/
│   │
│   ├── financeiro/                # Departamento Financeiro
│   │   ├── modules/
│   │   │   ├── extratos/          # Extrato das 21 lojas — Portal Mooz Cartões
│   │   │   ├── relatorios/        # Relatórios Retaguarda + Finanças GB
│   │   │   ├── depositos/         # Automação de depósitos
│   │   │   ├── emails_vd/         # 6 caixas VD (3 UDI + 3 BH)
│   │   │   ├── extranet/          # Vendas boleto, recebíveis, boletos a maior
│   │   │   ├── xml/               # Scripts de relatórios XML
│   │   │   └── concilia/          # Motor de conciliação financeira
│   │   ├── dashboard/             # Páginas do financeiro no Streamlit
│   │   ├── .env.local             # Credenciais exclusivas do financeiro
│   │   └── README.md
│   │
│   ├── rh/                        # Departamento RH (em breve)
│   │   ├── modules/
│   │   │   └── triagem/           # Sistema de triagem de currículos com IA
│   │   ├── dashboard/
│   │   ├── .env.local
│   │   └── README.md
│   │
│   └── compras/                   # Departamento Compras (em breve)
│       ├── modules/
│       ├── dashboard/
│       ├── .env.local
│       └── README.md
│
├── dashboard/                     # HUB principal — seleção de departamento
│   ├── app.py                     # Entry point do Streamlit
│   ├── pages/
│   │   ├── financeiro.py
│   │   ├── rh.py
│   │   └── compras.py
│   └── components/
│       └── navbar.py
│
├── .env                           # Credenciais compartilhadas — NUNCA subir pro GitHub
├── .env.example                   # Template com campos vazios — versionar normalmente
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Departamentos e módulos

### Financeiro

| Módulo | Descrição | Status | Portais |
|---|---|---|---|
| SOFI Extrato | Extrato das 21 lojas | ✅ Ativo | Mooz Cartões |
| SOFI Relatórios | Relatórios financeiros UDI e BH | ✅ Ativo | Retaguarda · Finanças GB |
| SOFI Emails VD | 6 caixas VD processadas ao receber | ✅ Ativo | Email corporativo |
| SOFI Depósitos | Lançamento e conferência de depósitos | ✅ Ativo | Finanças GB |
| SOFI Extranet | Boletos, recebíveis e boletos a maior | ✅ Ativo | Extranet |
| SOFI XML | Scripts de relatórios XML fiscais | ✅ Ativo | MeuDanfe API |
| SOFI Importa | Leitura automática de arquivos via pasta | ✅ Ativo | Local / Oracle |
| SOFI Concilia | Motor de conciliação financeira | 🔄 Em evolução | — |
| Pré Conciliação Bancária | Tratamento de dados bancários | 🔄 Em evolução | — |

### RH

| Módulo | Descrição | Status |
|---|---|---|
| Triagem de Currículos | Análise automatizada com IA + funil de candidatos | 🕐 Em breve |

### Compras

| Módulo | Descrição | Status |
|---|---|---|
| A mapear | Consolidação de relatórios e cálculos automáticos | 🕐 Em breve |

---

## Fluxo de dados

```
FONTES
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Extrato + VD   │  │   Relatórios    │  │    Importa      │
│  Mooz · 21 ljs  │  │  Retaguarda·GB  │  │ pasta/diretório │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         └───────────────────┬┴───────────────────┘
                             │ insumos para conciliação
                             ▼
                    PROCESSAMENTO
              ┌──────────────────────┐
              │     SOFI Concilia    │
              │  motor de conciliação│
              └──────────┬───────────┘
                         │ resultado consolidado
                         ▼
                      ENTREGA
              ┌──────────────────────┐
              │   Dashboard SOFI     │
              │ visão unificada      │
              │ alertas · relatórios │
              └──────────────────────┘
```

---

## Configuração do ambiente

### Pré-requisitos

- Python 3.10+
- pip
- Git
- Playwright (`playwright install chromium`)

### Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/[org-empresa]/sofi-core.git
cd sofi-core

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Instalar navegadores do Playwright
playwright install chromium

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Preencher .env com as credenciais reais
```

### Variáveis de ambiente

O SOFI usa um sistema de `.env` em dois níveis:

**`.env` central (raiz)** — credenciais compartilhadas entre departamentos:

```dotenv
# RETAGUARDA
RETAGUARDA_URL=https://cp10488.retaguarda.grupoboticario.com.br/
RETAGUARDA_USER=
RETAGUARDA_PASS=

# FINANÇAS GB — UDI
FINANCAS_URL=https://financasgb.grupoboticario.com.br/
FINANCAS_UDI_USER=
FINANCAS_UDI_PASS=

# FINANÇAS GB — BH
FINANCAS_BH_USER=
FINANCAS_BH_PASS=

# EXTRANET
EXTRANET_URL=https://extranet.grupoboticario.com.br/
EXTRANET_USER=
EXTRANET_PASSWORD=

# MOOZ CARTÕES
MOOZ_URL=
MOOZ_TOKEN=
MOOZ_COOKIE=

# CONFIGURAÇÕES DE BROWSER
HEADLESS=false
BROWSER_CHANNEL=chrome
DISABLE_HTTP2=true

# XML / NOTAS FISCAIS
CERT_PASSWORD=
MEUDANFE_API_KEY=

# DEPÓSITOS
DEPOSITOS_API_URL=https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/

# CAMINHOS
ORACLE_PATH=
LOCAL_OUTPUT_PATH=
LOG_DB_PATH=database/sofi.db

# GERAL
EMPRESA=
AMBIENTE=development
```

**`.env.local` por departamento** — credenciais exclusivas de cada setor, dentro de `departments/[dept]/`.

> ⚠️ **Nunca subir arquivos `.env` para o GitHub.** Apenas `.env.example` é versionado.

---

## Como rodar

```bash
# Rodar o dashboard completo
streamlit run dashboard/app.py

# Rodar um módulo específico isolado (exemplo)
cd departments/financeiro/modules/extratos
python extrato_mooz.py
```

O dashboard estará disponível em `http://localhost:8501`.

---

## Deploy no servidor

O SOFI roda no servidor Windows Server dedicado da empresa.

### Configurar como serviço Windows (NSSM)

```powershell
# Instalar NSSM
# Download: https://nssm.cc/download

# Registrar SOFI como serviço
nssm install SOFI python "-m streamlit run C:\sofi-core\dashboard\app.py --server.port 8501"
nssm start SOFI
```

O serviço inicia automaticamente com o servidor e reinicia em caso de falha.

### Acesso externo (Cloudflare Tunnel)

O acesso externo é gerenciado via **Cloudflare Tunnel** — sem abertura de portas no firewall da empresa.

```bash
# Instalar cloudflared no servidor
# Configurar tunnel apontando para localhost:8501
cloudflared tunnel --url http://localhost:8501
```

### Estrutura de arquivos no servidor

```
C:\sofi-core\          # repositório clonado
C:\sofi-core\.env      # credenciais reais (nunca no GitHub)
Z:\                    # servidor Oracle — saída de arquivos
```

---

## Roadmap

| Fase | Entrega | Prazo | Status |
|---|---|---|---|
| Fase 1 | Financeiro integrado — todos os módulos no dashboard | Concluído | ✅ |
| Fase 2 | BETA dashboard + triagem RH + mapeamento Contas a Pagar | 45 dias | 🔄 |
| Fase 3 | Expansão Compras e Controladoria | A definir | 🕐 |
| Fase 4 | Machine Learning preditivo — antecipar inconsistências | Longo prazo | 🕐 |

---

## Governança e documentação

O SOFI é um **ativo corporativo**, não uma dependência de pessoa.

### Regras obrigatórias

1. **Todo módulo entregue em produção precisa ter documentação** em `departments/[dept]/docs/`
2. **Nenhuma credencial real** sobe para o repositório — apenas `.env.example`
3. **Todo novo departamento** segue a estrutura padrão: `modules/` + `dashboard/` + `.env.local` + `README.md`
4. **Nenhum módulo importa de outro departamento** — código compartilhado vai para `core/`
5. **Commits com mensagens descritivas em português** — o histórico precisa ser legível por qualquer pessoa do TI

### Documentação por módulo

Cada módulo deve conter em seu diretório:

```
modulo/
├── README.md        # O que faz, de onde puxa dados, como manter
├── CHANGELOG.md     # Histórico de alterações
└── .env.example     # Variáveis necessárias para o módulo
```

### Em caso de falha

```bash
# Verificar status do serviço
nssm status SOFI

# Reiniciar serviço
nssm restart SOFI

# Ver logs do Streamlit
# Logs ficam em: C:\sofi-core\logs\
```

---

## Contribuição

Este repositório é de uso interno. Para adicionar um novo módulo ou departamento:

1. Cria a estrutura padrão em `departments/[novo_dept]/`
2. Documenta o módulo antes de abrir PR
3. Testa localmente antes de subir para `main`
4. Atualiza este README com o novo módulo

---

*SOFI v2.2.0 · Sistema Operacional Financeiro Integrado · Uso interno · 2026*
