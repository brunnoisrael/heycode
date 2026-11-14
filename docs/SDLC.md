# SDLC do HeyCode

Este documento vale para qualquer agente ou pessoa que altere o repositório. Detalhe dos gates: `docs/superpowers/specs/2026-11-13-esteira-obrigatoria-de-agentes.md`. Decisão: `docs/adr/0024-esteira-obrigatoria-de-agentes.md`.

## Regra de ouro

O CI é a autoridade. Hook local ajuda a falhar cedo, mas o CI repete tudo, em cada commit do PR. Contornar um gate (`--no-verify`, editar o gate, desligar um check) não passa no CI, e alterar os caminhos protegidos exige aprovação humana. "Pronto" é a saída do CI, nunca o relato do agente.

## Etapas

| # | Etapa | Artefato | Quem aprova |
|---|---|---|---|
| 1 | Intake | Issue com problema, usuário afetado e risco | Mantenedor |
| 2 | Spec | `docs/superpowers/specs/*.md` com `Status: aprovada` | Humano |
| 3 | ADR (se mudar arquitetura) | `docs/adr/NNNN-titulo.md` **novo** | Humano nos caminhos sensíveis |
| 4 | Plano | `docs/superpowers/plans/*.md` | Revisão de agente independente |
| 5 | Implementação TDD | Teste que falha, depois código mínimo | Gates locais |
| 6 | Revisão independente | Agente de contexto novo revisa o diff contra spec e plano | Check `agent-review` |
| 7 | CI | G1 a G16, refeitos do zero, em matriz de sistemas | Automático |
| 8 | Aprovação humana | Obrigatória em `human_review_paths` e em qualquer mudança de gate | Humano (CODEOWNERS) |
| 9 | Merge | Squash, histórico linear, sem force push | Proteção de branch |
| 10 | Release | Semver por Conventional Commits, changelog, artefatos assinados, SBOM | Pipeline, humano na primeira vez |
| 11 | Operação | SLOs, alertas, runbooks, resposta a incidente | Mantenedor de plantão |
| 12 | Retrospectiva | Toda falha vira teste, gate ou ADR | Mantenedor |

## Definição de pronto

- Spec aprovada e plano rastreáveis pelo trailer `Spec:`.
- Teste novo para o comportamento, visto falhar antes de passar.
- Todos os gates verdes no CI, com a saída colada na seção "Evidência" do PR.
- Docs e `CHANGELOG.md` atualizados quando houver mudança visível.
- Aprovação humana quando tocar caminhos protegidos ou sensíveis.

## O que um agente nunca faz

- Alterar gates, workflows, `AGENTS.md`, `CLAUDE.md`, `.claude/` ou CODEOWNERS sem pedido e aprovação humana explícitos.
- Marcar uma spec como aprovada. A aprovação é de uma pessoa.
- Usar `--no-verify`, desligar um gate ou baixar o piso de cobertura para a tarefa passar.
- Executar scripts baixados da internet, ou publicar, fazer push em branch compartilhada, mesclar ou criar repositório remoto sem pedido humano.
- Ler segredos em voz alta ou colocá-los em log, commit ou PR.

## Commits

Formato `tipo: descrição` (`feat|fix|docs|chore|test|refactor`). `feat`, `fix`, `test` e `refactor` exigem o trailer `Spec:`. Um commit por tarefa do plano. Não há limite de tamanho de PR (o G12 foi removido pelo ADR 0060).
