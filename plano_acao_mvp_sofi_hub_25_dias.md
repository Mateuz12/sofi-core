# Plano de Ação — MVP SOFI Hub em 25 dias

## Objetivo da entrega

Entregar uma primeira versão funcional do **SOFI Hub**, acessível pelo time financeiro, com:

- interface web simples;
- módulos principais organizados;
- botões para execução das automações;
- histórico de execução;
- logs de erro/sucesso;
- documentação técnica;
- documentação de uso;
- repositório oficial da empresa;
- estrutura preparada para futura integração com o Sage.

A entrega deve ser apresentada como:

> **Primeira versão operacional e documentada do SOFI Hub.**

E não como um sistema finalizado.

---

## Objetivos estratégicos

Este plano tem três objetivos principais:

1. **Entregar um SOFI Hub funcional em até 25 dias**
2. **Reduzir a dependência técnica concentrada em uma pessoa**
3. **Preparar o projeto para futuramente ser acessado pelo Sage**

A ideia central é transformar o SOFI de um conjunto de automações pessoais em um **ativo corporativo documentado, versionado e utilizável pelo financeiro**.

---

## Stack recomendada para o MVP

Para os primeiros 25 dias, a stack recomendada é:

- **Python** — para manter e reaproveitar os scripts atuais;
- **Streamlit** — para criar uma interface rápida e funcional;
- **SQLite** — para logs e histórico de execução;
- **GitHub da empresa** — para versionamento e repositório oficial;
- **`.env`** — para credenciais, caminhos e variáveis sensíveis;
- **Servidor interno ou ambiente aprovado pelo TI** — para hospedagem.

> O Streamlit deve funcionar apenas como camada visual.  
> A lógica das automações deve ficar separada em módulos, permitindo futura migração para FastAPI ou integração com o Sage.

---

## Estrutura sugerida do repositório

```text
sofi-hub/
├── README.md
├── CHANGELOG.md
├── .gitignore
├── .env.example
├── requirements.txt
│
├── dashboard/
│   ├── app.py
│   ├── pages/
│   │   ├── 01_inicio.py
│   │   ├── 02_modulos.py
│   │   ├── 03_historico.py
│   │   ├── 04_status.py
│   │   └── 05_documentacao.py
│   └── assets/
│
├── modules/
│   ├── relatorios/
│   │   ├── service.py
│   │   └── README.md
│   ├── emails_vd/
│   │   ├── service.py
│   │   └── README.md
│   ├── extratos/
│   │   ├── service.py
│   │   └── README.md
│   ├── depositos/
│   │   ├── service.py
│   │   └── README.md
│   ├── concilia/
│   │   ├── service.py
│   │   └── README.md
│   └── xml/
│       ├── service.py
│       └── README.md
│
├── core/
│   ├── config.py
│   ├── logger.py
│   ├── executor.py
│   ├── database.py
│   └── paths.py
│
├── data/
│   └── sofi_logs.db
│
├── docs/
│   ├── manual_usuario.md
│   ├── manual_tecnico.md
│   ├── instalacao.md
│   ├── troubleshooting.md
│   └── arquitetura.md
│
├── outputs/
└── tests/
```

---

## Padrão técnico dos módulos

O dashboard não deve conter a lógica pesada da automação.  
Ele deve apenas chamar funções dos módulos.

Cada módulo deve seguir um padrão semelhante:

```python
def executar_modulo(params: dict) -> dict:
    return {
        "status": "sucesso",
        "mensagem": "Execução finalizada",
        "arquivos_gerados": [],
        "tempo_execucao": "00:02:15"
    }
```

Cada módulo precisa:

- ter uma função principal;
- receber parâmetros de forma clara;
- retornar status padronizado;
- registrar log;
- não depender de caminhos fixos;
- ter documentação própria.

---

# Fase 0 — Alinhamento com TI e diretoria

## Prazo: 1 dia

Antes de hospedar qualquer coisa, alinhar com TI e diretoria:

- onde o SOFI pode rodar;
- se pode usar GitHub;
- se será GitHub da empresa, organização própria ou outro Git interno;
- se pode usar servidor externo;
- se precisa ser servidor interno;
- quem terá acesso;
- se o Sage poderá futuramente ter botão para abrir o Hub;
- se o acesso inicial pode ser por link interno;
- como serão tratadas credenciais e dados sensíveis.

Frase sugerida:

> Antes de hospedar qualquer coisa, quero alinhar com o TI qual ambiente é aprovado para o SOFI, porque ele vai lidar com dados e rotinas financeiras.

---

# Fase 1 — Fundação técnica e governança

## Dias 1 a 5

### Dia 1 — Criar repositório oficial

Entregas:

- Criar repositório oficial da empresa.
- Subir estrutura inicial de pastas.
- Criar `README.md`.
- Criar `.gitignore`.
- Criar `.env.example`.
- Criar `requirements.txt`.

O `README.md` inicial deve conter:

- O que é o SOFI.
- Objetivo do Hub.
- Módulos existentes.
- Status de cada módulo.
- Como instalar.
- Como rodar localmente.
- Contatos/responsáveis.
- Aviso de que credenciais reais não ficam no repositório.

### Dia 2 — Padronizar variáveis e caminhos

Entregas:

- Remover caminhos fixos dos scripts.
- Criar `core/config.py`.
- Criar `.env`.
- Criar `.env.example`.
- Configurar `python-dotenv`.
- Padronizar caminhos de entrada e saída.

Exemplo de `.env.example`:

```env
SOFI_ENV=development
DOWNLOADS_PATH=
OUTPUTS_PATH=
LOG_DB_PATH=

PORTAL_USER=
PORTAL_PASSWORD=

EMAIL_HOST=
EMAIL_USER=
EMAIL_PASSWORD=
```

> O arquivo `.env` real nunca deve ser enviado para o GitHub.

### Dia 3 — Teste técnico antecipado do servidor

Esse teste deve acontecer cedo porque Playwright e automações de navegador podem apresentar problemas em servidor Linux.

Entregas:

- Subir ambiente simples de teste.
- Instalar Python.
- Instalar dependências.
- Instalar Playwright.
- Testar abertura de navegador headless.
- Testar download simples.
- Testar permissões de pasta.

Objetivo:

> Descobrir cedo se o servidor pode travar a entrega.

Se houver problema, ainda haverá tempo para ajustar o plano.

### Dia 4 — Criar logging centralizado

Entregas:

- Criar `core/logger.py`.
- Criar banco SQLite.
- Criar tabela de logs.
- Fazer todo módulo registrar início, fim, erro e sucesso.

Tabela mínima sugerida:

```text
execucoes
├── id
├── modulo
├── status
├── mensagem
├── usuario
├── inicio_em
├── fim_em
├── tempo_execucao
└── detalhes_erro
```

Essa etapa é essencial para governança, auditoria e rastreabilidade.

### Dia 5 — Refatorar módulos principais

Selecionar os módulos mais importantes para o MVP.

Prioridade inicial:

1. **SOFI Relatórios**
2. **SOFI Emails VD**
3. **SOFI Extratos**

Se houver tempo:

4. **SOFI Depósitos**
5. **SOFI Concilia**

Cada módulo precisa:

- ter uma função principal;
- retornar status;
- registrar log;
- não depender de caminho fixo;
- ter `README.md` próprio.

---

# Fase 2 — Interface do SOFI Hub

## Dias 6 a 12

### Dia 6 — Criar dashboard base

Criar app Streamlit com navegação:

- Início;
- Módulos;
- Histórico;
- Status;
- Documentação.

A tela inicial deve mostrar:

- Nome do SOFI.
- Resumo do sistema.
- Módulos disponíveis.
- Últimos processos executados.
- Status geral.

### Dias 7 e 8 — Página de módulos

Cada módulo deve aparecer como um card.

Informações do card:

- Nome do módulo.
- Descrição.
- Status.
- Última execução.
- Botão **Executar**.
- Botão **Ver documentação**.

Exemplo:

```text
SOFI Relatórios
Baixa, processa e importa relatórios financeiros dos portais.
Última execução: 15/05/2026 08:14
Status: Sucesso
[Executar]
```

Ao clicar em executar:

- Chamar `executar_modulo()`.
- Mostrar progresso.
- Salvar log.
- Mostrar resultado final.

### Dia 9 — Página de histórico

Mostrar logs do SQLite.

Colunas:

- Módulo;
- Data;
- Status;
- Mensagem;
- Tempo de execução;
- Usuário.

Filtros:

- Por módulo;
- Por data;
- Por sucesso/erro.

Essa página é essencial para mostrar rastreabilidade.

### Dia 10 — Página de status geral

Mostrar visão consolidada do SOFI.

Indicadores:

- Módulos que rodaram hoje.
- Últimos erros.
- Tempo médio de execução.
- Quantidade de processos executados.
- Alertas pendentes.
- Arquivos gerados.

### Dia 11 — Página de documentação

Dentro do Hub, incluir links para:

- Manual do usuário;
- Manual técnico;
- Documentação por módulo;
- Troubleshooting;
- Histórico de versões.

### Dia 12 — Ajuste visual

Aplicar identidade visual do SOFI.

Diretrizes:

- Interface limpa.
- Cards por módulo.
- Botões claros.
- Mensagens simples.
- Cores alinhadas à identidade do projeto.
- Usabilidade acima de estética.

---

# Fase 3 — Documentação e institucionalização

## Dias 13 a 17

### Dia 13 — Manual do usuário

Criar documento simples para o time financeiro.

Estrutura sugerida:

```text
Manual do Usuário — SOFI Hub

1. Como acessar
2. Como executar um módulo
3. Como consultar histórico
4. Como identificar erro
5. O que fazer se falhar
6. Onde ficam os arquivos gerados
7. Quem acionar em caso de problema
```

Esse manual deve ser escrito para usuários do financeiro, não para programadores.

### Dia 14 — Manual técnico

Criar documento para TI ou futuro responsável técnico.

Estrutura sugerida:

```text
Manual Técnico — SOFI Hub

1. Arquitetura geral
2. Tecnologias usadas
3. Estrutura de pastas
4. Variáveis de ambiente
5. Como instalar
6. Como rodar
7. Como adicionar novo módulo
8. Como consultar logs
9. Como dar manutenção
10. Pontos críticos
```

Esse documento responde diretamente à preocupação de continuidade do projeto.

### Dia 15 — Documentação por módulo

Para cada módulo, criar um `README.md`.

Estrutura sugerida:

```text
Nome do módulo:
Objetivo:
Entrada:
Saída:
Portais envolvidos:
Credenciais necessárias:
Frequência de uso:
Passo a passo técnico:
Possíveis erros:
Como corrigir:
```

Começar pelos módulos principais.

### Dia 16 — Criar changelog e padrão de versão

Criar `CHANGELOG.md`.

Exemplo:

```text
# Changelog SOFI

## v0.1.0 — MVP inicial
- Criação do repositório
- Estrutura base do Hub
- Módulos Relatórios, Emails VD e Extratos
- Logging em SQLite
- Documentação inicial
```

### Dia 17 — Revisão de governança

Checklist:

- `.env` real não subiu.
- Senhas não estão no código.
- Logs funcionam.
- Documentação existe.
- Repositório está organizado.
- Nomes de pastas fazem sentido.
- Outro usuário consegue entender o básico.

---

# Fase 4 — Servidor e acesso interno

## Dias 18 a 22

### Dia 18 — Definir hospedagem com TI

Definir onde o SOFI Hub será hospedado.

Opções possíveis:

1. Servidor interno;
2. VM da empresa;
3. VPS aprovada;
4. Máquina dedicada temporária;
5. Ambiente Docker.

> Evitar decidir sozinho por servidor externo sem aprovação, porque o SOFI lida com dados financeiros.

### Dia 19 — Configurar ambiente

Instalar/configurar:

- Python;
- Git;
- Dependências do projeto;
- Playwright, se necessário;
- Variáveis de ambiente;
- Pastas de saída;
- Permissões.

### Dia 20 — Subir SOFI Hub

Rodar Streamlit no servidor.

Exemplo:

```bash
streamlit run dashboard/app.py --server.port 8501
```

Se possível, configurar para rodar como serviço.

### Dia 21 — Testar acesso

Testes:

- Acesso de outra máquina;
- Execução de módulo;
- Gravação de logs;
- Arquivos gerados;
- Permissões;
- Erros de navegador/Playwright;
- Tempo de resposta.

### Dia 22 — Plano B se servidor travar

Se Playwright ou o servidor travar, não comprometer toda a entrega.

Plano B:

- Hub roda no servidor;
- Algumas automações ficam inicialmente em modo assistido;
- Execução local controlada enquanto o TI ajusta ambiente;
- Logs e documentação continuam funcionando;
- A entrega continua válida como MVP operacional e documentado.

---

# Fase 5 — Teste com usuário real e entrega

## Dias 23 a 25

### Dia 23 — Teste com alguém do financeiro

Escolher uma pessoa do financeiro para testar.

Testar:

- Acessar o Hub;
- Rodar módulo;
- Consultar histórico;
- Ler instruções;
- Abrir ou baixar arquivo gerado.

Anotar:

- Onde a pessoa travou;
- Quais textos não ficaram claros;
- Quais botões confundiram;
- Quais erros apareceram.

### Dia 24 — Ajustes finais

Corrigir:

- Textos;
- Botões;
- Mensagens de erro;
- Documentação;
- Visual;
- Logs;
- Fluxos quebrados.

### Dia 25 — Apresentação para Eduardo

Ordem sugerida da apresentação:

1. Repositório oficial;
2. Estrutura de pastas;
3. `.env.example`;
4. Documentação;
5. SOFI Hub funcionando;
6. Execução de um módulo;
7. Histórico de logs;
8. Manual do usuário;
9. Manual técnico;
10. Plano de próximos módulos.

Frase ideal:

> A entrega principal desses 25 dias não é só o Hub funcionando. É o SOFI começando a funcionar como ativo da empresa: organizado, documentado, versionado e utilizável pelo financeiro.

Evitar dizer:

> Se eu sair amanhã, está tudo aqui.

Melhor dizer:

> Com essa estrutura, a operação deixa de depender exclusivamente do meu conhecimento e passa a ter documentação, histórico e repositório oficial.

---

# O que NÃO tentar fazer nesses 25 dias

Evitar tentar:

- integrar diretamente no Sage;
- criar login corporativo completo;
- construir um sistema perfeito;
- automatizar todos os módulos de uma vez;
- resolver todo o financeiro;
- criar BI complexo;
- colocar inteligência preditiva;
- prometer que nunca vai dar erro.

O foco é:

> **MVP funcional + governança + documentação + uso real.**

---

# Entrega mínima aceitável

Se no dia 25 houver os itens abaixo, a entrega já será uma vitória:

- Repositório oficial criado;
- Scripts principais organizados;
- Dashboard funcionando;
- 3 módulos executáveis pelo Hub;
- Logs em SQLite;
- Documentação inicial;
- Manual de usuário;
- Manual técnico;
- Teste com pelo menos 1 pessoa do financeiro.

---

# Entrega ideal

Se tudo der certo, a entrega ideal inclui:

- Hub rodando em servidor;
- Acesso por link interno;
- 4 ou 5 módulos integrados;
- Histórico completo;
- Status geral;
- Documentação por módulo;
- Financeiro testando;
- Plano para botão no Sage.

---

# Como explicar o plano para o diretor

Mensagem sugerida:

```text
Eduardo, organizei uma proposta de próximo passo para o SOFI.

Minha sugestão é trabalhar em um ciclo de 25 dias para entregar uma primeira versão operacional do SOFI Hub, com os principais módulos centralizados, interface de uso para o financeiro, histórico de execução, documentação inicial e repositório oficial da empresa.

O objetivo dessa primeira etapa não é entregar um sistema final, mas transformar o SOFI em um ativo corporativo: organizado, documentado, versionado e utilizável por outras pessoas do financeiro.

Também vou alinhar a parte de hospedagem com o TI, para garantir que o ambiente esteja adequado e seguro.
```

---

# Resumo final

```text
Dias 1–5: Repositório, estrutura, .env, logs e teste técnico de servidor
Dias 6–12: Dashboard SOFI Hub
Dias 13–17: Documentação e governança
Dias 18–22: Hospedagem e testes técnicos
Dias 23–25: Teste com usuário real, ajustes e apresentação
```

Este plano entrega rápido, mas sem irresponsabilidade técnica.

Ele mostra que o SOFI não é mais uma automação pessoal.  
Ele começa a virar uma **estrutura oficial da empresa**.
