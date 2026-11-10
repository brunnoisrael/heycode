# Fase 3: Servidor MCP e adaptadores Claude/Codex, plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Qualquer agente com cliente MCP (Claude Code, Codex) conversa com a ponte por ferramentas MCP, e o Claude já aberto recebe a próxima instrução pelo hook de Stop.

**Architecture:** O store ganha uma fila de instruções. O servidor MCP (SDK Python oficial, streamable HTTP) é montado em `/mcp` na mesma app FastAPI e usa `decidir`, o store e as mesmas regras. `hook.py` ganha `--agent` e o tratamento do evento Stop. Scripts registram o MCP no Claude e no Codex.

**Tech Stack:** Python 3.14, FastAPI, `mcp` (SDK oficial), sqlite3, pytest, PowerShell.

**Spec:** `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (§8, §9 fase 3, §10) e `docs/superpowers/specs/2026-11-09-spike-codex-aider.md`.

## Global Constraints

- Todo commit `feat|fix|test|refactor` leva o trailer `Spec: docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`; commit que toca `bridge/store/*`, `bridge/mcp/*`, `bridge/policy/*` leva **um ADR novo** (reservado: 0006).
- Hooks e adaptadores falham abertos; a ponte nunca quebra o agente.
- Instrução para agente já aberto: só o Claude (hook de Stop + MCP `buscar_instrucao`); Codex só recebe instrução via MCP `buscar_instrucao` ou quando iniciado pelo supervisor (fase 4); Aider fica só no supervisor, pois não tem MCP nem hook de aprovação (spike).
- Autenticação do `/mcp`: header `Authorization: Bearer <BRIDGE_SECRET>` ou `x-secret`, comparação em tempo constante.
- Nome do servidor MCP registrado nos agentes: `roomcode`.
- Os scripts de setup **não alteram** `approval_policy` nem o sandbox do Codex do dono (hoje `never` e `danger-full-access`); só acrescentam o servidor MCP, fazem backup antes e avisam.
- Compatibilidade: endpoints atuais intactos; suíte inteira verde antes de cada commit.

## Review Focus

- `pedir_decisao` sem resposta no prazo (APPROVAL_WAIT): retorna `{"answer": "sem_resposta"}`, nunca trava o agente.
- No modo auto, `pedir_decisao` responde sozinha `{"answer": "sim", "auto": true}`.
- `buscar_instrucao` com fila vazia retorna `{"instruction": null}`; duas chamadas seguidas entregam cada instrução uma única vez, na ordem.
- Instrução endereçada a um projeto não vaza para outro projeto; sem projeto, vale para qualquer um do agente.
- `hook.py` com a ponte fora do ar no evento Stop: sai com código 0 e sem saída (o Claude termina normal).

## Contratos compartilhados

Store (acrescentar a `bridge/store/db.py`):
```python
def add_instruction(self, text: str, agent: str = "claude", project: str | None = None) -> int
def pop_instruction(self, agent: str, project: str | None) -> dict | None
# pop: a mais antiga com agent igual e (project da instrução None ou igual ao pedido); marca como entregue; None se não houver.
# chaves: id, text, agent, project
```

API HTTP nova em `bridge/server.py` (auth `x-secret`):
- `POST /instruction` corpo `{"text": str, "agent"?: str = "claude", "project"?: str}` → `{"id": int}`; texto vazio ou maior que 300 caracteres → 422.
- `POST /instruction/next` corpo `{"agent": str, "project"?: str}` → `{"instruction": str | null}`.

Ferramentas MCP (`bridge/mcp/server.py`, FastMCP, nome `roomcode`):
- `registrar_status(status: str, detail: str = "", agent: str = "agent", project: str = "projeto") -> dict`
- `pedir_decisao(question: str, agent: str = "agent", project: str = "projeto") -> dict` → `{"answer": "sim" | "nao" | "sem_resposta", "auto"?: true}`; cria uma aprovação com `tool="pedir_decisao"` e `command=question`, resolvida pelo `/decide` existente.
- `reportar_fim(summary: str, agent: str = "agent", project: str = "projeto") -> dict`
- `buscar_instrucao(agent: str = "agent", project: str = "projeto") -> dict` → `{"instruction": str | null}`

`bridge/hook.py`: novo argumento `--agent <nome>` (padrão `claude`) que entra no corpo enviado (`agent`). No evento `Stop`, depois de enviar o evento, chama `POST /instruction/next`; se vier instrução, imprime `{"decision": "block", "reason": "<instrução>"}` para o Claude Code continuar com ela.

---

### Task F: Fila de instruções, endpoints e servidor MCP (+ ADR 0006)

**Files:** Modify `bridge/store/db.py`, `bridge/server.py`, `bridge/requirements.txt` (`mcp`); Create `bridge/mcp/__init__.py`, `bridge/mcp/server.py`, `docs/adr/0006-servidor-mcp-central.md`; Test `tests/store/test_instructions.py`, `tests/server/test_instruction_api.py`, `tests/mcp/test_tools.py`.

- [ ] **Step 1:** Testes que falham: store (`add/pop` na ordem; isolamento por projeto; sem projeto vale para qualquer; entregue uma vez só; fila vazia → `None`); API (`POST /instruction` 422 para vazio e para 301 caracteres, 401 sem header, `next` entrega e esvazia); MCP, chamando as funções das ferramentas diretamente com um Store temporário e, em pelo menos um teste, via cliente MCP real do SDK contra `/mcp` com `TestClient`/servidor de teste: `registrar_status` atualiza a sessão; `reportar_fim` grava o resumo; `buscar_instrucao` esvazia a fila; `pedir_decisao` no modo auto → `sim`+`auto`; no manual, com `APPROVAL_WAIT=1` e sem resposta → `sem_resposta`; no manual, resolvida por `POST /decide` (PIN certo) numa thread → `sim`; `/mcp` sem credencial → 401.
- [ ] **Step 2:** Rodar `python -m pytest tests/store tests/server tests/mcp -v`; esperado FAIL.
- [ ] **Step 3:** Implementar store, endpoints e o módulo MCP, montado em `/mcp` com a integração de lifespan que o SDK exigir (o gerenciador de sessão precisa subir junto com a app), com middleware de autenticação.
- [ ] **Step 4:** `python -m pytest -q` verde (suíte inteira). Escrever o ADR 0006 (hub MCP único; alternativas rejeitadas: um MCP por agente e só hooks; Aider fora por falta de MCP, citando o spike).
- [ ] **Step 5: Commit** (ADR e trailer): `feat: fila de instrucoes e servidor MCP central`.

### Task G: Hook com --agent e Stop, e setup dos agentes (independente da F, só do contrato)

**Files:** Modify `bridge/hook.py`; Create `scripts/setup-agents.ps1`; Test `tests/hook/test_hook.py`.

- [ ] **Step 1:** Testes que falham (executar `bridge/hook.py` como subprocesso contra um servidor HTTP falso em thread, porta livre via `BRIDGE_URL`): `--agent codex` envia `agent: "codex"` no corpo; evento `Stop` com instrução pendente imprime exatamente `{"decision":"block","reason":"..."}`; `Stop` sem instrução não imprime nada; ponte fora do ar → código de saída 0 e saída vazia; `approve` continua imprimindo o JSON de `PermissionRequest` para `allow`, `deny` e nada para `ask`.
- [ ] **Step 2:** Rodar `python -m pytest tests/hook -v`; esperado FAIL.
- [ ] **Step 3:** Implementar `--agent` e o tratamento do `Stop` em `hook.py` mantendo o fail-open.
- [ ] **Step 4:** `scripts/setup-agents.ps1` idempotente: (a) Claude: `claude mcp add --transport http --scope user roomcode <BRIDGE_URL>/mcp --header "Authorization: Bearer <segredo>"` se ainda não listado; (b) Codex: copiar `~/.codex/config.toml` para `config.toml.bak-<data>`, acrescentar `[mcp_servers.roomcode]` com `url` e `bearer_token_env_var = "BRIDGE_SECRET"` se ausente; (c) imprimir aviso sobre `approval_policy="never"`/`danger-full-access` no Codex sem alterá-los. Parâmetros `-BridgeUrl` (padrão `http://127.0.0.1:8765`) e `-DryRun` que só mostra o que faria. Rodar com `-DryRun` e anexar a saída ao relatório.
- [ ] **Step 5: Commit**: `feat: hook com --agent e instrucao no Stop, script de setup dos agentes`.

---

## Self-Review

- Spec §8 (servidor MCP, adaptadores) → F, G; §10 (instrução só no Claude, Aider via supervisor) → Global Constraints e G; resultado do spike usado no aviso do Codex.
- Contratos: `Store.add_instruction/pop_instruction` consumidos por `/instruction*` e `buscar_instrucao`; `hook.py` depende só dos endpoints, testável com servidor falso (daí F e G paralelas).
- Fora desta fase: supervisor (`codex exec`/`aider`), ditado, criar projeto, aviso proativo, Aider por MCP.
