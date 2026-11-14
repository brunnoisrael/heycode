# 0039. Relay do MVP com SQLite em volume até existir o adaptador Postgres

## Status

Aceito. Data: 2026-11-13. Ajusta o ADR 0035 (não o substitui).

## Contexto

O ADR 0035 prevê Postgres gerenciado em produção atrás da interface `Repository`. Nesta entrega só o adaptador SQLite foi escrito e testado; o relay roda como instância única (mesmo ADR). Spec: `docs/superpowers/specs/2026-11-13-heycode-relay-mvp.md` §3 e §6.

## Decisão

- O staging e o beta fechado rodam com SQLite num volume persistente (`RELAY_DB`), com instância única, backup manual documentado e restauração testada trimestralmente (`docs/runbooks/restauracao-do-banco.md`).
- O relay recusa subir sem `RELAY_DB`, para nunca usar banco em memória por engano.
- O adaptador Postgres é pré-requisito de produção pública (P6); o contrato é a interface `Repository`. Escala horizontal continua exigindo ADR próprio.
- Rejeitado: esperar o Postgres para validar o produto (atrasa o beta sem reduzir risco de segurança, que está na identidade e no roteamento).

## Consequências

Menos peças para operar no beta. Custo: sem backup gerenciado, um disco perdido perde contas e revogações; mitigado por backup fora da plataforma e pelo volume replicado da plataforma. A restauração não propaga revogações feitas depois do backup (o runbook manda revogar de novo).
