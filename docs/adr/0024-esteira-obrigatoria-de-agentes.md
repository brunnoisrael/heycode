# 0024. Esteira obrigatória de agentes: CI como autoridade e gates protegidos

## Status

Proposto. Data: 2026-11-13.

## Contexto

Todo o código do HeyCode será produzido por agentes, e o projeto pretende ser usado e mantido por outras pessoas sem depender do dono. Hoje há dois gates locais (trailer `Spec:` e ADR novo), que um agente consegue burlar com `--no-verify` ou editando o próprio gate. Spec: `docs/superpowers/specs/2026-11-13-esteira-obrigatoria-de-agentes.md`.

## Decisão

- O **CI é a autoridade**: todos os gates (G1 a G16) rodam sobre cada commit do PR e são obrigatórios para o merge. Os hooks locais são conveniência.
- Os gates **falham fechados**; os hooks dos agentes seguem falhando abertos (`AGENTS.md`).
- Os **caminhos dos gates e das regras dos agentes são protegidos**: alterá-los exige aprovação humana via CODEOWNERS.
- Spec precisa de `Status: aprovada` dada por uma pessoa; agentes não aprovam specs.
- Revisão independente por agente de contexto novo é um gate, mas nunca o único: caminhos sensíveis exigem aprovação humana.
- "Pronto" é a saída do CI colada no PR, não o relato do agente.

Alternativas rejeitadas: confiar só em hooks locais (burláveis); confiar nas instruções do `AGENTS.md` sem gate (um agente pode ignorá-las); revisão exclusivamente por agente (mesmos pontos cegos do autor).

## Consequências

Mudanças em gates e regras passam a depender de uma pessoa, o que adiciona um ponto de atrito deliberado e exige pelo menos dois humanos donos para não virar gargalo. O repositório precisa de remoto GitHub com proteção de branch (ação do dono). Ferramentas baixadas (gitleaks, ruff) são fixadas por versão e checksum. Qualquer spec anterior sem `Status: aprovada` não pode ser citada em novos commits até uma pessoa a aprovar.
