# 0029. Protocolo local↔relay versionado

## Status

Aceito. Data: 2026-11-13.

## Contexto

O relay (P3) e o componente local precisam evoluir separados. Spec: `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md` §3.

## Decisão

Envelopes JSON com `v`, `id` (UUIDv7), `ts`, `installation_id`, `type`, `payload`, `sig`, validados por JSON Schema 2020-12 em `protocol/v1/`. Campo opcional novo mantém a versão; remoção, renomeação ou obrigatório novo sobe a versão. Receptor ignora campos desconhecidos e recusa versão maior com `unsupported_version`. Conteúdo sensível é mascarado na máquina antes de entrar no envelope. Rejeitado: protocolo sem versão e formato binário (menos depurável).

## Consequências

Mudanças ficam auditáveis (G9) e clientes antigos continuam funcionando. Custo: manter `protocol/CHANGELOG.md` e testes de compatibilidade entre versões vizinhas.
