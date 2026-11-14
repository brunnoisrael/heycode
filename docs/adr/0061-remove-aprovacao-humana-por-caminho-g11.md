# 0061. Remove a aprovação humana por caminho (G11 e a parte humana do G15)

## Status

Aceito. Data: 2026-11-14. Decisão do dono. Altera o ADR 0024 (esteira obrigatória).

## Contexto

O G11 exigia aprovação de um dono humano, diferente do autor, em todo PR que tocasse gates, workflows, regras dos agentes ou caminhos sensíveis (`protected_paths` e `human_review_paths`, espelhados no CODEOWNERS). Com um único dono e todo o código escrito por agentes, cada mudança desses caminhos parava à espera dele. O dono quer uma esteira totalmente agêntica, que se implementa e evolui por revisão adversarial entre agentes.

## Decisão

- O G11 sai de `enabled_gates`; `protected_paths`, `human_review_paths` e `human_owners` saem de `scripts/gates/gates.json`.
- O job `human-approval` sai do CI e o modo `approvals` sai de `scripts/gates/ci_range.py`.
- `.github/CODEOWNERS` e o teste que o espelhava são removidos.
- O G15 passa a ser só a revisão independente por agente (`agent-review`), que continua falhando fechada sem `AGENT_REVIEW_BOT`.
- A aprovação humana da spec (G2) não muda.

## Consequências

- Um agente pode alterar os próprios gates num PR; o que segura é o CI, o `agent-review` e o ruleset da `main`. Esse risco é aceito pelo dono.
- O ruleset do GitHub precisa deixar de exigir o check `human-approval` e a aprovação de code owner, senão os PRs ficam travados.
- As regras de conduta do `AGENTS.md` e do `docs/SDLC.md` continuam valendo até o dono decidir alterá-las.
