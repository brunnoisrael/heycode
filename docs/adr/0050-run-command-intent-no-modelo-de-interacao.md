# 0050. `RunCommandIntent` no modelo de interação

## Status

Aceito. Data: 2026-11-13.

## Contexto

Os atalhos cadastrados no painel (ADR 0048) precisam de uma porta de entrada por voz. O modelo de interação da Alexa é fixo por skill, então cada atalho novo não pode virar uma intent nova. Spec: `docs/superpowers/specs/2026-11-13-heycode-painel-web-rastro-e-comandos.md` §5.

## Decisão

- Uma única intent aditiva, `RunCommandIntent`, com o slot livre `comando` (`AMAZON.SearchQuery`) e frases-guia obrigatórias do SearchQuery ("executar {comando}", "execute", "rode", "rodar", "dispare", "dispara"). O relay normaliza a fala e casa com nome ou apelido; empate e baixa semelhança são recusados.
- O slot `comando` entra no modelo de diálogo com elicitação (`Elicit.Slot.RunCommand.comando`, "Qual comando?"), para a pergunta quando a pessoa só diz "executar um comando".
- A alteração é textual e aditiva em `skill/interaction-model-pt-BR.json` (arquivo UTF-8 com quebras CRLF): só linhas ASCII novas, nenhum byte existente tocado; um teste garante o formato, os acentos íntegros e a presença das intents antigas.
- O Lambda do dono não conhece a intent e continua igual; ela só é tratada pelo endpoint compartilhado.
- Rejeitado: tipo de slot customizado por conta (exige a API de entidades dinâmicas e credenciais da Amazon por usuário) e uma intent por atalho (o modelo é compartilhado por todos).

## Consequências

Atalhos novos aparecem sem republicar a skill. Custo: o reconhecimento do slot livre é menos preciso que o de um tipo fechado, o que a confirmação por voz ("Confirma?") compensa; o modelo precisa ser reenviado ao console da Amazon uma vez, e `main` tem alteração local do dono nesse arquivo que pode conflitar no merge.
