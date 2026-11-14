# SDLC do HeyCode

Este documento vale para qualquer agente ou pessoa que altere o repositório. Detalhe dos gates: `docs/superpowers/specs/2026-11-13-esteira-obrigatoria-de-agentes.md`. Decisão: `docs/adr/0024-esteira-obrigatoria-de-agentes.md`.

## Regra de ouro

O CI é a autoridade. Hook local ajuda a falhar cedo, mas o CI repete os gates na branch de entrega antes da integração. Contornar um gate (`--no-verify`, editar o gate, desligar um check) não é aceito. "Pronto" é a saída do CI para o commit exato, nunca o relato do agente. A ativação do fluxo depende também da configuração descrita no ADR 0064.

## Etapas

| # | Etapa | Artefato | Quem aprova |
|---|---|---|---|
| 1 | Intake | Issue com problema, usuário afetado e risco | Mantenedor |
| 2 | Spec | `docs/superpowers/specs/*.md` com `Status: aprovada` | Humano |
| 3 | ADR (se mudar arquitetura) | `docs/adr/NNNN-titulo.md` **novo** | Mantenedor |
| 4 | Plano | `docs/superpowers/plans/*.md` | Mantenedor |
| 5 | Implementação TDD | Teste que falha, depois código mínimo | Gates locais |
| 6 | Revisão independente | Parecer no SHA da entrega, fora de PR | Identidade revisora configurada |
| 7 | CI | Gates ativos, refeitos do zero, em matriz de sistemas (G11 e G15 removidos) | Automático |
| 8 | Aprovação humana | Removida (ADR 0061); vale só a aprovação da spec | — |
| 9 | Integração | Atualização linear da main com o SHA validado, sem PR ou force push | Proteção de branch |
| 10 | Release | Semver por Conventional Commits, changelog, artefatos assinados, SBOM | Pipeline, humano na primeira vez |
| 11 | Operação | SLOs, alertas, runbooks, resposta a incidente | Mantenedor de plantão |
| 12 | Retrospectiva | Toda falha vira teste, gate ou ADR | Mantenedor |

## Definição de pronto

- Spec aprovada e plano rastreáveis pelo trailer `Spec:`.
- Teste novo para o comportamento, visto falhar antes de passar.
- Todos os gates verdes no CI para o SHA a integrar; a mensagem do commit final inclui seção `## Evidência` com comando e saída reais.
- Parecer independente bem-sucedido no mesmo SHA, com a identidade configurada distinta do autor.
- Docs e `CHANGELOG.md` atualizados quando houver mudança visível.

## O que um agente nunca faz

- Alterar gates, workflows, `AGENTS.md`, `CLAUDE.md` ou `.claude/` sem pedido humano explícito.
- Marcar uma spec como aprovada. A aprovação é de uma pessoa.
- Usar `--no-verify`, desligar um gate ou baixar o piso de cobertura para a tarefa passar.
- Executar scripts baixados da internet, ou publicar, fazer push em branch compartilhada, mesclar ou criar repositório remoto sem pedido humano.
- Ler segredos em voz alta ou colocá-los em log, commit ou PR.

## Commits

Formato `tipo: descrição` (`feat|fix|docs|chore|test|refactor`). `feat`, `fix`, `test` e `refactor` exigem o trailer `Spec:`. Um commit por tarefa do plano, com no máximo 400 linhas adicionadas conforme o G12.
