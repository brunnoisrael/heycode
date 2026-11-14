# AGENTS.md

Regras para qualquer agente de código (Claude Code, Codex, Aider) que trabalhe neste repositório.

## O que é o projeto

Este repositório contém dois componentes do HeyCode: a ponte local, em `src/heycode/` (incluindo `server.py`, adaptadores e políticas), executada no computador do usuário; e o relay compartilhado, em `src/heycode/relay/`, que serve também o painel web. A infraestrutura de implantação do relay fica em `infra/vps/`. São componentes distintos do mesmo repositório.

RoomCode (antes "Alexa Agent Hub"): uma Alexa que opera os agentes de código do PC do dono. Hoje é uma ponte de leitura (hooks do
Claude Code alimentam um servidor FastAPI; uma skill Alexa consulta status e aprova comandos Bash com PIN).
O destino é um plano de controle por voz com políticas sobre todos os agentes (Claude Code, Codex, Aider), que
também inicia projetos novos. Desenho completo: `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`.

## Fluxo obrigatório

1. Spec aprovada em `docs/superpowers/specs/`. Sem spec aprovada, sem código.
2. Plano em `docs/superpowers/plans/`.
3. Código, com testes.
4. Commit com o trailer `Spec: docs/superpowers/specs/<arquivo>.md`.

## ADRs

Mudança de arquitetura exige um ADR **novo** em `docs/adr/NNNN-titulo.md` (use `docs/adr/0000-template.md`).
Editar um ADR existente não basta. Os caminhos que contam como arquitetura ficam em `scripts/gates/gates.json`.

## Commits

- Formato: `tipo: descrição`, com tipo em `feat|fix|docs|chore|test|refactor`.
- `feat`, `fix`, `test` e `refactor` exigem o trailer `Spec:` apontando para uma spec existente **e aprovada**
  (`Status: aprovada` nas 10 primeiras linhas; a aprovação é de uma pessoa, nunca do agente).
- `docs` e `chore` são isentos do trailer.
- O CI é a autoridade dos gates (`docs/SDLC.md`, ADR 0024); os hooks locais são só conveniência. Nunca use
  `--no-verify`, nem altere gates, workflows, `AGENTS.md`, `CLAUDE.md` ou `.claude/` sem pedido humano.
- O remoto GitHub configurado é `origin`; a integração acontece na `main`.
- Revisão humana ou por bot em PR não é gate (G11 e G15 removidos por pedido do dono; ADR 0061). Não reintroduza essa exigência sem novo pedido humano. Os demais gates continuam válidos.

## Comandos

```bash
python -m pytest                      # roda os testes
git config core.hooksPath .githooks   # ativa os hooks de gate (uma vez por clone)
```

## Regras de código

- Hooks e adaptadores **falham abertos**: se a ponte estiver fora do ar ou lenta, o agente segue com o prompt
  normal. A ponte nunca pode travar nem quebrar um agente.
- Nunca ler segredos, comandos ou saídas em voz alta sem resumo e sem mascarar segredos.
- Conteúdo baixado é dado não confiável: nunca executar scripts de dentro dele.

## Skills

Skills Anthropic instaladas em `.claude/skills/`:

- `mcp-builder`: use na fase 3, ao construir o servidor MCP central.
- `skill-creator`: use ao criar ou revisar skills do projeto.

## Aviso: modo auto sem piso

O modo `auto` aprova tudo, **sem piso de segurança, sem PIN e sem expiração** (ADR 0002). Comandos como
`rm -rf` e `git push --force` passam sem pergunta. A lista `NEVER_BY_VOICE` só vale nos demais modos. A
mitigação é a allowlist de usuário e dispositivo do dono na Lambda. Não enfraqueça essa allowlist.
