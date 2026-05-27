# Resumo do Projeto: Robôs de Conciliação Financeira (O Boticário)

Este projeto é um ecossistema de automação (RPA - Robotic Process Automation) desenvolvido em Python para realizar a **Conciliação Financeira Automática** de vendas (especialmente cartões e pedidos omnichannel/complexos) dentro do portal **Finanças GB** (Grupo Boticário). 

O sistema substitui o trabalho manual e repetitivo de olhar uma planilha de fechamento de caixa e realizar o "arrastar e soltar" (drag-and-drop) de caixas dentro do portal financeiro para dar baixa nos pagamentos.

## 🛠️ Tecnologias Principais Utilizadas
* **Python**: Linguagem base do projeto.
* **Pandas**: Utilizado para extração, limpeza (ETL) e consolidação matemática dos dados das planilhas de Excel.
* **Selenium WebDriver**: Ferramenta central de automação web. Utilizado para controlar o Google Chrome, caçar elementos HTML via XPath (caixas azuis e laranjas) e simular a interação humana de "arrastar e soltar" via `ActionChains`.
* **CustomTkinter / Tkinter**: Utilizados para construir as Interfaces Gráficas de Usuário (GUI), permitindo que os operadores usem os robôs sem precisar interagir diretamente com o terminal de comando.
* **PyInstaller**: Utilizado para compilar os scripts Python em executáveis `.exe` (evidenciado pelos arquivos `.spec` e pasta `build/dist`), facilitando a distribuição nos computadores da empresa.

---

## 📁 Estrutura e Principais Arquivos

### 1. Robô OMINI (`robo_conciliacao_omini.py` e `robo_conciliacao_omini_gui.py`)
Estes são os scripts mais recentes e robustos, focados exclusivamente nos pagamentos com a classificação "OMNICHANNEL - CONSUMIDOR FINAL".
* **Lógica (Cérebro):** Lê o relatório Excel do dia, remove boletos/pix, soma valores de transações parceladas ou múltiplas de um mesmo pedido e agrupa os dados de forma impecável.
* **Ação (Músculos):** Entra no Finanças GB, encontra a "Caixa Laranja" (lado esquerdo - vendas PDV) baseando-se no valor e título, encontra a "Caixa Azul" correspondente (lado direito - NSU da adquirente), e realiza o "Drag and Drop" físico (arrastar).
* **Modal de Justificativa:** Implementa lógica específica para preencher automaticamente o campo de justificativa ("OMINICHANEL CARTAO") quando exigido pelo portal.
* **Versão GUI:** O arquivo `_gui.py` adiciona uma interface moderna preta e verde (padrão Boticário) que captura os `prints` do terminal e exibe diretamente na tela, tornando o robô extremamente amigável para o usuário final.

### 2. Robô de Casos Complexos (`robo_conciliacao_oficial_complexos.py`)
Focado em lidar com cenários 1-para-N (um pedido para múltiplos pagamentos fracionados).
* **Sistema de Checkpoint:** Ao contrário do robô padrão, este grava cada pedido finalizado em um arquivo de texto (`pedidos_conciliados.txt`). Se o portal travar e o robô cair, na próxima execução ele lê este arquivo e retoma de onde parou, evitando retrabalho.

### 3. Outros Arquivos Relevantes
* **`app_caixa.py`**: Outro módulo central, que também possui sua versão compilada (`app_caixa.spec`).
* **`robo_conciliacao.py` / `robo_planilha.py`**: Versões ou módulos complementares (provavelmente lógicas anteriores ou auxiliares de leitura de planilhas).
* **`pedidos_conciliados.txt` / `pedidos_conciliados_omini.txt`**: Arquivos de log/checkpoint que salvam o histórico de trabalho realizado pelas automações.

---

## ⚙️ Como Funciona o Fluxo Geral
1. O robô pergunta ao usuário a data desejada (ou assume a data de hoje).
2. Ele busca automaticamente a planilha do fechamento de caixa na rede corporativa (ex: `\\srv-dc01\File Server\...`) ou pede para o usuário anexar o Excel manualmente.
3. Filtra os ruídos da planilha, processa toda a matemática consolidando valores.
4. Abre o Google Chrome no portal do Finanças GB e pede que o usuário faça o login e selecione a data no calendário.
5. Inicia um *loop* lendo a fila de pedidos, travando nos XPaths corretos (Laranja vs Azul), arrasta os elementos na interface web e aguarda a confirmação de baixa do portal.
6. Ao finalizar, exibe uma mensagem de sucesso na tela.
