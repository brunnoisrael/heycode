# Plano: rotas protegidas, borda anti-abuso e painel refinado

Spec: `docs/superpowers/specs/2026-11-14-heycode-painel-rotas-e-borda.md`. ADR: 0058.

O gate G12 limita cada PR a 400 linhas adicionadas (fora docs). O trabalho foi feito em sequência num ramo e fatiado em cinco ramos empilhados; cada PR tem como base o ramo anterior (o primeiro, a `main`).

| # | Ramo | Conteúdo | Linhas |
|---|---|---|---|
| 1 | `painel-borda/1-guarda` | spec; `RateLimiter` com memória limitada e `BanList`; guarda global por IP, teto de corpo, cabeçalhos, `/docs` desligado | 288 |
| 2 | `painel-borda/2-limites` | limites por e-mail, por conta e nas rotas sem login; memória do pareamento; limites do WebSocket; teto de Argon2 | 296 |
| 3 | `painel-borda/3-borda` | ADR 0058; Caddyfile, firewall por faixa da Cloudflare, tetos no uvicorn e no Compose; runbook | 203 |
| 4 | `painel-borda/4-visual` | CSS novo; visão geral, menu com ícones, cabeçalho de página, diálogo próprio | 350 |
| 5 | `painel-borda/5-telas` | telas em grade, formulários, página de vinculação OAuth; este plano | 141 |

## Conferência

- `python -m pytest` (com `PYTHONPATH=src` se houver outro `heycode` instalado no ambiente).
- `python scripts/gates/ci_range.py range <base> <ponta>` em cada trecho.
- Visual: capturas em 1280 px e 390 px, temas claro e escuro, de todas as telas.

## Fora do alcance do agente (dono)

1. Subir os ramos e abrir os PRs na ordem.
2. Na VM: `docker compose exec caddy caddy validate`, depois o runbook da seção 5 de `infra/vps/README.md`.
3. Na Cloudflare: proxy ligado, TLS "Full (strict)", WebSockets, regra de taxa.
4. `docs/security/threat-model.md` ainda não descreve as novas camadas (caminho de revisão humana).
