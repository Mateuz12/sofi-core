# Implementação do Relatório Detalhado por PDV (VD Captação) no Módulo XML

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o novo relatório "Nota fiscal Detalhado" no módulo XML do domínio Financeiro gerando 1 planilha por PDV (foco inicial em VD Captação: 20844 e 13793) com itens/SKUs, integrado ao pipeline semanal e executável standalone, e registrar a nova convenção corporativa de nomenclatura e pastas no vault Obsidian (`overview.md`).

**Architecture:** Módulo Python desacoplado (`gerador_relatorio_detalhado.py`) que processa os XMLs SEFAZ da semana extraindo itens (`<det>` -> `<cProd>`, `<qCom>`) vinculados ao cabeçalho da NF-e (`<nNF>`, `<dhEmi>`, `<dest><CNPJ>` -> PDV), gerando planilhas `.xlsx` formatadas via `openpyxl` na pasta dedicada `RELATÓRIOS DETALHADOS` e integrado automaticamente ao final da execução de `gerador_relatorio.py`. Atualização da documentação no vault Obsidian em `00_SYSTEM/overview.md`.

**Tech Stack:** Python 3.10+, `xml.etree.ElementTree` / `lxml`, `openpyxl`, `unittest` / `pytest`, Obsidian Markdown.

**Spec / Documentos do Vault Consultados:**
- `obsidian/00_SYSTEM/overview.md`
- `obsidian/00_SYSTEM/conventions.md`
- `obsidian/01_DOMAINS/dominio_financeiro.md`
- `obsidian/01_DOMAINS/modulo_xml.md`

## Global Constraints

- Cabeçalhos da planilha estritamente na Linha 1, começando na Coluna A: `['Numero da Nota', 'Codigo', 'Emissao', 'SKU', 'Quantidade']`.
- Quantidade numérica: inteiros como `int`, decimais como `float`.
- Uma linha por item (`<det>`), sem agrupamento por SKU.
- PDVs padrão: `['20844', '13793']` (configurável para extensão futura).
- Nomenclatura do arquivo: `13-PUB.XML.VD.CAPTACAO.<PDV>.NOTA FISCAL DETALHADO.<SEMANA>.xlsx`.
- Diretório de saída: `T:\13-Publica\XMLS CÁLAMO\RELATÓRIOS DETALHADOS\<ANO>\<MÊS>\<SEMANA>\` (fallback local em `Relatórios Cálamo Detalhado`).
- Regra de Acoplamento Zero: importar apenas dependências do próprio módulo XML ou de `core/`.
- Preservar integridade de processos COM e arquivos existentes.
- Atualizar a nova regra de nomenclatura corporativa e árvore de diretórios no `obsidian/00_SYSTEM/overview.md`.

---

### Task 1: Extrator de Itens de NF-e para Relatório Detalhado

**Files:**
- Create: `tests/financeiro/test_leitor_itens_xml.py`
- Modify: `departments/financeiro/modules/xml/leitor_xml.py`

**Interfaces:**
- Produces: `extrair_itens_xml(caminho_xml_ou_conteudo)` -> `List[Dict[str, Any]]` com chaves: `n_doc`, `pdv`, `dt_emissao`, `sku`, `quantidade`.

- [ ] **Step 1: Escrever teste unitário para extração de itens de XML**
  Criar `tests/financeiro/test_leitor_itens_xml.py` testando extração com XML sintético com múltiplos itens `<det>`, tags com e sem namespace SEFAZ (`nfe:det` e `det`), verificação de tipos numéricos e data formatada.

- [ ] **Step 2: Executar teste e validar falha**
  Executar `python -m unittest tests/financeiro/test_leitor_itens_xml.py` e verificar `ImportError` ou `AttributeError` indicando ausência de `extrair_itens_xml`.

- [ ] **Step 3: Implementar função `extrair_itens_xml` em `leitor_xml.py`**
  Implementar a função que lê `<infNFe>`, extrai `nNF`, `dhEmi`, `CNPJ` destinatário (mapeando para PDV via `LOJAS_MAP_DINAMICO` ou fallback de CNPJ limpo), e itera sobre cada `<det>` capturando `cProd` e `qCom`.

- [ ] **Step 4: Executar testes unitários e garantir aprovação**
  Executar `python -m unittest tests/financeiro/test_leitor_itens_xml.py` e garantir 100% de sucesso.

---

### Task 2: Gerador de Planilhas Detalhadas por PDV (`gerador_relatorio_detalhado.py`)

**Files:**
- Create: `tests/financeiro/test_gerador_relatorio_detalhado.py`
- Create: `departments/financeiro/modules/xml/gerador_relatorio_detalhado.py`

**Interfaces:**
- Consumes: `extrair_itens_xml` de `leitor_xml.py`
- Produces: `gerar_planilhas_detalhadas(lista_xmls_ou_pasta, diretorio_saida_base, semana_str, pdvs_alvo=['20844', '13793'])` -> `Dict[str, str]` (mapa `pdv -> caminho_arquivo_gerado`)

- [ ] **Step 1: Escrever teste unitário para geração da planilha openpyxl**
  Testar criação do arquivo `.xlsx`, presença dos cabeçalhos na linha 1 colunas A-E, dados preenchidos corretamente, larguras ajustadas, e nome do arquivo respeitando a regra `13-PUB.XML.VD.CAPTACAO.<PDV>.NOTA FISCAL DETALHADO.<SEMANA>.xlsx`.

- [ ] **Step 2: Executar teste e validar falha**
  Executar `python -m unittest tests/financeiro/test_gerador_relatorio_detalhado.py` e validar falha inicial.

- [ ] **Step 3: Implementar `gerador_relatorio_detalhado.py`**
  Construir o módulo contendo:
  - Resolução canônica de raiz e `@log_execution`.
  - Função `salvar_planilha_pdv(pdv, itens, caminho_saida)`.
  - Função principal `processar_relatorios_detalhados(...)` com suporte a CLI (`--pasta`, `--pdvs`, `--semana`).
  - Fallback automático para diretório local se unidade de rede `T:` não estiver acessível.

- [ ] **Step 4: Executar testes unitários e validar aprovação**
  Executar `python -m unittest tests/financeiro/test_gerador_relatorio_detalhado.py`.

---

### Task 3: Integração no Pipeline Semanal (`gerador_relatorio.py`)

**Files:**
- Modify: `departments/financeiro/modules/xml/gerador_relatorio.py`
- Create/Modify: `tests/financeiro/test_integracao_gerador_detalhado.py`

**Interfaces:**
- Consumes: `gerador_relatorio_detalhado.processar_relatorios_detalhados`
- Disparado dentro de: `gerar_relatorio_calamo()` em `gerador_relatorio.py` logo após ou em conjunto com a organização das pastas semanais.

- [ ] **Step 1: Criar teste de integração para a chamada do relatório detalhado**
  Validar que quando `gerador_relatorio.py` processa uma lista de notas/arquivos XML, a geração dos relatórios detalhados é acionada para os PDVs configurados.

- [ ] **Step 2: Modificar `gerador_relatorio.py`**
  Adicionar a chamada para `processar_relatorios_detalhados` dentro do fluxo de `gerar_relatorio_calamo()`, passando os caminhos de XMLs e a estrutura temporal da semana calculada (`ano_pasta`, `mes_pasta`, `semana_pasta`).

- [ ] **Step 3: Executar testes de integração**
  Executar `python -m unittest discover -s tests/financeiro` e verificar que todas as etapas passam.

---

### Task 4: Atualização no Vault Obsidian com a Nova Regra de Nomenclatura e Pastas

**Files:**
- Modify: `obsidian/00_SYSTEM/overview.md`
- Modify: `obsidian/00_SYSTEM/conventions.md`
- Modify: `obsidian/01_DOMAINS/modulo_xml.md`

- [ ] **Step 1: Atualizar `obsidian/00_SYSTEM/overview.md`**
  Adicionar a seção "📐 Padrão Corporativo de Nomenclatura e Estrutura de Diretórios" documentando:
  - Formato canônico de nomenclatura: `[COD_DEPT]-[ABREV_DEPT].[SETOR].[PROJETO_OU_TEMA].[UNIDADE].[NOME_DO_RELATORIO].[DATA_OU_PERIODO].[ext]`
  - Hierarquia de pastas: `<COD_DEPT>-<DEPARTAMENTO> / <SETOR> / <PROJETO> / <UNIDADE> / <ANO> / <MÊS> /`
  - Exemplos da foto 1 e foto 2 (Marketing Eventos) e do Módulo XML (Financeiro).
- [ ] **Step 2: Sincronizar `conventions.md` e `modulo_xml.md`**
  Registrar a convenção em `conventions.md` e atualizar as saídas em `modulo_xml.md` adicionando o novo relatório "Nota fiscal Detalhado (VD Captação - PDVs 20844 e 13793)".

---

### Task 5: Verificação Completa e Lembrança do Vault

- [ ] **Step 1: Rodar suíte completa de testes de validação**
  Verificar que nenhum arquivo existente quebrou e que os novos relatórios são gerados perfeitamente.
- [ ] **Step 2: Notificar o Lindão sobre a conclusão e lembrar da atualização manual do vault**
  Conforme Regra do `AGENTS.md`: "Lembra de atualizar o vault desse módulo antes de fechar."
