# Plano de Expansão – Automação de Lançamento de Depósitos para Todas as Lojas

## 1. Objetivo

Expandir a automação de lançamento de depósitos via API HTTP, que já teve o MVP validado com uma loja, para processar automaticamente os depósitos de todas as lojas a partir da planilha de fechamento de caixa.

A automação deverá ler os dados da planilha, identificar a aba referente ao dia do depósito, capturar o código da loja, o nome da loja, o valor do depósito e calcular a data de crédito conforme as regras operacionais definidas.

---

## 2. Status Atual do Projeto

O MVP da automação funcionou com uma loja.

A próxima fase é transformar esse MVP em uma automação em lote para todas as lojas, com leitura automática da planilha de depósitos e envio dos lançamentos para o portal.

Nesta fase, o script deverá:

- Ler a planilha de fechamento de caixa.
- Identificar a aba referente à data do depósito.
- Ler todas as lojas da aba selecionada.
- Capturar a data do depósito.
- Capturar o código da loja.
- Capturar o nome da loja.
- Capturar o valor da coluna `Depósito`.
- Consultar os dados fixos da loja no cadastro.
- Calcular a data do crédito.
- Montar o payload de cada loja.
- Enviar cada lançamento para o portal via API.
- Registrar logs e relatório final da execução.

---

## 3. Fonte de Dados Principal

A automação utilizará como entrada a planilha de depósitos/fechamento de caixa.

Essa planilha é separada por abas, e cada aba representa um dia.

Exemplo de aba:

```text
07.05.2026
```

Cada aba diária contém as informações de depósito daquele respectivo dia.

---

## 4. Estrutura da Planilha

A planilha possui colunas importantes para a automação.

| Coluna | Uso na automação |
|---|---|
| `DATA` | Data do depósito. |
| `Código` | Código da loja. |
| `Loja` | Nome da loja. |
| `Depósito` | Valor do depósito a ser lançado no portal. |

---

## 5. Regra de Leitura por Aba

A planilha possui uma aba para cada data.

Exemplo:

```text
06.05.2026
07.05.2026
08.05.2026
```

O script deverá receber ou identificar a data de processamento e abrir a aba correspondente.

Exemplo:

Se a data de processamento for:

```text
07/05/2026
```

O script deverá procurar a aba:

```text
07.05.2026
```

Caso a aba não exista, o script deve registrar erro e interromper a execução antes de tentar enviar qualquer lançamento.

---

## 6. Interpretação dos Campos da Planilha

### 6.1 Data do Depósito

A data da aba representa a data do depósito.

Além disso, a própria planilha também possui o campo `DATA`.

Essa data será usada no payload no campo:

```json
"Data"
```

Exemplo de data na planilha:

```text
07.05.2026
```

Formato esperado pela API:

```text
2026-05-07T03:00:00.000Z
```

---

### 6.2 Código da Loja

A coluna `Código` será usada para identificar a loja.

Com esse código, o script deverá buscar em um cadastro auxiliar os dados fixos necessários para montar o payload:

- `ContaOrigem`
- `ContaDestino`
- `EmpresaId`
- `NomeContaOrigem`

Exemplo:

| Código | Loja |
|---:|---|
| 20843 | Udi. Shopping |
| 20845 | Floriano P. |
| 911557 | Loja com regra especial |

---

### 6.3 Nome da Loja

A coluna `Loja` será usada para conferência, logs e relatório.

O nome da loja ajuda a validar se o código lido realmente corresponde à loja esperada.

---

### 6.4 Valor do Depósito

A coluna `Depósito` será usada como o valor a ser lançado no portal.

Esse valor será enviado no payload no campo:

```json
"Valor"
```

Exemplo na planilha:

```text
R$ 350,00
```

Valor tratado pelo script:

```text
350.00
```

Linhas com depósito zerado, vazio ou inválido devem ser ignoradas ou registradas no relatório como não processadas.

---

## 7. Cadastro de Lojas

Além da planilha de fechamento, será necessário manter um cadastro fixo com os dados técnicos de cada loja.

Arquivo recomendado:

```text
config/lojas.xlsx
```

Colunas recomendadas:

| Coluna | Descrição |
|---|---|
| `codigo_loja` | Código da loja usado na planilha de depósitos. |
| `nome_loja_planilha` | Nome da loja como aparece na planilha. |
| `ContaOrigem` | ID da conta de origem no portal. |
| `ContaDestino` | ID da conta destino no portal. |
| `EmpresaId` | ID da empresa no portal. |
| `NomeContaOrigem` | Nome completo da conta de origem usado no payload. |
| `regra_credito` | Tipo de regra de crédito da loja. |

Exemplo:

| codigo_loja | nome_loja_planilha | ContaOrigem | ContaDestino | EmpresaId | NomeContaOrigem | regra_credito |
|---:|---|---|---|---|---|---|
| 20843 | Udi. Shopping | id_conta_origem | id_conta_destino | id_empresa | CAIXA LOJA - 20843 - UDI SHOPPING | padrao |
| 911557 | Loja Especial | id_conta_origem | id_conta_destino | id_empresa | CAIXA LOJA - 911557 | especial_911557 |

---

## 8. Regra Padrão de Data de Crédito

Na maioria das lojas, os depósitos seguem esta regra:

| Dia em que o crédito é feito | Depósitos correspondentes |
|---|---|
| Segunda-feira | Depósitos de sexta, sábado e domingo |
| Quarta-feira | Depósitos de segunda e terça |
| Sexta-feira | Depósitos de quarta e quinta |

Isso significa que o script deverá calcular a data do crédito com base na data do depósito.

---

## 9. Mapeamento da Regra Padrão

| Dia do depósito | Data do crédito |
|---|---|
| Segunda-feira | Quarta-feira da mesma semana |
| Terça-feira | Quarta-feira da mesma semana |
| Quarta-feira | Sexta-feira da mesma semana |
| Quinta-feira | Sexta-feira da mesma semana |
| Sexta-feira | Segunda-feira seguinte |
| Sábado | Segunda-feira seguinte |
| Domingo | Segunda-feira seguinte |

---

## 10. Regra Especial da Loja 911557

A loja `911557` possui uma regra diferente da regra padrão.

Para essa loja, os créditos seguem a seguinte lógica:

| Dia em que o crédito é feito | Depósitos correspondentes |
|---|---|
| Segunda-feira | Depósitos de quinta e sexta |
| Quarta-feira | Depósitos de sábado, domingo e segunda |
| Sexta-feira | Depósitos de terça e quarta |

---

## 11. Mapeamento da Regra Especial – Loja 911557

| Dia do depósito | Data do crédito |
|---|---|
| Segunda-feira | Quarta-feira da mesma semana |
| Terça-feira | Sexta-feira da mesma semana |
| Quarta-feira | Sexta-feira da mesma semana |
| Quinta-feira | Segunda-feira seguinte |
| Sexta-feira | Segunda-feira seguinte |
| Sábado | Quarta-feira seguinte |
| Domingo | Quarta-feira seguinte |

---

## 12. Função Conceitual para Cálculo da Data de Crédito

### 12.1 Regra padrão

```python
def calcular_credito_padrao(data_deposito):
    dia_semana = data_deposito.weekday()

    if dia_semana == 0:  # segunda
        return data_deposito + timedelta(days=2)

    if dia_semana == 1:  # terça
        return data_deposito + timedelta(days=1)

    if dia_semana == 2:  # quarta
        return data_deposito + timedelta(days=2)

    if dia_semana == 3:  # quinta
        return data_deposito + timedelta(days=1)

    if dia_semana == 4:  # sexta
        return data_deposito + timedelta(days=3)

    if dia_semana == 5:  # sábado
        return data_deposito + timedelta(days=2)

    if dia_semana == 6:  # domingo
        return data_deposito + timedelta(days=1)
```

### 12.2 Regra especial da loja 911557

```python
def calcular_credito_911557(data_deposito):
    dia_semana = data_deposito.weekday()

    if dia_semana == 0:  # segunda
        return data_deposito + timedelta(days=2)

    if dia_semana == 1:  # terça
        return data_deposito + timedelta(days=3)

    if dia_semana == 2:  # quarta
        return data_deposito + timedelta(days=2)

    if dia_semana == 3:  # quinta
        return data_deposito + timedelta(days=4)

    if dia_semana == 4:  # sexta
        return data_deposito + timedelta(days=3)

    if dia_semana == 5:  # sábado
        return data_deposito + timedelta(days=4)

    if dia_semana == 6:  # domingo
        return data_deposito + timedelta(days=3)
```

---

## 13. Payload Final Esperado

Para cada linha válida da planilha, o script deverá montar um payload neste formato:

```json
{
  "_id": null,
  "ContaOrigem": "ID_DA_CONTA_ORIGEM",
  "ContaDestino": "ID_DA_CONTA_DESTINO",
  "Data": "2026-05-07T03:00:00.000Z",
  "DataDoCredito": "2026-05-08T03:00:00.000Z",
  "Descricao": "Depósito para CC em 07/05/2026",
  "EmpresaId": "ID_DA_EMPRESA",
  "NomeContaDestino": null,
  "NomeContaOrigem": "NOME_DA_CONTA_ORIGEM",
  "Valor": 350.00,
  "errors": []
}
```

---

## 14. Fluxo da Automação Expandida

```text
1. Iniciar script.
2. Carregar configurações da API.
3. Carregar cadastro de lojas.
4. Abrir planilha de fechamento de caixa.
5. Identificar a aba referente à data de processamento.
6. Ler os dados da aba.
7. Identificar a data do depósito.
8. Ler cada linha da tabela.
9. Capturar código da loja.
10. Capturar nome da loja.
11. Capturar valor da coluna Depósito.
12. Ignorar linhas sem depósito válido.
13. Buscar a loja no cadastro pelo código.
14. Identificar se a loja usa regra padrão ou regra especial.
15. Calcular DataDoCredito.
16. Montar payload.
17. Validar payload.
18. Enviar requisição POST para a API.
19. Registrar resultado individual.
20. Gerar relatório final.
21. Encerrar execução.
```

---

## 15. Validações Antes do Envio

Antes de enviar qualquer lançamento para o portal, o script deve validar:

- Se a planilha existe.
- Se a aba da data existe.
- Se a data da aba está em formato válido.
- Se a coluna `Código` existe.
- Se a coluna `Loja` existe.
- Se a coluna `Depósito` existe.
- Se o valor do depósito é maior que zero.
- Se o código da loja existe no cadastro.
- Se a loja possui `ContaOrigem`.
- Se a loja possui `ContaDestino`.
- Se a loja possui `EmpresaId`.
- Se a loja possui `NomeContaOrigem`.
- Se a data de crédito foi calculada corretamente.
- Se o token/cookie da API está disponível.
- Se a resposta da API não retornou erro de negócio.

---

## 16. Tratamento de Linhas Inválidas

O script não deve interromper toda a execução por causa de uma loja com problema.

Se uma linha apresentar erro, o script deve:

1. Registrar a falha no relatório.
2. Informar o motivo da falha.
3. Pular a loja problemática.
4. Continuar processando as demais lojas.

Exemplos de falhas por linha:

- Código da loja não encontrado no cadastro.
- Valor de depósito vazio.
- Valor de depósito igual a zero.
- Valor de depósito em formato inválido.
- Dados obrigatórios da loja ausentes.
- Erro de comunicação com a API.
- Erro de negócio retornado pela API.

---

## 17. Controle Contra Duplicidade

Como o script fará lançamentos em lote, é fundamental evitar duplicidade.

Recomendação:

Criar uma chave única por lançamento:

```text
codigo_loja + data_deposito + valor_deposito
```

Exemplo:

```text
20843_2026-05-07_350.00
```

Antes de enviar, o script deve consultar o histórico de execuções e verificar se aquela chave já foi enviada com sucesso.

Se já existir sucesso para aquela chave, o script deve:

- Não enviar novamente.
- Registrar no relatório como `ignorado_por_duplicidade`.

---

## 18. Relatório Final da Execução

Ao final da execução, o script deverá gerar um relatório em Excel ou CSV contendo:

| Campo | Descrição |
|---|---|
| `data_execucao` | Data e hora em que o script rodou. |
| `aba_processada` | Nome da aba lida. |
| `data_deposito` | Data do depósito. |
| `data_credito` | Data do crédito calculada. |
| `codigo_loja` | Código da loja. |
| `nome_loja_planilha` | Nome da loja na planilha. |
| `NomeContaOrigem` | Nome da conta enviada no payload. |
| `valor_deposito` | Valor lançado. |
| `regra_credito` | Regra usada: `padrao` ou `especial_911557`. |
| `status` | Sucesso, erro, ignorado ou duplicado. |
| `status_code` | Código HTTP retornado pela API. |
| `mensagem_erro` | Mensagem de erro, se houver. |
| `payload` | Payload enviado. |
| `resposta_api` | Resposta retornada pela API. |

---

## 19. Estrutura Recomendada de Pastas

```text
automacao_depositos/
│
├── config/
│   ├── lojas.xlsx
│   └── .env
│
├── input/
│   └── fechamento_de_caixa.xlsx
│
├── output/
│   ├── logs/
│   ├── relatorios/
│   └── historico/
│
├── script_depositos.py
├── requirements.txt
└── README.md
```

---

## 20. Arquivo `.env`

O arquivo `.env` deve armazenar informações sensíveis e configurações da API.

Exemplo:

```env
API_URL=https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/RealizarDeposito/
AUTHORIZATION=Bearer COLE_SEU_TOKEN_AQUI
COOKIE=COLE_SEU_COOKIE_AQUI_SE_NECESSARIO
```

Importante:

- Não salvar tokens diretamente no código.
- Não subir o `.env` para repositório.
- Atualizar tokens/cookies quando expirarem.

---

## 21. Dependências

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

## 22. Modo de Operação

O script poderá funcionar de duas formas.

### 22.1 Modo automático

O script usa a data atual e procura automaticamente a aba correspondente.

Exemplo:

Data atual:

```text
07/05/2026
```

Aba buscada:

```text
07.05.2026
```

### 22.2 Modo manual

O usuário informa a data desejada para processamento.

Exemplo:

```bash
python script_depositos.py --data 07.05.2026
```

Nesse caso, o script deve abrir especificamente a aba `07.05.2026`.

---

## 23. Modo de Teste

Antes de executar para todas as lojas, recomenda-se criar um modo de simulação.

Nesse modo, o script:

- Lê a planilha.
- Calcula as datas.
- Monta os payloads.
- Gera relatório.
- Não envia nada para a API.

Exemplo:

```bash
python script_depositos.py --data 07.05.2026 --dry-run
```

Esse modo é importante para validar:

- Se a aba correta foi lida.
- Se os códigos das lojas foram encontrados.
- Se os valores estão corretos.
- Se a data do crédito foi calculada corretamente.
- Se a loja `911557` recebeu a regra especial.

---

## 24. Checklist de Validação

Antes de rodar em produção:

- [ ] O MVP com uma loja foi validado.
- [ ] A planilha de fechamento está no formato esperado.
- [ ] A aba da data existe.
- [ ] O cadastro de lojas está completo.
- [ ] A loja `911557` está marcada com regra especial.
- [ ] Os valores da coluna `Depósito` estão sendo convertidos corretamente.
- [ ] A data do depósito está sendo capturada corretamente.
- [ ] A data do crédito está sendo calculada corretamente.
- [ ] O payload final bate com o payload real do portal.
- [ ] O modo teste foi executado.
- [ ] O relatório de simulação foi revisado.
- [ ] O envio real foi testado com poucas lojas.
- [ ] O envio real foi validado no portal.
- [ ] O controle contra duplicidade foi ativado.

---

## 25. Riscos e Cuidados

| Risco | Impacto | Mitigação |
|---|---|---|
| Enviar depósito duplicado | Alto | Controle por chave única e histórico de sucesso. |
| Calcular crédito errado | Alto | Testar regra padrão e regra especial antes do envio real. |
| Loja sem cadastro | Médio | Registrar erro e não enviar a linha. |
| Token expirado | Médio | Validar autenticação antes do lote. |
| Planilha fora do padrão | Médio | Validar colunas obrigatórias antes da execução. |
| Valor convertido errado | Alto | Normalizar formato monetário brasileiro antes do envio. |
| Aba inexistente | Médio | Interromper execução antes do envio. |

---

## 26. Critérios de Sucesso

A expansão será considerada concluída quando:

- [ ] O script conseguir ler a aba correta da planilha.
- [ ] O script conseguir processar todas as lojas da aba.
- [ ] O script conseguir ignorar linhas sem depósito.
- [ ] O script conseguir cruzar loja pelo código.
- [ ] O script conseguir calcular data de crédito pela regra padrão.
- [ ] O script conseguir calcular data de crédito pela regra especial da loja `911557`.
- [ ] O script conseguir montar os payloads corretamente.
- [ ] O script conseguir enviar os lançamentos em lote.
- [ ] O script conseguir gerar relatório detalhado da execução.
- [ ] O script conseguir evitar duplicidade.
- [ ] O processo puder ser repetido diariamente com segurança.

---

## 27. Próximos Passos Técnicos

1. Ajustar o cadastro de lojas com todos os códigos.
2. Confirmar o nome exato das colunas da planilha.
3. Criar função para abrir a aba conforme a data.
4. Criar função para limpar e converter valores monetários.
5. Criar função para calcular data de crédito padrão.
6. Criar função para calcular data de crédito da loja `911557`.
7. Criar função para montar payload.
8. Criar modo `dry-run`.
9. Criar relatório de simulação.
10. Validar com uma aba real.
11. Testar envio com poucas lojas.
12. Expandir para todas as lojas.
13. Agendar execução ou integrar ao HUB de automações.

---

---

## 29. Captura Automática de Autenticação: Bearer e Cookie

Para que a automação funcione de ponta a ponta sem depender da cópia manual de credenciais, será necessário criar um fluxo automático para obter o `Bearer Token` e o `Cookie` de sessão usados pelo portal.

Essas informações serão capturadas no momento em que o usuário fizer login e executar uma ação real dentro do portal.

A estratégia será usar o Playwright para abrir o navegador, realizar o login, navegar até a tela de lançamento de depósito, executar um depósito teste de R$ 0,01 em uma loja controlada, capturar os dados de autenticação utilizados nas requisições e depois excluir esse depósito teste via API.

Depois disso, o navegador será fechado e o script seguirá para o fluxo principal de lançamento dos depósitos reais.

---

## 30. Objetivo da Captura Automática

O objetivo dessa etapa é obter automaticamente:

- `Authorization: Bearer ...`
- `Cookie`
- Possíveis headers adicionais exigidos pelo portal

Essas credenciais serão usadas posteriormente nas requisições HTTP feitas pelo script, sem precisar manter navegador aberto durante todo o processo.

---

## 31. Fluxo Geral da Captura de Bearer e Cookie

```text
1. Iniciar script.
2. Abrir navegador com Playwright.
3. Acessar o portal.
4. Realizar login na conta autorizada.
5. Navegar até o caminho de lançamento de depósito.
6. Selecionar a primeira loja controlada para teste.
7. Realizar um depósito teste de R$ 0,01.
8. Capturar o Bearer Token usado nas requisições.
9. Capturar o Cookie de sessão usado no momento do depósito.
10. Capturar o ID do depósito teste criado.
11. Fechar o navegador.
12. Enviar requisição POST/DELETE para excluir o depósito teste.
13. Validar se o depósito teste foi excluído com sucesso.
14. Usar Bearer e Cookie capturados para seguir com os depósitos reais.
```

---

## 32. Por Que Fazer um Depósito Teste de R$ 0,01?

Apenas fazer login pode não ser suficiente para capturar todos os dados necessários.

Em muitos sistemas, o token de autenticação aparece no login, mas o cookie, headers adicionais ou dados específicos da operação só ficam claros quando uma ação real é feita no módulo desejado.

Por isso, o fluxo propõe criar um depósito mínimo de R$ 0,01.

Esse depósito serve apenas para:

- Forçar o portal a executar a requisição real de depósito.
- Capturar os headers corretos usados nessa operação.
- Confirmar o endpoint de criação do depósito.
- Obter o ID do lançamento criado.
- Validar que o usuário logado possui permissão para realizar essa operação.

Após a captura, esse depósito deverá ser excluído automaticamente antes do script seguir para os lançamentos reais.

---

## 33. Etapa 1 – Login com Playwright

O Playwright será responsável por abrir o navegador e realizar o login no portal.

Fluxo esperado:

```text
1. Abrir navegador.
2. Acessar URL do portal.
3. Preencher usuário.
4. Preencher senha.
5. Clicar em entrar.
6. Aguardar carregamento completo.
7. Confirmar que login foi realizado com sucesso.
```

Exemplo conceitual:

```python
from playwright.sync_api import sync_playwright

def abrir_portal_e_logar(usuario, senha):
    playwright = sync_playwright().start()

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto("URL_DO_PORTAL")

    page.fill("#campo_usuario", usuario)
    page.fill("#campo_senha", senha)
    page.click("#botao_login")

    page.wait_for_load_state("networkidle")

    return playwright, browser, context, page
```

Observação:

Os seletores reais (`#campo_usuario`, `#campo_senha`, `#botao_login`) deverão ser ajustados conforme o HTML do portal.

---

## 34. Etapa 2 – Captura do Bearer Token

O `Bearer Token` poderá ser capturado monitorando as requisições feitas pelo navegador.

O Playwright permite escutar as requisições e analisar os headers enviados.

Exemplo conceitual:

```python
auth_data = {
    "bearer": None,
    "cookie": None
}

def capturar_headers(request):
    headers = request.headers

    authorization = headers.get("authorization")
    cookie = headers.get("cookie")

    if authorization and authorization.lower().startswith("bearer"):
        auth_data["bearer"] = authorization

    if cookie:
        auth_data["cookie"] = cookie

page.on("request", capturar_headers)
```

Essa função deverá ser ativada antes de navegar até a tela de depósito e antes de executar o depósito teste.

---

## 35. Etapa 3 – Navegar até a Tela de Depósito

Depois do login, o script deverá navegar até o caminho no portal onde o lançamento de depósito é feito.

Fluxo esperado:

```text
1. Acessar menu financeiro/fechamento de caixa.
2. Entrar na tela de depósitos.
3. Selecionar a primeira loja controlada para teste.
4. Preencher os dados mínimos do depósito.
```

Essa navegação pode ser feita de duas formas:

### 35.1 Por cliques na interface

O script clica nos menus e botões do portal como um usuário faria.

Vantagem:

- Mais parecido com o uso real.

Desvantagem:

- Mais sensível a mudanças visuais na tela.

### 35.2 Por URL direta

O script acessa diretamente a URL da tela de depósito, caso ela seja conhecida.

Vantagem:

- Mais rápido.
- Menos dependente de cliques.

Desvantagem:

- Pode falhar se a URL depender de estado interno da aplicação.

---

## 36. Etapa 4 – Criar Depósito Teste de R$ 0,01

O script deverá criar um depósito teste em uma loja previamente definida como segura para esse processo.

Recomendação:

Criar uma configuração específica no `.env` ou no arquivo de configuração:

```env
LOJA_TESTE_CODIGO=20843
VALOR_DEPOSITO_TESTE=0.01
```

O depósito teste deverá usar:

| Campo | Valor |
|---|---|
| Loja | Loja controlada definida no projeto |
| Valor | R$ 0,01 |
| Data | Data atual ou data segura definida |
| Descrição | Depósito teste automático para captura de autenticação |

Descrição recomendada:

```text
DEPÓSITO TESTE AUTOMÁTICO - CAPTURA DE AUTENTICAÇÃO
```

Essa descrição facilitará a identificação e exclusão do lançamento.

---

## 37. Etapa 5 – Capturar o ID do Depósito Teste

Após criar o depósito teste, o script precisa capturar o ID do lançamento criado.

Esse ID pode aparecer:

- Na resposta da API de criação do depósito.
- Em uma requisição posterior de listagem.
- No payload de retorno da tela.
- Em uma tabela atualizada no portal.

O ideal é capturar diretamente a resposta da requisição de criação.

Exemplo conceitual com Playwright:

```python
deposito_teste = {
    "id": None
}

def capturar_resposta(response):
    url = response.url

    if "RealizarDeposito" in url:
        try:
            data = response.json()
            deposito_teste["id"] = data.get("_id") or data.get("id")
        except Exception:
            pass

page.on("response", capturar_resposta)
```

Caso o endpoint de criação não retorne o ID diretamente, será necessário mapear o endpoint de consulta/listagem para localizar o depósito teste recém-criado.

---

## 38. Etapa 6 – Fechar o Navegador

Depois de capturar:

- Bearer
- Cookie
- ID do depósito teste

O navegador poderá ser fechado.

Exemplo:

```python
browser.close()
playwright.stop()
```

A partir desse ponto, o script seguirá apenas com requisições HTTP usando `requests`.

---

## 39. Etapa 7 – Excluir o Depósito Teste via API

Após fechar o navegador, o script deverá excluir o depósito teste usando o Bearer e o Cookie capturados.

O método exato precisa ser confirmado no DevTools do navegador.

Possíveis formas:

```http
POST /ExcluirDeposito/
```

ou

```http
DELETE /Deposito/{id}
```

ou

```http
POST /RealizarDeposito/Excluir
```

A estrutura final dependerá do endpoint real utilizado pelo portal.

Exemplo conceitual:

```python
import requests

def excluir_deposito_teste(deposito_id, bearer, cookie):
    headers = {
        "Authorization": bearer,
        "Cookie": cookie,
        "Content-Type": "application/json"
    }

    payload = {
        "_id": deposito_id
    }

    response = requests.post(
        "URL_ENDPOINT_EXCLUSAO_DEPOSITO",
        json=payload,
        headers=headers,
        timeout=30
    )

    return response
```

---

## 40. Validação da Exclusão do Depósito Teste

Antes de seguir para os depósitos reais, o script deve confirmar que o depósito teste foi excluído.

Critérios possíveis:

- API de exclusão retornou status `200` ou `204`.
- Resposta da API não possui erros.
- Endpoint de consulta não encontra mais o depósito.
- Portal não mostra mais o depósito na listagem.

Se o depósito teste não for excluído, o script deve parar a execução e gerar alerta.

Regra de segurança:

```text
Se o depósito teste não for excluído com sucesso, não continuar para os depósitos reais.
```

Isso evita acumular lançamentos de teste no portal.

---

## 41. Uso das Credenciais Capturadas no Fluxo Real

Depois que o Bearer e Cookie forem capturados e o depósito teste for excluído, o script seguirá para o fluxo principal.

Fluxo principal:

```text
1. Ler aba da planilha.
2. Processar lojas.
3. Calcular data de crédito.
4. Montar payloads.
5. Enviar depósitos reais usando Bearer e Cookie capturados.
6. Registrar relatório final.
```

Headers usados no envio real:

```python
headers = {
    "Authorization": bearer,
    "Cookie": cookie,
    "Content-Type": "application/json"
}
```

---

## 42. Estratégia de Segurança

Como o Bearer e o Cookie dão acesso à sessão autenticada, eles devem ser tratados como dados sensíveis.

Regras recomendadas:

- Não exibir Bearer completo no console.
- Não salvar Bearer completo nos logs.
- Não salvar Cookie completo nos logs.
- Se precisar registrar, mascarar os valores.
- Armazenar temporariamente apenas em memória.
- Encerrar execução se a autenticação falhar.
- Usar somente conta autorizada pela empresa para essa automação.

Exemplo de mascaramento:

```python
def mascarar_token(valor):
    if not valor:
        return None

    return valor[:12] + "..." + valor[-6:]
```

---

## 43. Estratégia de Falha

Se qualquer etapa da captura automática falhar, o script não deve continuar.

### 43.1 Falhou login

Ação:

```text
Parar execução e registrar: Falha no login.
```

### 43.2 Não capturou Bearer

Ação:

```text
Parar execução e registrar: Bearer não capturado.
```

### 43.3 Não capturou Cookie

Ação:

```text
Parar execução e registrar: Cookie não capturado.
```

### 43.4 Depósito teste não foi criado

Ação:

```text
Parar execução e registrar: Depósito teste não criado.
```

### 43.5 ID do depósito teste não foi localizado

Ação:

```text
Parar execução e registrar: ID do depósito teste não localizado.
```

### 43.6 Depósito teste não foi excluído

Ação:

```text
Parar execução e registrar: Depósito teste não excluído. Fluxo real bloqueado.
```

---

## 44. Ordem Final da Automação Completa

A automação completa deverá seguir esta ordem:

```text
1. Iniciar script.
2. Abrir navegador com Playwright.
3. Logar no portal.
4. Ativar captura de requests e responses.
5. Navegar até a tela de depósito.
6. Criar depósito teste de R$ 0,01.
7. Capturar Bearer.
8. Capturar Cookie.
9. Capturar ID do depósito teste.
10. Fechar navegador.
11. Excluir depósito teste via API.
12. Confirmar exclusão do depósito teste.
13. Ler planilha de fechamento.
14. Abrir aba da data.
15. Processar depósitos reais.
16. Calcular data de crédito.
17. Enviar depósitos reais via API.
18. Gerar relatório final.
19. Encerrar execução.
```

---

## 45. Atualização dos Critérios de Sucesso

Além dos critérios anteriores, a expansão só será considerada segura quando:

- [ ] O Playwright conseguir logar automaticamente.
- [ ] O script conseguir capturar o Bearer Token.
- [ ] O script conseguir capturar o Cookie de sessão.
- [ ] O script conseguir criar um depósito teste de R$ 0,01.
- [ ] O script conseguir capturar o ID do depósito teste.
- [ ] O script conseguir excluir o depósito teste via API.
- [ ] O script bloquear o fluxo real se a exclusão do teste falhar.
- [ ] O script usar Bearer e Cookie capturados para enviar os depósitos reais.
- [ ] Nenhuma credencial sensível ficar exposta em logs ou relatórios.

---

## 46. Próximos Passos Técnicos Adicionados

1. Mapear os seletores da tela de login.
2. Mapear o caminho até a tela de depósito.
3. Criar função de login com Playwright.
4. Criar função de captura de headers.
5. Criar função de criação do depósito teste.
6. Identificar onde o ID do depósito teste aparece.
7. Mapear endpoint de exclusão do depósito.
8. Criar função para excluir depósito teste via API.
9. Criar bloqueio de segurança se o teste não for excluído.
10. Integrar a captura automática ao fluxo principal de depósitos reais.

## 28. Conclusão

A expansão da automação é viável porque o MVP já validou o envio via API com uma loja.

A próxima etapa é transformar o script em um processo robusto de leitura, validação, cálculo de data de crédito e envio em lote.

O ponto mais importante da expansão será garantir três coisas:

1. A leitura correta da aba diária da planilha.
2. O cálculo correto da data de crédito.
3. A prevenção contra duplicidade de lançamentos.

Com esses controles, a automação poderá ser usada de forma segura para todas as lojas.

---

**Projeto:** Automação de Lançamento de Depósitos via API HTTP  
**Fase:** Expansão para todas as lojas  
**Versão:** 1.1  
**Data:** 07/05/2026  
**Atualização:** Inclusão do plano de captura automática de Bearer e Cookie com Playwright
