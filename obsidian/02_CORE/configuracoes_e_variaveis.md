---
tipo: arquitetura
sistema: config_manager
status: producao
atualizado: 2026-09-11
dominio: core_configuracoes
---

# ⚙️ Central de Configurações Dinâmicas e Governança do SOFI

> **Documento Arquitetural Vivo:** Mapeamento de fontes da verdade, domínios de configuração, ciclo de vida de hot-reload e impacto direto em cada automação do SOFI-core.

---

## 🏛️ 1. Princípios Arquiteturais

A camada de configurações dinâmicas foi projetada com base nos seguintes requisitos estritos de engenharia:

1. **Separação por Domínio (Redução de Blast Radius):** Em vez de concentrar todas as variáveis em um único arquivo sujeito a falhas em cascata, o sistema divide suas configurações em três arquivos YAML especializados dentro do diretório `config/`:
   - `config/scheduler.yaml`: Horários, flags de ativação, retries e rotinas do APScheduler.
   - `config/notificacoes.yaml`: Grupos de e-mail e regras de roteamento SMTP por processo.
   - `config/parametros_negocio.yaml`: Prazos de pagamento por PDV e regras mercadológicas/financeiras.

2. **Escrita Atômica Real:** Todo salvamento grava primeiramente em arquivo temporário (`.tmp`) e executa a substituição definitiva via `os.replace()`, imune a quedas de energia ou interrupções de processo no filesystem NTFS.

3. **Lock de Concorrência:** Cada domínio possui seu próprio arquivo `.lock` operado pela biblioteca `filelock`, impedindo *race conditions* entre múltiplas threads ou sessões simultâneas do Streamlit.

4. **Transação com Rollback Automático:** No caso do Scheduler, se o salvamento do arquivo suceder mas a aplicação em memória (`reload_scheduler_jobs`) falhar, o YAML é imediatamente revertido ao backup anterior e o erro é reportado à interface.

5. **Trilha de Auditoria Granular:** As alterações não são gravadas em bloco. Um analisador de diff recursivo (`core.config.diff`) identifica cada chave alterada e registra pontualmente no SQLite (`configuration_audit_logs`) com: data/hora, usuário logado, domínio, chave pontuada, valor anterior e valor novo.

6. **Retenção Automática de Backups:** A cada modificação é gerado um backup versionado em `config/backups/`, com expiração automática FIFO que preserva os últimos 30 backups por domínio.

---

## 🗺️ 2. Mapeamento de Variáveis e Impacto Operacional

| Arquivo | Chave / Parâmetro | Tipo | Módulos Impactados | Impacto no Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `scheduler.yaml` | `jobs[].enabled` | `bool` | `core/scheduler/scheduler.py` | Ativa ou desativa a execução automática do robô. |
| `scheduler.yaml` | `jobs[].schedule.hour` / `minute` | `int` | `core/scheduler/scheduler.py` | Determina o horário de disparo matinal da rotina. |
| `scheduler.yaml` | `jobs[].dias` | `int` | Extratores DFC, Retaguarda, Extranet | Dias retroativos para consulta de faturamento/vendas. |
| `scheduler.yaml` | `jobs[].retry.max_attempts` | `int` | `run_job` (Subprocess) | Quantidade de tentativas antes de considerar falha permanente. |
| `notificacoes.yaml` | `grupos.retaguarda.emails` | `list[EmailStr]` | `core/notifier/smtp_notifier.py` | Destinatários dos relatórios consolidados de Retaguarda e DFC. |
| `notificacoes.yaml` | `grupos.xml_retaguarda.emails` | `list[EmailStr]` | `core/notifier/smtp_notifier.py` | Destinatários dos relatórios de conferência de notas fiscais de entrada. |
| `notificacoes.yaml` | `grupos.extranet.emails` | `list[EmailStr]` | `core/notifier/smtp_notifier.py` | Destinatários dos relatórios de vendas Extranet BH e UDI. |
| `parametros_negocio.yaml` | `prazos_pagamento.default` | `int` | `gerador_relatorio.py` (Cálamo) | Prazo padrão (dias) para PDVs sem regra individual cadastrada. |
| `parametros_negocio.yaml` | `prazos_pagamento.<PDV>` | `int` | `gerador_relatorio.py` (Cálamo) | Regra customizada de vencimento (ex: 21274=0, 13793=60, 20844=45). |

---

## 🖥️ 3. Interface da Torre de Controle (NOC)

A gestão dessas variáveis ocorre visualmente no portal Streamlit através da rota dedicada:
`http://localhost:8501/torre_controle`

### Painel Executivo (Header)
Exibe cartões com métricas das últimas 24 horas consolidadas diretamente do SQLite (`execution_logs`):
- **Status do Agendador:** Indicador de execução com próximo horário previsto.
- **Taxa de Sucesso:** Total de execuções nas últimas 24h discriminadas em sucessos versus falhas.
- **Próximo Disparo:** Próximo job a ser executado e horário estimado.

### Abas Operacionais
1. **Agendamentos & Jobs:** Formulário com checkboxes de ativação, seleção de horários (`st.time_input`), dias e retries, com proteção contra duplo clique e aplicação imediata.
2. **Notificações & Alertas:** Áreas de texto com validação RFC (`pydantic.EmailStr`) para distribuição dos relatórios por departamento.
3. **Prazos PDV:** Tabela dinâmica editável para ajuste de prazos comerciais de todas as 43 lojas de UDI e BH.
4. **Auditoria & YAML Raw:** Grade histórica com as últimas 50 alterações de variáveis e visualizador de código com syntax-highlighting.

---

## ⚠️ 4. Dívida Técnica Rastreata

> [!WARNING]
> **AUTH-001 — Controle de Acesso e Permissões**
> Na versão atual (v1), o acesso à Torre de Controle não requer credenciais ou token, sendo protegido unicamente pelo perímetro da rede interna corporativa. Está planejado para a v2 a implementação de controle de acesso por perfil (administrador vs. operador) via `st.session_state` e `secrets.toml`.
