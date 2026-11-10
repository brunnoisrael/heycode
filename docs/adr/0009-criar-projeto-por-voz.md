# 0009. Criar projeto por voz

## Status

Aceito. Data: 2026-11-09.

## Contexto

A meta G5 da spec (`docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`, fases 5 e 6) é iniciar um
projeto novo pela Alexa e já disparar o agente na primeira tarefa. O nome do projeto chega por voz, portanto é
entrada não confiável: pode tentar sair da pasta de projetos (`../x`, `C:\Windows`) ou usar nomes reservados do
Windows (`con`, `nul`). A criação também escreve em disco, então exige confirmação como o ditado (ADR 0008).

## Decisão

- Novo pacote `bridge/projects`. `slugify` reduz o nome a `[a-z0-9-]` com no máximo 40 caracteres, sem
  acentos, e recusa vazio e nomes reservados. `scaffold_project` só cria `PROJECTS_ROOT/<slug>`, confere que o
  pai real é a raiz, nunca sobrescreve (`FileExistsError`) e apaga o que criou se algo falhar no meio.
- O projeto nasce com git local (`main`), `AGENTS.md` próprio e enxuto, `docs/superpowers/specs/`, `docs/adr/`,
  `scripts/gates/` e `.githooks/` copiados deste repositório (hooks com LF), `core.hooksPath=.githooks` e o
  commit `chore: scaffold` (tipo isento, os hooks não o bloqueiam). `user.name`/`user.email` locais só são
  definidos se não houver configuração global.
- `ProjectCreator` segue o padrão de `Dictation`: um pendente, validade de 60 s, relógio injetável, segredos
  mascarados com `policy.redact.mask_secrets`. A confirmação cria o projeto e chama `start_run` com um prompt
  que manda escrever a spec antes de qualquer código.
- HTTP: `POST /projects`, e `/confirm` e `/cancel` unificados (projeto pendente primeiro, depois ditado).
  `/dictation/confirm` e `/dictation/cancel` continuam funcionando.
- Alternativas rejeitadas: aceitar caminho completo por voz (risco de escapar da raiz) e criar a pasta já na
  proposta (deixaria lixo se o dono não confirmar).

## Consequências

Criar projeto fica seguro por construção e o gate de spec vale para projetos novos. O custo é depender de
`git` e `python` no PATH para os hooks do projeto novo. Um nome ambíguo por voz vira um slug que o dono ouve
antes de confirmar; se já existir, a ponte recusa e avisa.
