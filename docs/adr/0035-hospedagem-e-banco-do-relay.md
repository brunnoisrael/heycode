# 0035. Hospedagem e banco do relay

## Status

Aceito. Data: 2026-11-13.

## Contexto

O relay (spec `docs/superpowers/specs/2026-11-13-heycode-relay-mvp.md` §3 e §6) precisa de compute com WebSocket de longa duração, estado durável e operação reproduzível por outra pessoa.

## Decisão

- Um contêiner Python (o mesmo pacote `heycode`, aplicação `heycode.relay`) em plataforma gerenciada com WebSocket; sugestão inicial Fly.io, trocável porque o contêiner não depende da plataforma. A escolha e a conta são do dono (envolve cobrança).
- Postgres gerenciado com backup e restauração testada em produção; SQLite atrás da mesma interface de repositório em desenvolvimento e testes. O código só fala com a interface `Repository`.
- MVP com **uma única instância** do contêiner: o hub de WebSockets e os códigos de pareamento pendentes ficam em memória (códigos duram 5 min e se perdem num reinício sem dano). Escala horizontal exige ADR novo (barramento entre instâncias).
- Infraestrutura como código em `infra/`, sem segredos.
- Rejeitado: função serverless (não mantém WebSocket); banco só em memória (perde contas e revogações).

## Consequências

Deploy simples e reproduzível, custo previsível. Custo: instância única é ponto único de falha no MVP; o componente local reconecta sozinho e os agentes seguem em falha aberta.
