# Regras do agente — Projeto SOFI

## Regra 0 (inegociável): consultar o vault antes de qualquer decisão

Antes de propor um plano de implementação, decidir uma abordagem técnica, ou alterar
qualquer código, você **precisa** consultar o vault de contexto em `_vault/` (Obsidian).
Isso vale mesmo que você "já saiba" a resposta pelo que está no código — o vault
carrega decisões, gambiarras propositais e histórico que o código sozinho não mostra.

Nunca pule essa etapa por parecer "óbvio" ou "rápido demais pra precisar checar".

## Como navegar o vault (convenção do grafo)

- Todo arquivo do vault usa links no formato `[[nome-do-modulo]]`.
- Essa notação **não é reconhecida automaticamente** — é convenção nossa: todo
  `[[nome-do-modulo]]` aponta para o arquivo `_vault/**/nome-do-modulo.md` (mesma raiz do vault).
- Ao encontrar um `[[link]]` relevante para a tarefa, localize o arquivo correspondente
  (grep/glob por `nome-do-modulo.md`) e leia-o antes de continuar.
- Não trate `[[link]]` como texto decorativo. Ele é uma instrução de navegação.

## Processo obrigatório antes de qualquer plano

1. Leia `_vault/_system/overview.md` primeiro (arquitetura, stack, glossário).
2. Identifique o(s) módulo(s) que a tarefa toca. Leia o `.md` de cada um.
3. Siga os `[[links]]` relevantes desses arquivos — não leia o vault inteiro, só o
   que está conectado ao que você vai mexer.
4. Preste atenção especial na seção **"Problemas conhecidos / gambiarras"** de cada
   módulo lido — nunca "conserte" algo que está documentado ali como intencional
   sem confirmar com o Lindão antes.
5. Só depois desses passos, monte o plano de implementação ou faça a alteração.

## Se o módulo não tem arquivo no vault

Não siga em frente como se o vault estivesse completo. Avise explicitamente:
"Não encontrei arquivo de contexto pra este módulo em `_vault/`. Quer que eu gere um
rascunho a partir do código antes de prosseguir, ou você prefere seguir sem ele?"

## Depois de qualquer alteração de código

Ao final da tarefa, lembre o Lindão de atualizar o `.md` do(s) módulo(s) alterado(s)
no vault (atualização é manual, não automática neste projeto). Uma linha basta:
"Lembra de atualizar o vault desse módulo antes de fechar."

## O que NUNCA fazer

- Nunca proponha um plano de implementação sem citar quais arquivos do vault você
  consultou para chegar nele.
- Nunca ignore uma gambiarra documentada achando que é "código ruim" a ser corrigido —
  se parecer errado, pergunte antes de mudar.
- Nunca leia o repositório de código inteiro como atalho para não usar o vault. O
  vault existe justamente pra evitar isso.
