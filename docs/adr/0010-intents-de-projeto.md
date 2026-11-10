# 0010. Intents de projeto e checagem do ID da skill

## Status

Aceito. Data: 2026-11-09.

## Contexto

A fase 5 deixa o dono criar um projeto novo por voz e já disparar o agente na primeira tarefa (ADR 0009). A skill precisa de um intent para isso, e a confirmação passa a ser unificada na ponte (projeto pendente primeiro, depois ditado). Além disso, a allowlist por `userId` e `deviceId` não impede que outra skill apontada para a mesma Lambda a invoque. Spec: `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (G5, §10).

## Decisão

- `CreateProjectIntent` tem os slots `nome` (tipo customizado `NOME_PROJETO`), `agente` (`AGENTE`) e `descricao` (`AMAZON.SearchQuery`). Faz `POST /projects` com `{name, agent, description}`, fala a resposta e mantém a sessão aberta com "Confirma?" quando `ok` não é falso. Slot faltando ou agente inválido não chama a ponte.
- `ConfirmIntent` e `CancelDictationIntent` passam a chamar `POST /confirm` e `POST /cancel`; a ponte decide se confirma o projeto ou o ditado. Os endpoints `/dictation/*` seguem existindo na ponte por compatibilidade.
- Se `ALLOWED_SKILL_ID` estiver definido e o `applicationId` da requisição for diferente, a Lambda recusa com "Acesso negado" antes de qualquer chamada à ponte. Ausente, a checagem é ignorada e userId e deviceId continuam obrigatórios.
- Alternativas rejeitadas: manter `/dictation/confirm` e escolher o endpoint na skill (a skill não sabe o que está pendente); tornar `ALLOWED_SKILL_ID` obrigatório (quebraria instalações existentes).

## Consequências

- Limitação conhecida: slots de tipo personalizado não restringem a fala. A Alexa pode devolver valores fora da lista de `NOME_PROJETO` (os valores do modelo são só exemplos). A ponte portanto trata o nome como entrada não confiável e o normaliza em slug dentro de `PROJECTS_ROOT`.
- A fala de confirmação relê o nome final e a descrição antes de criar qualquer coisa.
- Outra skill chamando a mesma Lambda é barrada quando `ALLOWED_SKILL_ID` está configurado; documentar como descobrir o ID fica para o guia de deploy.
