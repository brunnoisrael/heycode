# HeyCode comandos locais: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline).

**Spec:** `docs/superpowers/specs/2026-11-13-heycode-comandos-locais-scripts-e-webhooks.md` (aprovada). ADRs 0051 e 0052.

## Global Constraints

- Commits `feat|fix|test|refactor` com `Spec:`; um por tarefa; português. Suíte anterior verde; Lambda do dono e atalhos de agente intactos.
- Nada falado entra em argv, URL, corpo ou cabeçalho. Sem shell. Segredos de cabeçalho nunca fora da máquina.
- O relay e o painel só leem resumo e só desligam.

## Tasks

- **C1 Registro e validação** (`heycode/commands.py`): modelos, carga e gravação atômica, casamento.
- **C2 Execução** (mesmo módulo): script sem shell, webhook, pendência por risco, travas.
- **C3 Rotas da ponte local** (`app.py`), histórico e `/voice/audit`.
- **C4 Executor e relay:** lista fechada, voz (`RunCommandIntent` cai nos comandos locais, ConfirmIntent/ApproveIntent/Cancel com pendência), rotas `/v1/computers/{id}/commands`.
- **C5 CLI** `heycode command add|list|remove|enable|disable|test`.
- **C6 Painel** "Comandos do computador" e teste em navegador.
- **C7 Docs:** threat model, OPERATIONS.
