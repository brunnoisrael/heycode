# HeyCode painel web, rastro e comandos: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline).

**Goal:** Painel web de gerenciamento servido pelo relay, rastro da voz e atalhos para agentes, sem ampliar o poder do relay.

**Spec:** `docs/superpowers/specs/2026-11-13-heycode-painel-web-rastro-e-comandos.md` (aprovada). ADRs 0046 a 0048.

## Global Constraints

- Commits `feat|fix|test|refactor` com `Spec:`; um por tarefa; português. Suíte anterior verde; caminho do dono intacto.
- Rastro sem conteúdo no relay. Nenhum HTML montado com dados do usuário.
- Cookie `HttpOnly`/`Secure`/`SameSite=Strict` e CSRF em toda escrita do painel.

## Tasks

- **W1 Sessão em cookie, CSRF e cabeçalhos de segurança:** `POST /app/api/login` etc., `current_account` aceita cookie, escrita exige `X-CSRF-Token`, CSP.
- **W2 Rastro:** tabela `audit`, gravação em `/v1/alexa` e nas decisões do painel, `GET /v1/audit`, limpeza de 30 dias; rota local `GET /voice/audit` e entrada na lista fechada; detalhe por `bridge-call`.
- **W3 Atalhos:** CRUD `/v1/commands`, casamento por nome/apelido/semelhança, `RunCommandIntent` no voice e no modelo de interação.
- **W4 Painel:** HTML/CSS/JS estáticos em `/app`, telas da spec §3.
- **W5 Teste de navegador e docs:** Playwright de ponta a ponta, threat model, OPERATIONS.
