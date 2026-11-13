# Runbook: backup e restauração do banco

Estado atual (MVP): SQLite em volume persistente. O adaptador Postgres gerenciado com backup automático é trabalho da P4; este runbook cobre o que existe.

## Backup

1. `sqlite3 /data/relay.db ".backup /data/backup-AAAAMMDD.db"` dentro da máquina (consistente com o relay no ar) ou snapshot de volume da plataforma.
2. Copie o backup para fora da plataforma, em local com acesso restrito. Ele contém hashes de senha e chaves públicas, nunca segredos em claro.

## Restaurar

1. Pare o relay (instância única).
2. Substitua `/data/relay.db` pelo backup e suba de novo; confira `/health`.
3. Sessões e instalações voltam ao estado do backup: instalações revogadas depois dele voltam a valer, então **revogue de novo** o que foi revogado no intervalo.
4. **Teste a restauração** num ambiente de staging a cada trimestre e registre o resultado; backup nunca restaurado não conta.
