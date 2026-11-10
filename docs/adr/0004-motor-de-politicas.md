# 0004. Motor de políticas com modos manual, auto e decisões

## Status

Aceito. Data: 2026-11-09.

## Contexto

Hoje a decisão de aprovar, negar ou perguntar está espalhada em `bridge/server.py`. A spec
(`docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`, §2 G1/G2, §7 e §10) pede modos controláveis por voz
e um único ponto de decisão para hooks, MCP e supervisor.

## Decisão

- `bridge/policy` expõe `decidir(agent, project, tool_name, tool_input, store)`, o único lugar onde os modos existem.
  Retorna `allow`, `deny`, `ask_voz` ou `ask_teclado`. O `store` só precisa de `get_policy`.
- Três modos: `manual` (tudo pergunta por voz, destrutivo vai ao teclado), `auto` (tudo aprovado, sem piso, ver
  ADR 0002) e `decisoes` (rotina aprovada, o resto pergunta por voz, destrutivo vai ao teclado).
- "Fim de ciclo" é a flag `report_on_end`, ortogonal ao modo, para permitir combinações (decisão de projeto).
- A regra é por ferramenta, com lista de padrões (`NEVER_BY_VOICE`, movida de `server.py` para `rules.py`) e sem LLM:
  determinística, rápida e testável. Rotina: `Read`, `Grep`, `Glob`, `Edit`, `Write`, `MultiEdit` e `Bash` não destrutivo.
- Falha aberto: entrada malformada, modo desconhecido ou qualquer exceção resulta em `ask_teclado`, nunca em
  `allow` e nunca em travamento do agente.
- Alternativa rejeitada: classificar comandos com um LLM (latência, custo e não determinismo).

## Consequências

- Os modos ficam testáveis em tabela e o servidor vira só cliente do motor.
- Padrões por regex podem ter falsos positivos (ex.: "deploy" em qualquer parte do comando), que caem no teclado:
  erro para o lado seguro.
- Ferramentas desconhecidas pedem voz em `decisoes`; novas rotinas exigem alterar `rules.py`.
