# 0001. Arquitetura híbrida: motor de políticas central, hub MCP, hooks e supervisor

## Status

Aceito. Data: 2026-11-09.

## Contexto

A ponte atual só serve ao Claude Code, só em um sentido, e guarda o estado em memória. O dono quer a Alexa como
plano de controle por voz sobre todos os agentes de código do PC (Claude Code, Codex, Aider), incluindo agentes
já abertos e tarefas pedidas pela própria Alexa. Ver `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`
(§6 e §8).

## Decisão

Adotar a abordagem C (híbrida): um motor de políticas central (`decidir(agente, projeto, pedido)`), com estado em
SQLite, exposto por um servidor MCP e por hooks para agentes abertos, mais um supervisor que inicia agentes
headless a pedido da Alexa. O motor é o único lugar onde os modos de política existem.

Alternativas rejeitadas:

- **A. Hub MCP + hooks (cooperativo):** atende agentes já abertos, mas não consegue mandar tarefa a uma sessão
  interativa existente, o que impede "peça ao Codex para...".
- **B. Supervisor puro:** dá controle total e cobre "peça ao X para Y", mas não alcança agentes abertos na mão.

## Consequências

- Cobre os dois cenários (agentes abertos e tarefas iniciadas pela Alexa).
- É a maior obra das três; a entrega é feita em fases (spec §9).
- Exige cuidado para que hooks e adaptadores falhem abertos e para que política e fila sobrevivam a reinícios.
- O Aider pode ficar só no supervisor se não aceitar MCP (teste de viabilidade na fase 3).
