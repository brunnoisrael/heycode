# HeyCode relay MVP (P3): plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Steps use checkbox syntax.

**Goal:** Relay em código e testes que leva um pedido da skill ao agente local e de volta, isolando contas, sem tocar o caminho do dono. Infra real, DNS e cobrança ficam com o dono.

**Architecture:** `src/heycode/relay/` (FastAPI): `repo.py` (interface `Repository` + SQLite), `accounts.py`, `app.py` (HTTP + WebSocket), `hub.py` (conexões por instalação), `limits.py`. Cliente local em `src/heycode/relay_client.py`. Reusa `heycode.identity` e `heycode.protocol` da P2.

**Tech Stack:** FastAPI, argon2-cffi, SQLite (Postgres em produção via mesma interface), pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-heycode-relay-mvp.md` (aprovada). ADRs 0035 a 0037.

## Global Constraints

- Commits `feat|fix|test|refactor` com `Spec:` da spec acima; um commit por tarefa, em português.
- Caminho do dono intacto; suíte existente verde.
- Autoridade de conta e instalação vem sempre da autenticação, nunca do corpo (testes de isolamento).
- Segredo nunca em log do relay; senha só como hash Argon2id; token de sessão só como hash.
- Agentes e componente local falham abertos; o relay falha fechado em identidade.
- Dependência nova fixada em `constraints.txt` e `pyproject.toml` (G8).

## Review Focus

1. Conta A lê, aciona ou revoga instalação de B (IDs reaproveitados, corridas).
2. Enumeração de contas pelo login; força bruta.
3. Envelope assinado válido por uma instalação revogada ou de outra conta.
4. Pedido pendente que nunca expira; máquina offline.
5. Segredo em log ou resposta.

## Task P3.1: Repositório, contas e sessões

**Files:** Create `src/heycode/relay/{__init__,repo,accounts}.py`, `tests/relay/test_accounts.py`. Modify `pyproject.toml`, `constraints.txt` (argon2-cffi).

- [ ] Testes: cadastro, e-mail duplicado recusado, senha curta recusada, login ok, senha errada e e-mail inexistente com o mesmo erro, token guardado só como hash, sessão expira em 12 h, logout revoga, hash Argon2id no banco.
- [ ] Rodar; esperado FAIL. Implementar; rodar; esperado PASS.
- [ ] Commit `feat: contas e sessoes do relay`.

## Task P3.2: Pareamento e instalações via relay

**Files:** Create `src/heycode/relay/app.py` (rotas de conta, pareamento, instalações), `tests/relay/test_pairing_api.py`.

- [ ] Testes: emitir código autenticado, resgatar sem login (origem = IP), confirmar nos dois lados cria instalação, listar só as próprias, revogar a própria, revogar a de outra conta recusado (404), limite de 2 instalações, código reaproveitado recusado.
- [ ] Rodar; FAIL. Implementar; PASS.
- [ ] Commit `feat: pareamento e instalacoes no relay`.

## Task P3.3: Hub WebSocket, endpoint da skill e limites

**Files:** Create `src/heycode/relay/{hub,limits}.py`, ampliar `app.py`, `tests/relay/test_hub.py`, `tests/relay/test_isolation_relay.py`.

- [ ] Testes: máquina conecta por WebSocket com envelope assinado e recebe pedido; assinatura inválida, replay e instalação revogada recusados; segunda conexão da mesma instalação substitui a primeira; skill de A não alcança instalação de B; máquina offline responde `offline` na hora; sem resposta em 4 s devolve `pending`; resultado tardio fica disponível; cota de 200 pedidos/dia; limite de taxa no login.
- [ ] Rodar; FAIL. Implementar; PASS.
- [ ] Commit `feat: hub de conexoes, endpoint da skill e limites`.

## Task P3.4: Cliente local e `heycode pair`

**Files:** Create `src/heycode/relay_client.py`, `tests/relay/test_client.py`. Modify `src/heycode/cli.py`.

- [ ] Testes: backoff exponencial 1 s a 60 s com jitter; reconecta depois de queda; falha do relay nunca levanta para o agente; `heycode pair` gera a chave, resgata o código e imprime o código de verificação.
- [ ] Rodar; FAIL. Implementar; PASS.
- [ ] Commit `feat: cliente local do relay e comando pair`.

## Task P3.5: Infra como código, runbooks e threat model

**Files:** Create `infra/README.md`, `infra/Dockerfile`, `infra/fly.toml.example`, `docs/runbooks/{relay-fora-do-ar,chave-vazada,dominio-expirando,restauracao-do-banco}.md`. Modify `docs/OPERATIONS.md`, `docs/security/threat-model.md`.

- [ ] Escrever, sem segredos nem comandos que contratem nada. Teste: `Dockerfile` constrói e o relay sobe localmente com `uvicorn` e responde `/health`.
- [ ] Commit `docs: infra como codigo e runbooks do relay` (isento de trailer).

## Self-Review

Cobre critérios 1–5 e 7 da spec em código; 6 (reconstruir staging) depende de P3.5 e das ações do dono.
