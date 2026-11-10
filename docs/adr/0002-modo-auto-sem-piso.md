# 0002. Modo auto aprova tudo, sem piso, sem PIN e sem expiração

## Status

Aceito. Data: 2026-11-09.

## Contexto

O dono quer um modo em que a Alexa aprove tudo o que os agentes pedirem, sem fricção. A spec
(`docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`, §7 e §10) registra essa decisão como do dono.

## Decisão

No modo `auto`:

- Tudo é aprovado, sem piso de segurança: a lista `NEVER_BY_VOICE` não vale neste modo.
- Ativar o modo não exige PIN e não expira; basta pedir por voz ("modo auto").
- Vale para hooks, MCP e agentes iniciados pelo supervisor.

Nos demais modos a lista `NEVER_BY_VOICE` continua valendo, e o PIN segue existindo para os modos que o usarem.

## Consequências

- Risco aceito pelo dono: `rm -rf`, `git push --force` e similares passam sem pergunta no modo auto.
- Mitigação: a Lambda só aceita o ID de usuário e de dispositivo do dono (allowlist), além do `x-secret`, para que
  ninguém mais controle os agentes.
- A allowlist passa a ser a principal barreira de segurança e não pode ser enfraquecida sem novo ADR.
