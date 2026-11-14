# HeyCode intents no modo compartilhado: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline).

**Goal:** Levar as intents do Lambda do dono para `/v1/alexa`, com executor local de lista fechada e gate do `auto`.

**Spec:** `docs/superpowers/specs/2026-11-13-heycode-intents-no-modo-compartilhado.md` (aprovada). ADRs 0044 e 0045.

## Global Constraints

- Commits `feat|fix|test|refactor` com `Spec:`; um por tarefa, em português. Lambda do dono e suíte existente intactos.
- Relay nunca conhece o segredo da ponte; PIN e texto de pedidos fora de log.
- Falas e atributos de sessão idênticos aos do `skill/lambda/index.js`.

## Tasks

- **P5.1 Protocolo:** esquemas `bridge-call` e `bridge-result`, enum de `envelope`, CHANGELOG, testes de contrato.
- **P5.2 Executor local:** lista fechada, `auto_allowed`, cliente despacha `bridge-call`; `heycode relay-auto on|off`; `heycode connect` liga o executor.
- **P5.3 Tratadores de intent** (`relay/voice.py`): porte de status, projetos, pendências, aprovar/negar, modo, aviso de fim, selecionar projeto, pedir ao agente, instrução ao aberto, resposta livre, confirmar/cancelar, criar projeto, cancelar execução, ajuda, parada, fallback.
- **P5.4 Integração em `/v1/alexa`:** ponte via hub, sessão da Alexa, cota, falha padrão; teste ponta a ponta com servidor real.
- **P5.5 Docs:** threat model, OPERATIONS, roteiro do beta.
