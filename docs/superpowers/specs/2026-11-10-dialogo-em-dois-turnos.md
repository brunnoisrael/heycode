# Ditado e criação de projeto em dois turnos

Data: 2026-11-10. Status: aprovada pelo dono na sessão de deploy de 2026-11-10 ("pode sequenciar tudo").

## Problema

O build do modelo de interação falha no Alexa Developer Console com sete erros do tipo:

> Sample utterance "peça ao {agente} {instrucao}" in intent "AskAgentIntent" cannot include both a phrase
> slot and another intent slot.

A Alexa não aceita um slot de frase livre (`AMAZON.SearchQuery`) na mesma frase de exemplo que outro slot.
As cinco frases de `AskAgentIntent` e as duas de `CreateProjectIntent` violam a regra. Sem build, a skill não
pode ser publicada nem em modo desenvolvimento, e os dois recursos centrais (pedir uma instrução a um agente e
criar um projeto por voz) não existem na prática.

## Comportamento desejado

A frase livre sai da primeira frase e é pedida no turno seguinte.

Pedir instrução:

1. Dono: "peça ao codex" ou "peça ao claude no projeto painel".
2. Alexa: "Qual é a instrução para o codex?"
3. Dono: a instrução, em fala livre.
4. Alexa lê o que entendeu e pede confirmação, como já fazia (`POST /dictation`, depois `ConfirmIntent`).

Criar projeto:

1. Dono: "crie o projeto meu app com o claude".
2. Alexa: "Para que serve o projeto meu app?"
3. Dono: a descrição, em fala livre.
4. Alexa lê e pede confirmação (`POST /projects`, depois `ConfirmIntent`).

## Requisitos

- Nenhuma frase de exemplo combina slot de frase com outro slot. Frase com slot de frase tem texto fixo.
- `AskAgentIntent` sem `instrucao` responde com `Dialog.ElicitSlot` para `instrucao` e não chama a ponte.
- `CreateProjectIntent` sem `descricao` responde com `Dialog.ElicitSlot` para `descricao` e não chama a ponte.
- O que foi dito no primeiro turno (agente e projeto; nome e agente) fica em `sessionAttributes` e é usado no
  segundo turno se a Alexa não devolver os slots. Slot presente no pedido vence o valor guardado. O valor
  guardado é apagado ao chamar a ponte. Os demais atributos da sessão (`approval_id`) não são tocados.
- Sem agente (ou sem nome, no projeto), a skill explica a frase certa e não pede a frase livre.
- O pedido com todos os slots de uma vez continua funcionando, para não quebrar os testes e chamadas existentes.
- O modelo ganha a seção `dialog` (estratégia `SKILL_RESPONSE`, a skill conduz) e os `prompts` de elicitação.
- O contrato com a ponte não muda: mesmos corpos em `/dictation` e `/projects`.
- `SendInstructionIntent` não muda: já tem só o slot de frase, com texto fixo.

## Configuração na skill Alexa-hosted

A skill é Alexa-hosted, e o console não tem tela de variáveis de ambiente. A Lambda só lia `process.env`, então
na skill hospedada `BRIDGE_URL`, `BRIDGE_CONTROL_SECRET` e os IDs permitidos ficavam vazios.

- A Lambda carrega `env.json`, ao lado do `index.js`, na inicialização. O arquivo é um objeto `{ "NOME": "valor" }`.
- Variável já definida no ambiente vence o arquivo. Valor vazio no arquivo é ignorado.
- Sem o arquivo, nada muda. JSON inválido falha alto, em vez de subir uma skill sem allowlist.
- `skill/lambda/env.json` fica no `.gitignore` e existe só no editor da skill hospedada.

## Chamada HTTP sem `fetch` global

A Alexa-hosted roda a Lambda em Node 16 (`nodejs:16` no log de inicialização), que não tem `fetch` global. Toda
chamada à ponte falhava com `ReferenceError: fetch is not defined` e a Alexa dizia "Não consegui falar com o seu
computador". Os testes locais não pegavam, porque rodam em Node mais novo e trocam o `fetch` por um dublê.

- Sem `fetch` global, a Lambda usa `http`/`https` nativos (`httpFetch`), sem dependência nova.
- Com `fetch` global, nada muda.
- O substituto cobre o que `bridge()` usa: método, cabeçalhos, corpo em UTF-8, abort no limite de 5 s, e
  `ok`, `status` e `json()` na resposta.
- Testes removem o `fetch` e falam com um servidor HTTP local de verdade.

## Fora do escopo

Pedir o agente quando ele falta, confirmação nativa da Alexa (`Dialog.ConfirmIntent`) e mudanças na ponte.

## Verificação

- `npm test` em `skill/lambda`, com testes novos para os dois turnos, as regras do modelo, o `env.json` e a
  chamada sem `fetch`.
- Build do modelo no Alexa Developer Console sem erros.
- No simulador do console, com a ponte e o túnel no ar: "qual o status" fala o status real; "peça ao claude",
  depois a instrução, depois "esquece" percorre os dois turnos e cancela.
