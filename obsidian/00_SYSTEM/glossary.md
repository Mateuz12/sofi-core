# 📖 Glossário Corporativo e Técnico do SOFI

Este documento centraliza a terminologia operacional, financeira e tecnológica utilizada pelo ecossistema SOFI e suas integrações com o franqueado do Grupo Boticário.

---

## 🏢 Termos de Negócio e Operação

### PDV (Ponto de Venda)
Identificador alfanumérico ou código numérico único que individualiza cada uma das 43 lojas e operações da franquia (ex: 21061).

### VD (Venda Direta)
Canal comercial do Grupo Boticário baseado em revendedoras diretas. Operacionalmente, possui caixas de e-mail específicas, planilhas próprias e processos de conciliação segregados dos PDVs de shopping e rua.

### UDI e BH (Unidades Operacionais)
Divisão regional das operações da franqueada:
- **UDI:** Região de Uberlândia / Triângulo Mineiro.
- **BH:** Região de Belo Horizonte / Central.
Cada região possui credenciais distintas nos portais, diretórios próprios na rede corporativa e caixas de e-mail segregadas.

### DFC (Demonstração do Fluxo de Caixa)
Relatório analítico de fluxo de caixa projetado e realizado, extraído diariamente do portal FinançasGB com horizonte de até 12 meses futuros para apoiar o planejamento financeiro da diretoria.

### D-1
Convenção temporal para relatórios que consolidam os dados de faturamento e vendas encerrados no dia anterior útil ou civil.

### Cálamo (Cálamo Distribuidora de Produtos de Beleza)
Distribuidora e fornecedora principal de mercadorias para as franquias do Grupo Boticário. As notas fiscais emitidas pela Cálamo passam por conferência semanal detalhada de ICMS ST, prazos e produtos.

### Matheus (Relatório Matheus)
Variação específica dos relatórios formatados de notas fiscais da Cálamo (gerados para BH e UDI), contendo agrupamentos e cálculos direcionados ao controle de auditoria de compras.

### OP Picking / Picking
Ordem de Separação / Processo de preparação e conferência de mercadorias no centro de distribuição. As automações do SOFI extraem os dados de picking via API para validar o faturamento contra o que foi fisicamente separado.

### NSU (Número Sequencial Único)
Identificador numérico fornecido pelas adquirentes e credenciadoras de cartão de crédito e débito para identificar univocamente uma transação financeira.

### Omnichannel
Modalidade de venda que conecta os estoques e pedidos do e-commerce/aplicativo à retirada ou entrega a partir do PDV físico. No portal FinançasGB, requer conciliação visual específica.

### Caixas Laranja vs. Caixas Azul
Terminologia visual da interface do portal FinançasGB (baseado em Knockout.js):
- **Caixa Laranja:** Representa o registro de venda emitido pelo PDV.
- **Caixa Azul:** Representa a liquidação financeira / recebível correspondente.
A conciliação consiste em associar (arrastar) a caixa laranja até a caixa azul compatível.

### Fundo de Caixa
Valor fixo mantido em espécie nas lojas para troco e pequenas despesas operacionais, cuja conferência é cruzada com os depósitos bancários de fechamento.

---

## 💻 Termos Técnicos e de Infraestrutura

### APScheduler
Biblioteca Python (`apscheduler`) utilizada em background no SOFI para disparo autônomo de tarefas programadas (cron interno) com gestão de timezones (`America/Sao_Paulo`).

### Exit Codes (0, 1, 2, 3)
Convenção de códigos numéricos retornados pelos scripts no encerramento de sua execução, informando ao orquestrador se a rotina obteve sucesso (`0`), falhou de forma transitória (`1` - cabe retry), falhou de forma permanente (`2` - abortar sem retry) ou concluiu sem dados de faturamento (`3`).

### WAL (Write-Ahead Logging)
Modo de operação do banco de dados SQLite (`PRAGMA journal_mode=WAL;`) que permite que múltiplos processos (ex: Streamlit lendo dashboards enquanto robôs gravam logs) acessem o arquivo `.db` sem travamentos de escrita (`database is locked`).

### DBStreamCatcher
Classe em `core/database/logger.py` que intercepta os canais padrão de saída do Python (`sys.stdout` e `sys.stderr`), direcionando a saída simultaneamente para o terminal do Windows e incrementalmente para o SQLite.

### pywin32 / COM (Component Object Model)
Interface do Windows utilizada pelo SOFI para controlar via automação binária local o Microsoft Outlook (leitura de caixas de email MAPI) e o Microsoft Excel (instâncias `DispatchEx` para geração de relatórios com fórmulas e macros).

### Playwright vs. Selenium
As duas ferramentas de automação web utilizadas no ecossistema:
- **Playwright:** Padrão para 90% das extrações (Extranet, Retaguarda, DFC, FinançasGB) devido à performance assíncrona, robustez para downloads e capacidade de rodar headless com stealth anti-bot.
- **Selenium:** Usado pontualmente na Conciliação de Vendas pela facilidade da API `ActionChains` para realizar drag-and-drop físico em componentes visuais.

### NSSM (Non-Sucking Service Manager)
Utilitário de linha de comando do Windows que encapsula scripts ou binários (como o `streamlit run app.py`) para operarem como serviços nativos do Windows Server, reiniciando automaticamente após reinicializações da máquina.

### Cloudflare Tunnel (`cloudflared`)
Túnel criptografado de rede que publica a porta do Streamlit (8501) na internet de forma segura, sem expor portas do firewall da empresa ou exigir IP fixo.

### Rede Z:\ e T:\
Unidades mapeadas de rede local SMB do servidor `/srv-dc01/File Server/` que servem de repositório oficial de fechamento de caixa, extratos e relatórios auditados da empresa.
