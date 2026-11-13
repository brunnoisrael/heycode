# Changelog do protocolo local-relay

Regras (ADR 0029): campo opcional novo mantém a versão; remoção, renomeação ou campo obrigatório novo sobe a versão.

## v1 (2026-11-13)

- Versão inicial: `envelope`, `status`, `decision-request`, `decision-response`, `instruction`, `run-result`, `pair-request`, `pair-confirm`, `error`.

### Adições compatíveis em v1 (2026-11-13)

- `payload.in_reply_to` (opcional, string): id do envelope de pedido a que a resposta se refere (ADR 0038).
- Quadros do relay para a máquina podem ter `sig` vazio (ADR 0038).
