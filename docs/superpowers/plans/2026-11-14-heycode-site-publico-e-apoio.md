# Plano: site público, identidade e níveis de apoio

Spec: `docs/superpowers/specs/2026-11-14-heycode-site-publico-e-apoio.md`. ADR: 0059. Continua a pilha de `docs/superpowers/plans/2026-11-14-heycode-painel-rotas-e-borda.md`.

Quatro ramos empilhados; o primeiro tem como base `painel-borda/5-telas`. Cada PR fica abaixo de 400 linhas adicionadas (G12).

| # | Ramo | Conteúdo | Linhas |
|---|---|---|---|
| 6 | `site-apoio/1-niveis` | spec e ADR 0059; `plans.py`, `grant.py`, tabela `plans`, `GET /v1/plan`, `PUT /v1/plan/interest`, limites por nível | 294 |
| 7 | `site-apoio/2-plano` | tela "Plano e apoio" no painel; marca do anel com prompt | 96 |
| 8 | `site-apoio/3-inicio` | rotas `/`, `/apoie` e `/site/{nome}`; `index.html`; `site.js`; testes estáticos | 312 |
| 9 | `site-apoio/4-estilo` | `site.css`; `apoie.html`; testes em navegador; runbook dos níveis; este plano | 376 |

Entre o PR 8 e o PR 9 a página inicial existe sem estilo; mescle os dois em seguida.

## Conferência

- `python -m pytest` (com `PYTHONPATH=src` se houver outro `heycode` instalado no ambiente).
- `python scripts/gates/ci_range.py range <base> <ponta>` em cada trecho.
- Visual: capturas da página inicial e da página de apoio em 1360 px e 390 px.

## Próximas specs (fora desta entrega)

1. **Comunidade:** catálogo de pacotes com link do repositório, polegar verde e vermelho e percentual de aprovação; publicação pela conta; moderação.
2. **Carga automática:** `heycode addon install` no computador, com commit fixado e confirmação local; pacotes só de atalhos instalados pelo painel.
3. **Recursos dos níveis de apoio:** aviso da Alexa quando o agente termina e resumo matinal por voz (hoje marcados como "em construção").
4. **Cobrança:** só se o interesse medido justificar e o dono tiver como receber.
