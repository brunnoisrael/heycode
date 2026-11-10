# 0016. Frase livre pedida em um segundo turno

## Status

Aceito. Data: 2026-11-10.

## Contexto

O modelo de interação não compilava no Alexa Developer Console: a Alexa recusa uma frase de exemplo que combine
um slot de frase livre (`AMAZON.SearchQuery`) com outro slot. `AskAgentIntent` ("peça ao {agente} {instrucao}") e
`CreateProjectIntent` ("crie o projeto {nome} com o {agente} para {descricao}") dependiam dessa combinação, que
vinha dos ADRs 0008, 0010 e 0013. Os testes locais não pegavam o erro, porque só o build da Alexa aplica a regra.
Spec: `docs/superpowers/specs/2026-11-10-dialogo-em-dois-turnos.md`.

## Decisão

- A frase livre sai da primeira frase. `AskAgentIntent` recebe só agente e projeto; `CreateProjectIntent` recebe
  só nome e agente. A Lambda pede `instrucao` ou `descricao` no turno seguinte com `Dialog.ElicitSlot`.
- O modelo ganha a seção `dialog` com estratégia `SKILL_RESPONSE`: a skill conduz o diálogo, a Alexa não delega
  sozinha.
- O contexto do primeiro turno fica em `sessionAttributes` (`ask`, `create`) e é apagado ao chamar a ponte. Slot
  presente no pedido vence o valor guardado.
- Um teste do modelo passa a reprovar qualquer frase que misture slot de frase com outro slot.
- Alternativa rejeitada: um intent por agente com o nome fixo na frase ("peça ao claude {instrucao}"). Compila,
  mas não comporta o projeto, que é dinâmico, e triplica os intents.
- Alternativa rejeitada: trocar `AMAZON.SearchQuery` por um tipo custom com exemplos. Um tipo custom não captura
  fala livre com fidelidade.

## Consequências

O modelo compila e a skill pode ser publicada. Pedir uma instrução custa um turno a mais, o que também separa
"para quem" de "o quê" e reduz o erro de reconhecimento do agente dentro de uma frase longa. O contrato com a
ponte não muda. A regra da Alexa agora tem teste local, mas a prova final continua sendo o build no console.
