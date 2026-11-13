# Infraestrutura do relay

Estado: **somente configuração de exemplo e runbooks**. Nada foi contratado, publicado nem apontado em DNS; essas ações são do dono (spec do relay §9).

## O que existe

- `Dockerfile`: constrói o relay a partir do pacote `heycode`. `docker build -f infra/Dockerfile -t heycode-relay .` na raiz do repositório.
- `fly.toml.example`: exemplo para Fly.io (ADR 0035; trocável por qualquer plataforma que rode contêiner com volume e WebSocket).
- Variáveis: `RELAY_DB` (obrigatória, caminho do SQLite no volume), `RELAY_DAILY_QUOTA`, `RELAY_SYNC_TIMEOUT`.

## Limites conhecidos do MVP

- **Uma única instância** (hub e códigos de pareamento em memória).
- **SQLite em volume persistente**, não Postgres: a interface `Repository` já isola o banco, mas só o adaptador SQLite foi escrito. O adaptador Postgres e a restauração testada de backup são trabalho antes do beta (P4); até lá, faça backup do volume (`docs/runbooks/restauracao-do-banco.md`).
- A origem do cliente vem do `X-Forwarded-For` do proxy (ADR 0040): **não exponha a porta 8080 direto**.
- O TLS termina na plataforma; o cliente local recusa `ws://` fora de localhost.

## O que o dono precisa fazer (não faço sem pedido explícito)

1. Criar a conta na plataforma e liberar um teto de orçamento.
2. Criar `staging-api.` e `staging-app.` em `heycode.dev.br` apontando para o serviço (`ponte.` fica intacto).
3. Ativar `privacy@`, `support@`, `security@` com SPF, DKIM e DMARC.
4. Cadastrar um segundo administrador no registrador, na plataforma e no GitHub.

Reconstruir o staging por outra pessoa (critério 6 da spec) só será possível depois do item 1 e do adaptador Postgres.
