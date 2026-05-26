[[PROJETO SOFI]]

Esse módulo será a forma mais eficiente de controlar fundo de caixa e monitorar e lançar depósitos. 

Atualmente o processo é muito manual e repetitivo: 

1. O Assistente abre as fotos dos envelopes de depósitos que são enviados via whatsapp; 
2. Transcreve os valores em uma planilha do excel; 
3. Baixa um relatório de valores em dinheiro dos PDV's dentro do portal Retaguarda; 
4. Transcreve os valores em dinheiro na planilha;
5. Verifica os valores de fundo de caixa no FinançasGB; 
6. Transcreve manualmente na mesma planilha; 
7. Verifica por fórmula se tem algum depósito com valor divergente do valor em dinheiro no caixa; 
8. Lança manualmente depósito por depósito dentro do FinançasGB.

Esse processo está sujeito a erro humano, vamos criar um módulo dentro do SOFI que controla isso tudo de forma 80% autônoma: 

1. O Assistente ainda transcreverá manualmente os valores de depósito, só que vai ser descrito dentro do sistema, e não em uma planilha confusa no excel; 
2. Os valores em dinheiro vão ser extraídos automaticamente do Retaguarda; 
3. Os valores de fundo de caixa vão ser extraídos automaticamente do FinançasGB; 
4. O SOFI vai avisar se tiver alguma diferença relevante no caixa; 
5. Vai lançar automaticamente para o FinançasGB depois de confirmado pelo operador.

Etapas já automatizadas: 

1. Valores em dinheiro já transcritos automaticamente para o Excel; 
2. Lançamentos de depósitos no Finanças já automatizado e sem intervenção humana. 
   
A parte mais trabalhosa que é lançar no Finanças já está automatizada. 