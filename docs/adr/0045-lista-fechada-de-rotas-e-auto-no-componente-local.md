# 0045. Lista fechada de rotas e modo `auto` no componente local

## Status

Aceito. Data: 2026-11-13.

## Contexto

Com `bridge-call` (ADR 0044) o relay pede chamadas à ponte local. Um relay comprometido, ou um bug, não pode ganhar poder além do que a voz já tem hoje, e o modo `auto` não pode ser ligado só por voz na primeira vez (ADR 0031). Spec: `docs/superpowers/specs/2026-11-13-heycode-intents-no-modo-compartilhado.md` §3 e §4.

## Decisão

- O executor do componente local aceita somente os pares (método, caminho) que o Lambda do dono já usa, com consulta restrita às chaves esperadas (`offset`, `project`, `name`). Todo o resto devolve 403 sem tocar a ponte. A chamada vai a `127.0.0.1` com o segredo de controle lido do `config.env` local; o relay nunca o vê.
- `POST /mode` com `mode: auto` só é executado se `auto_allowed` estiver ligado em `relay.json`, o que somente o comando local `heycode relay-auto on` faz. Os outros modos passam sempre. Depois de ligado, o `auto` pode ser pedido por voz.
- O PIN de aprovação é verificado na ponte local; o relay o repassa sem guardar nem registrar.
- Rejeitado: executor genérico de HTTP (poder amplo) e liberar `auto` por voz se o dispositivo for aprovado (o dispositivo foi aprovado para operar, não para tirar a proteção).

## Consequências

O pior caso de um relay comprometido fica limitado às ações que a voz já permite, sem `auto` sem aval local. Custo: toda rota nova da ponte usada por voz exige atualizar a lista e o teste.
