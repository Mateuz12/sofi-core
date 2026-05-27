# Plano de Ação – Expansão da Automação de Depósitos

Este plano de ação organiza os próximos passos descritos no "Plano de Expansão" (v1.1) em fases estruturadas, facilitando a execução e o acompanhamento das atividades para a automação do lançamento de depósitos de todas as lojas.

---

## Fase 1: Planejamento e Configuração Inicial
*Preparar os arquivos, mapeamentos e configurações necessárias para iniciar o desenvolvimento.*

- [ ] **1.1. Ajustar o cadastro de lojas (`config/lojas.xlsx`):** Inserir todos os códigos das lojas, vinculando Conta Origem, Conta Destino, EmpresaId, NomeContaOrigem e a regra de crédito (`padrao` ou `especial_911557`).
- [ ] **1.2. Mapeamento da Planilha:** Confirmar o nome exato das abas e colunas (`DATA`, `Código`, `Loja`, `Depósito`) da planilha de fechamento de caixa (`input/fechamento_de_caixa.xlsx`).
- [ ] **1.3. Mapeamento de UI no Portal:** Inspecionar e documentar os seletores HTML (IDs, classes) da tela de login e o caminho completo de navegação até a tela de lançamento de depósito.
- [ ] **1.4. Mapeamento da API:** Identificar onde o ID do depósito teste retorna na requisição e mapear o endpoint exato e o payload necessário para a exclusão do depósito teste via API.
- [ ] **1.5. Configuração de Variáveis de Ambiente:** Criar a estrutura inicial do arquivo `.env` para receber futuramente credenciais estáticas, URLs de API e configuração da `LOJA_TESTE_CODIGO`.

---

## Fase 2: Autenticação Automática e Captura de Tokens (Playwright)
*Garantir que a automação consiga obter o Bearer Token e o Cookie de forma dinâmica e segura através da navegação na interface.*

- [ ] **2.1. Função de Login:** Desenvolver a função com `Playwright` que abre o portal em modo visível. O script vai preencher o e-mail (`//*[@id="email"]`) e senha (`//*[@id="input-button-icon-right"]`), e aguardar 10 segundos antes de clicar em Entrar (`//*[@id="login-root"]/div/div/div[2]/div/div/form/button`) para evitar captchas.
- [ ] **2.2. Navegação até Fechamento de Caixa:** Caso exista uma tela de "acesso em andamento", clicar em continuar. Após o login, clicar no menu lateral em "Fechamento de caixa" (`//*[@id="mfe-sidebar-react"]/div/nav/div[2]/div[2]/a`).
- [ ] **2.3. Selecionar Loja e Capturar Autenticação:** Clicar para listar as lojas (`//*[@id="novo-layout-filtros"]/div/div[1]/span/span/span`) e selecionar a loja "20843 - UDI SH" (`/html/body/div[22]/div/ul/li[1]`). Dar duplo clique em qualquer dia no calendário (ex: `//*[@id="calendarVendas"]/div/div/table/tbody/tr[2]/td[5]/div/div[2]/div/div`). O listener do Playwright vai interceptar e salvar o `Bearer Token` e o `Cookie` gerados automaticamente nessa ação.
- [ ] **2.4. Integração com Endpoint de Exclusão (Se necessário):** Utilizar o Bearer e Cookie capturados para fazer chamadas HTTP na API, por exemplo, testando o endpoint `https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/ExcluirDeposito/?id=...` com o payload contendo o ID da loja, caso seja preciso limpar a base.

---

## Fase 3: Leitura da Planilha e Lógica de Negócio (Pandas/Python)
*Extrair os dados da planilha de fechamento e calcular as datas de crédito.*

- [ ] **3.1. Navegação de Abas:** Criar a função que lê a planilha e localiza a aba exata correspondente à data alvo (ex: transformando a entrada `07/05/2026` para a aba `07.05.2026`).
- [ ] **3.2. Tratamento de Dados Monetários:** Desenvolver função para limpar, formatar e converter os valores da coluna `Depósito` (ex: de "R$ 350,00" para `350.00`).
- [ ] **3.3. Lógica de Data de Crédito - Regra Padrão:** Criar função para calcular a data do crédito das lojas comuns baseada no dia da semana.
- [ ] **3.4. Lógica de Data de Crédito - Regra Especial:** Criar função para calcular a data de crédito baseada na regra específica da loja `911557`.
- [ ] **3.5. Cruzamento de Dados:** Relacionar o código da loja lido na planilha com os dados fixos carregados do `lojas.xlsx`.
- [ ] **3.6. Construção do Payload:** Criar a estrutura JSON completa (`Data`, `DataDoCredito`, `Valor`, IDs, etc.) para cada linha lida válida.
- [ ] **3.7. Controle de Duplicidade:** Criar o mecanismo de chave única (`codigo_loja_data_valor`) e validação contra histórico de execuções passadas para evitar envios repetidos.

---

## Fase 4: Integração, Modo Simulação e Testes
*Unir a extração de dados com a captura de token, antes de realizar envios reais em massa.*

- [ ] **4.1. Modo de Simulação (`--dry-run`):** Implementar funcionalidade onde o script passa por todo o fluxo (leitura, conversão, cálculo, criação de payload), mas **pula** a requisição POST para a API real.
- [ ] **4.2. Geração do Relatório Intermediário:** Desenvolver a criação do relatório final (em Excel/CSV) reportando status como "sucesso", "erro", "ignorado" (linha vazia ou depósito zero) e "duplicado".
- [ ] **4.3. Teste Unitário (Aba Real vs Simulação):** Rodar o modo `dry-run` contra uma planilha real de fechamento e validar a conformidade dos dados calculados (Payloads e Datas de Crédito).
- [ ] **4.4. Integração do Fluxo Completo:** Conectar a Etapa de Captura de Token (Fase 2) com a Leitura e Geração de Payload (Fase 3), repassando as credenciais.
- [ ] **4.5. Teste Real com Lote Controlado:** Executar o script em modo real para apenas 2 ou 3 lojas, checando o comportamento na interface do portal Boticário.

---

## Fase 5: Expansão Completa e Deploy
*Colocar a automação em produção para todas as lojas.*

- [ ] **5.1. Execução Completa Homologada:** Retirar o limite de teste e rodar para a planilha completa de um único dia em ambiente de produção, acompanhando a geração do Relatório Final de Execução.
- [ ] **5.2. Tratamento Final de Erros e Logs:** Validar que exceções (loja não encontrada, timeout de API) registram a falha apenas na linha afetada e o script continua processando o resto da aba. Validar também o mascaramento de logs sensíveis (Tokens não expostos).
- [ ] **5.3. Agendamento / HUB:** Agendar a automação no servidor / HUB de automações (ex: Windows Task Scheduler, CRON, ou orquestrador).
- [ ] **5.4. Documentação de Entrega:** Atualizar o `README.md` do projeto contendo as instruções de instalação das dependências, as varáveis do `.env` e instruções sobre os modos de execução (`--data` e `--dry-run`).
