# 0047. Rastro de auditoria: metadados no relay, detalhe no computador

## Status

Aceito. Data: 2026-11-13.

## Contexto

A pessoa precisa ver o que a voz aprovou e fez. A política de privacidade promete que o relay não guarda conteúdo de pedidos nem saídas de agentes. Spec: `docs/superpowers/specs/2026-11-13-heycode-painel-web-rastro-e-comandos.md` §4.

## Decisão

- O relay grava por interação (autêntica) da Alexa e por decisão no painel: instante, dispositivo, computador, tipo, resultado e nome do atalho, sem texto de pedido, PIN ou saída de agente. Retenção de 30 dias, com limpeza automática. `GET /v1/audit` só devolve a própria conta.
- O detalhe vem do computador sob demanda, por `bridge-call` a `GET /voice/audit?limit=`, rota nova somente de leitura na lista fechada do executor (ADR 0045), com segredos mascarados na origem. O relay repassa e esquece.
- Rejeitado: guardar o conteúdo no relay (quebra a promessa de privacidade e cria um alvo valioso) e mostrar só o que o relay vê (rastro sem utilidade).

## Consequências

Rastro útil sem o relay conhecer o conteúdo. Custo: o detalhe só aparece com o computador conectado, e o executor local ganha uma rota (atualizar a lista e o teste de equivalência).
