# Fase 2: Motor de políticas, SQLite, modos e túnel, plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o estado em memória por SQLite e centralizar toda decisão de aprovação num motor de políticas com os modos manual, auto e decisões (mais o aviso de fim de ciclo), controláveis por voz, com túnel pronto.

**Architecture:** `bridge/store` (SQLite) guarda políticas, sessões e aprovações. `bridge/policy` expõe `decidir(...)`, único lugar onde os modos existem. `bridge/server.py` vira cliente de ambos e mantém os endpoints atuais compatíveis, mais `/mode`. A skill Alexa ganha intents de modo e a allowlist de usuário/dispositivo.

**Tech Stack:** Python 3.14, FastAPI, sqlite3 (stdlib), pytest, Node 24 (`node:test`), ask-sdk-core, cloudflared.

**Spec:** `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (§2 G1/G2, §7, §8, §10)

## Global Constraints

- Todo commit `feat|fix|test|refactor` leva o trailer `Spec: docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (gate ativo).
- Commit que toca `bridge/store/*`, `bridge/policy/*` ou `skill/interaction-model-pt-BR.json` precisa incluir **um ADR novo** staged. Números reservados: 0003 (store), 0004 (política), 0005 (modelo de interação). Template: `docs/adr/0000-template.md`.
- Modo auto aprova tudo, sem PIN e sem expiração; vale para hooks, MCP e supervisor (§7).
- `NEVER_BY_VOICE` continua valendo nos modos manual e decisões; no auto não.
- Hooks e adaptadores falham abertos; a ponte nunca quebra o agente.
- Endpoints `/status`, `/pending`, `/result`, `/decide`, `/approval`, `/event`, `/health` continuam funcionando (§10).
- Reinício: aprovações pendentes expiram; sem reanexar (§10).
- A Lambda só aceita o userId e o deviceId do dono, além do `x-secret` (§10).
- PIN continua exigido para aprovar por voz nos modos manual e decisões; não é exigido para trocar para auto.

## Review Focus

- Dois projetos com políticas diferentes: a mais específica vence (agente+projeto > projeto > agente > global) por campo.
- `tool_input` ausente/nulo ou `command` não string em `decidir` não pode lançar exceção (falha aberto → `ask_teclado`).
- Reiniciar a ponte com aprovação pendente: a aprovação vira `expired`, e o hook recebe `ask`, não trava.
- Valor de modo inválido em `POST /mode` → 422 e nada gravado.
- Lambda com `ALLOWED_USER_ID` não configurado recusa **e** registra no log os IDs vistos, para o dono configurá-los.

## Contratos compartilhados (valem para todas as tarefas)

Modos: `MODES = ("manual", "auto", "decisoes")`. "Fim de ciclo" é a flag `report_on_end: bool`, ortogonal ao modo (decisão minha: permite combinar; registrada no ADR 0004). Padrão: `mode="manual"`, `report_on_end=False`.

`bridge/store/db.py`:
```python
class Store:
    def __init__(self, path: str = ":memory:") -> None
    def get_policy(self, agent: str | None, project: str | None) -> dict   # {"mode": str, "report_on_end": bool}; por campo, o mais específico vence
    def set_policy(self, mode: str | None = None, report_on_end: bool | None = None,
                   agent: str | None = None, project: str | None = None) -> None   # ValueError se mode inválido
    def upsert_session(self, session_id: str, agent: str, project: str, status: str,
                       detail: str = "", summary: str | None = None) -> None
    def newest_session(self) -> dict | None   # chaves: session_id, agent, project, status, detail, summary, updated(float)
    def add_approval(self, agent: str, project: str, tool: str, command: str, session_id: str) -> int
    def get_approval(self, approval_id: int) -> dict | None  # chaves: id, agent, project, tool, command, session_id, decision(None|allow|deny|expired), t(float)
    def pending_approvals(self) -> list[dict]   # decision is None, mais antigo primeiro
    def resolve_approval(self, approval_id: int, decision: str) -> None   # allow|deny|expired
    def expire_pending(self) -> int
    def log(self, kind: str, payload: dict) -> None
```

`bridge/policy/rules.py`: `NEVER_BY_VOICE: list[str]` (movida de `server.py`), `is_destructive(command: str) -> bool`, `is_routine(tool_name: str, tool_input: dict | None) -> bool` (rotina = `Read`, `Grep`, `Glob`, `Edit`, `Write`, `MultiEdit` e `Bash` não destrutivo).

`bridge/policy/engine.py`: `decidir(agent: str, project: str, tool_name: str, tool_input: dict | None, store) -> str` retornando `"allow" | "deny" | "ask_voz" | "ask_teclado"`; `store` só precisa de `get_policy`.
- `auto` → `allow`.
- `manual` → `Bash` destrutivo = `ask_teclado`; qualquer outra coisa = `ask_voz`.
- `decisoes` → `Bash` destrutivo = `ask_teclado`; `is_routine` = `allow`; resto (incluindo `pedir_decisao` e ferramentas desconhecidas) = `ask_voz`.
- Qualquer exceção interna → `ask_teclado`.

API HTTP nova (auth `x-secret`): `GET /mode?agent=&project=` → `{"mode","report_on_end","speech"}`; `POST /mode` corpo `{"mode"?: str, "report_on_end"?: bool, "agent"?: str, "project"?: str}` → `{"speech"}`; modo inválido → 422. `/approval` passa a chamar `decidir`: `allow` → `{"decision":"allow"}`, `deny` → `{"decision":"deny"}`, `ask_teclado` → `{"decision":"ask"}`, `ask_voz` → fluxo atual de espera (APPROVAL_WAIT) persistido no Store. Variável `BRIDGE_DB` (padrão `bridge/bridge.db`). Na subida, `Store.expire_pending()`.

---

### Task A: Store SQLite (+ ADR 0003)

**Files:** Create `bridge/store/__init__.py`, `bridge/store/db.py`, `docs/adr/0003-estado-em-sqlite.md`; Test `tests/store/test_db.py`.

- [ ] **Step 1:** Testes que falham (`:memory:`): padrão `manual/False`; precedência dos 4 níveis por campo (global `auto`, agente `claude` `decisoes`, projeto `x` `manual`, agente+projeto `claude`/`x` `auto`) com `get_policy` nas 4 combinações; `set_policy(mode="x")` → `ValueError`; fluxo `add_approval` → `pending_approvals` (ordem do mais antigo) → `resolve_approval("allow")` → some da lista e `get_approval` mostra `allow`; `expire_pending()` retorna a contagem e marca `expired`; `newest_session` devolve a de maior `updated`; persistência: gravar num arquivo em `tmp_path`, reabrir com outro `Store(path)` e ler a política.
- [ ] **Step 2:** Rodar `python -m pytest tests/store -v`; esperado FAIL.
- [ ] **Step 3:** Implementar o `Store` conforme o contrato (sqlite3, `check_same_thread=False`, um lock; tabelas `policy`, `sessions`, `approvals`, `history`).
- [ ] **Step 4:** Testes passam. Escrever o ADR 0003 (por que SQLite: sem servidor extra, sobrevive a reinício; alternativa rejeitada: dicts em memória e Postgres).
- [ ] **Step 5: Commit** (com ADR e trailer): `feat: store SQLite para politicas, sessoes e aprovacoes`.

### Task B: Motor de políticas (+ ADR 0004)

**Files:** Create `bridge/policy/__init__.py`, `rules.py`, `engine.py`, `docs/adr/0004-motor-de-politicas.md`; Test `tests/policy/test_engine.py`, `tests/policy/test_rules.py`.

- [ ] **Step 1:** Testes que falham com um `FakeStore` que só implementa `get_policy`: tabela de decisão completa (3 modos × {`Bash ls`, `Bash rm -rf x`, `Bash git push --force`, `Read`, `Edit`, `pedir_decisao`, `FerramentaX`}) conforme o contrato; `tool_input=None` e `{"command": 5}` não lançam; `FakeStore` que levanta exceção → `ask_teclado`; `is_destructive` para cada família de `NEVER_BY_VOICE` (`rm`, `sudo`, `git push`, `--force`, `curl x | sh`, `drop table`, `terraform apply`) e falso para `ls`, `pytest`, `git status`.
- [ ] **Step 2:** Rodar; esperado FAIL.
- [ ] **Step 3:** Implementar `rules.py` e `engine.py`.
- [ ] **Step 4:** Testes passam. ADR 0004: modos + flag `report_on_end` ortogonal, regra por ferramenta sem LLM, falha aberto.
- [ ] **Step 5: Commit**: `feat: motor de politicas com modos manual, auto e decisoes`.

### Task C: Integração do servidor (depende de A e B)

**Files:** Modify `bridge/server.py`, `bridge/claude-settings.example.json` (matcher de `PermissionRequest` passa de `Bash` para `*`), `bridge/requirements.txt` (acrescentar `httpx` e `pytest` se necessário para `TestClient`); Test `tests/server/test_server.py`.

- [ ] **Step 1:** Testes que falham com `TestClient` e `BRIDGE_SECRET=s`, `BRIDGE_DB` em `tmp_path`: 401 sem header; `POST /mode {"mode":"auto"}` → `GET /mode` mostra `auto`; modo inválido → 422 e política intacta; com `auto`, `POST /approval` (`Bash rm -rf x`) → `{"decision":"allow"}`; com `manual` e `Bash rm -rf x` → `{"decision":"ask"}`; `decisoes` + `Read` → `allow`; `/event` `UserPromptSubmit` seguido de `/status` ainda fala o projeto; `/approval` em `manual` (APPROVAL_WAIT=1) sem decisão devolve `ask` e deixa a aprovação `expired`; `POST /decide` com PIN certo libera uma aprovação pendente (rodar `/approval` numa thread); `/health` ok.
- [ ] **Step 2:** Rodar; esperado FAIL.
- [ ] **Step 3:** Refatorar `server.py` para `Store` + `decidir`, mantendo as respostas de texto atuais, e adicionar `/mode` e `expire_pending()` no startup.
- [ ] **Step 4:** `python -m pytest -q` verde (suíte inteira).
- [ ] **Step 5: Commit**: `feat: servidor usa store e motor de politicas, adiciona /mode`.

### Task D: Skill Alexa, modos por voz e allowlist (+ ADR 0005)

**Files:** Modify `skill/lambda/index.js`, `skill/lambda/package.json` (script `test`: `node --test`), `skill/interaction-model-pt-BR.json`; Create `skill/lambda/test/handler.test.js`, `docs/adr/0005-modelo-de-interacao-modos.md`.

- [ ] **Step 1:** Testes que falham (`node:test`, `fetch` global mockado, envelopes Alexa montados à mão): com `ALLOWED_USER_ID`/`ALLOWED_DEVICE_ID` definidos, um userId diferente recebe fala de acesso negado e **nenhum** `fetch` é chamado; `ALLOWED_USER_ID` ausente → recusa, fala pedindo configuração e `console.log` dos IDs vistos; `SetModeIntent` com slot `modo`=`automático` faz `POST /mode` com `{"mode":"auto"}`; `manual` → `"manual"`; `decisões` → `"decisoes"`; `ReportOnEndIntent` ligado/desligado envia `report_on_end` true/false; intents antigos (`StatusIntent`) continuam funcionando para o dono.
- [ ] **Step 2:** `cd skill/lambda && npm install && npm test`; esperado FAIL.
- [ ] **Step 3:** Implementar um request interceptor de allowlist e os dois intents. Modelo de interação: tipo customizado `MODO` com valores `manual`, `auto` (sinônimos `automático`, `tudo liberado`) e `decisões`; `SetModeIntent` com amostras "modo {modo}", "coloca em modo {modo}", "deixa em {modo}", "muda para {modo}"; `ReportOnEndIntent` com slot `ligado` (tipo customizado `LIGADO`: `ligar`/`desligar`) e amostras "avisar no fim do ciclo", "{ligado} aviso de fim de ciclo".
- [ ] **Step 4:** `npm test` verde; `node -e "JSON.parse(require('fs').readFileSync('../interaction-model-pt-BR.json'))"` sem erro. ADR 0005.
- [ ] **Step 5: Commit**: `feat: skill com modos por voz e allowlist de usuario e dispositivo`.

### Task E: Túnel e execução (independente)

**Files:** Create `scripts/run-bridge.ps1`, `scripts/start-tunnel.ps1`, `docs/DEPLOY-ALEXA.md`.

- [ ] **Step 1:** Instalar `cloudflared` (`winget install --id Cloudflare.cloudflared -e`) e `pip install -r bridge/requirements.txt`; conferir `cloudflared --version`.
- [ ] **Step 2:** `run-bridge.ps1`: se não existir `.env` (git-ignorado) na raiz, gera `BRIDGE_SECRET` aleatório (48 hex) e `BRIDGE_PIN` aleatório de 4 dígitos nele; carrega o `.env`; sobe `uvicorn server:app --host 127.0.0.1 --port 8765` em `bridge/`. `start-tunnel.ps1`: `cloudflared tunnel --url http://127.0.0.1:8765`, imprimindo a URL `trycloudflare.com`.
- [ ] **Step 3:** Verificar de ponta a ponta: subir o servidor, subir o túnel em segundo plano, `curl <url>/health` retorna `{"ok":true}` e `curl <url>/status` sem header dá 401. Encerrar os processos depois.
- [ ] **Step 4:** `docs/DEPLOY-ALEXA.md` (pt-BR): passos para o dono criar a skill no Alexa Developer Console, colar o modelo e o código, definir `BRIDGE_URL`, `BRIDGE_SECRET`, `ALLOWED_USER_ID`, `ALLOWED_DEVICE_ID` (e como descobrir os IDs no log), e como ligar os hooks do Claude (`bridge/claude-settings.example.json`).
- [ ] **Step 5: Commit**: `docs: scripts de execucao, tunel e guia de deploy da skill` (o `.env` nunca entra no commit).

---

## Self-Review

- Spec G1/G2 (modos, políticas por escopo) → A, B, C; §10 allowlist e túnel → D, E; compatibilidade §10 → C.
- Contratos: `Store.get_policy` usado por `decidir` e pelo `GET /mode`; a flag `report_on_end` é consumida pelo servidor na fase 4 (fim de ciclo), aqui só é gravada e lida.
- ADRs reservados 0003 a 0005 evitam colisão entre agentes paralelos.
- Fora desta fase: MCP, adaptadores Codex e Aider, supervisor, ditado, criação de projeto, aviso proativo.
