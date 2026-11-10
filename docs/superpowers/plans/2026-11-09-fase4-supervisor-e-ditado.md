# Fase 4: Supervisor e ditado com confirmação, plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pela Alexa, o dono manda uma tarefa a um agente (Claude, Codex ou Aider): ela releia o que entendeu, o dono confirma, e a ponte inicia o agente como processo filho, guarda a saída e avisa no fim do ciclo.

**Architecture:** `bridge/supervisor` monta o comando de cada agente a partir da política vigente, roda o processo filho no Windows, guarda a saída e o resultado no store (tabela `runs`). `bridge/dictation` guarda o ditado pendente, mascara segredos e só envia depois da confirmação. Cada parte expõe um `make_router(...)` e o servidor liga tudo no fim (controlador).

**Tech Stack:** Python 3.14, FastAPI, subprocess, sqlite3, pytest, Node 24 (`node:test`).

**Spec:** `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (G4, G6, §10) e `docs/superpowers/specs/2026-11-09-spike-codex-aider.md`.

## Global Constraints

- Todo commit `feat|fix|test|refactor` leva o trailer `Spec: docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`; commit que toca `bridge/store/*`, `bridge/supervisor/*`, `bridge/policy/*` ou `skill/interaction-model-pt-BR.json` leva **um ADR novo** (reservados: 0007 supervisor, 0008 ditado).
- Ditado: confirmação em toda instrução, limite de 300 caracteres, segredos mascarados por padrão (§10).
- Auto sem piso (§7): em modo auto os agentes rodam sem restrição de aprovação/sandbox; em manual e decisões rodam com sandbox restrito (ver comandos abaixo).
- Reinício: execuções em andamento viram `interrompida`, sem reanexar (§10).
- Sem resposta de confirmação em 60 s, o ditado expira e nada é enviado.
- Os comandos dos agentes vêm de um mapa de configuração injetável (testes usam `python -c` no lugar dos agentes reais; nunca chamar Claude/Codex/Aider reais em testes).
- Os flags reais de cada CLI devem ser conferidos com `--help` na máquina (spike: `codex exec -C <dir> --json -o <arquivo> [-s modo] "prompt"`; `aider --message ... --yes-always --no-pretty --no-auto-commits`; `claude -p "prompt" --output-format json`); a tarefa registra no ADR 0007 o que confirmou.
- Hooks e adaptadores falham abertos; a ponte nunca derruba um agente aberto.

## Review Focus

- Instrução com segredo (`sk-...`, `ghp_...`, `AKIA...`, `password=...`) nunca aparece em voz nem em log sem máscara.
- Confirmação sem ditado pendente, ou depois de expirar, não inicia nada e fala isso.
- Dois ditados seguidos: o segundo substitui o primeiro (só um pendente).
- Processo filho que não termina: `cancel` o encerra (árvore inteira no Windows) e marca `cancelada`.
- Agente que sai com código diferente de zero vira `falhou` com as últimas linhas da saída, sem derrubar a ponte.

## Contratos compartilhados

Store (acrescentar a `bridge/store/db.py`, tabela `runs`):
```python
def create_run(self, agent: str, project: str, prompt: str, cwd: str) -> int
def update_run(self, run_id: int, status: str | None = None, summary: str | None = None,
               exit_code: int | None = None, pid: int | None = None) -> None
# status: rodando|concluida|falhou|cancelada|interrompida
def get_run(self, run_id: int) -> dict | None   # id, agent, project, prompt, cwd, status, summary, exit_code, pid, t_start, t_end
def latest_run(self, agent: str | None = None) -> dict | None
def interrupt_running(self) -> int   # chamado no startup
```

`bridge/supervisor/runner.py`: `build_command(agent: str, prompt: str, cwd: str, mode: str, out_file: str, commands: dict | None = None) -> list[str]` (ValueError para agente desconhecido). `mode="auto"` → sem restrições (`codex exec -s danger-full-access`, `claude -p --dangerously-skip-permissions`); outros modos → `codex exec -s workspace-write`, `claude -p` com permissão padrão. Aider: igual em todos os modos (`--yes-always`), só roda depois da confirmação do ditado.

`bridge/supervisor/manager.py`:
```python
class Supervisor:
    def __init__(self, store, commands: dict | None = None, on_finish: Callable[[dict], None] | None = None) -> None
    def start(self, agent: str, prompt: str, cwd: str, mode: str) -> int   # run_id; não bloqueia
    def cancel(self, run_id: int) -> bool
    def status(self, run_id: int) -> dict | None
```
Ao terminar: grava `summary` (última mensagem do agente, no máximo 400 caracteres, segredos mascarados), `exit_code`, status e chama `on_finish(run)`.

`bridge/supervisor/routes.py`: `make_router(supervisor, store, auth) -> APIRouter` com `POST /runs` `{agent, prompt, cwd?, project?}` → `{run_id}`; `GET /runs/{id}`; `POST /runs/{id}/cancel`; `GET /runs/latest?agent=`.

`bridge/policy/redact.py`: `mask_secrets(text: str) -> str` (substitui por `[segredo]`).

`bridge/dictation/service.py`:
```python
class Dictation:
    def __init__(self, start_run: Callable[[str, str, str | None], int], ttl: float = 60.0, clock=time.time) -> None
    def propose(self, agent: str, text: str, project: str | None = None) -> dict   # {"speech": ..., "ok": bool}; ok False se vazio ou > 300 chars
    def confirm(self) -> dict    # {"speech": ..., "run_id"?: int}
    def cancel(self) -> dict
```
`bridge/dictation/routes.py`: `make_router(dictation, auth)` com `POST /dictation` `{agent, text, project?}`, `POST /dictation/confirm`, `POST /dictation/cancel`; falas em pt-BR, sempre com o texto mascarado.

Skill: intents `AskAgentIntent` (slots `agente` tipo `AGENTE` [claude, codex, aider] e `instrucao` `AMAZON.SearchQuery`; amostras "peça ao {agente} {instrucao}", "manda o {agente} {instrucao}", "diz pro {agente} {instrucao}"), `ConfirmIntent` ("confirma", "pode mandar", "manda ver") e `CancelDictationIntent` ("esquece", "cancela isso"); chamam `/dictation*`.

---

### Task H: Supervisor (+ ADR 0007)

**Files:** Modify `bridge/store/db.py`; Create `bridge/supervisor/{__init__,runner,manager,routes}.py`, `bridge/policy/redact.py`, `docs/adr/0007-supervisor-de-agentes.md`; Test `tests/store/test_runs.py`, `tests/supervisor/test_runner.py`, `tests/supervisor/test_manager.py`, `tests/policy/test_redact.py`.

- [ ] **Step 1:** Testes que falham: store de runs (ciclo de status, `interrupt_running`, `latest_run`); `build_command` para os 3 agentes × modos (comparação exata da lista), agente desconhecido → `ValueError`; `mask_secrets` com cada família; manager com agentes falsos (`python -c`): sucesso grava `summary` e `concluida` e chama `on_finish`; saída com segredo vem mascarada; código de saída 3 → `falhou` com cauda da saída; processo que dorme → `cancel` o mata (árvore, via `taskkill /T /F` ou job object) e marca `cancelada`; rotas com `TestClient` (401 sem header; `POST /runs` → `GET /runs/{id}`).
- [ ] **Step 2:** `python -m pytest tests/store tests/supervisor tests/policy -v`; esperado FAIL.
- [ ] **Step 3:** Implementar. Confirmar os flags reais com `codex exec --help`, `claude --help`, `aider --help` e usar o que existir.
- [ ] **Step 4:** Suíte inteira verde; ADR 0007 (processo filho vs. app-server; modos e sandbox; o que foi confirmado nos `--help`).
- [ ] **Step 5: Commit**: `feat: supervisor que inicia e controla agentes headless`.

### Task I: Ditado com confirmação e intents (+ ADR 0008)

**Files:** Create `bridge/dictation/{__init__,service,routes}.py`, `docs/adr/0008-ditado-com-confirmacao.md`; Modify `skill/lambda/index.js`, `skill/interaction-model-pt-BR.json`; Test `tests/dictation/test_service.py`, `skill/lambda/test/dictation.test.js`.

- [ ] **Step 1:** Testes que falham (relógio injetado, `start_run` falso): `propose` com segredo fala o texto mascarado; texto vazio e de 301 caracteres → `ok False`; `confirm` sem pendente → fala que não há nada; `confirm` após 61 s → expirou e `start_run` não é chamado; segundo `propose` substitui o primeiro; `confirm` válido chama `start_run(agent, text_original, project)` uma única vez e uma segunda `confirm` não repete; Node: `AskAgentIntent` faz `POST /dictation` com `agent` e `text`; `ConfirmIntent` faz `POST /dictation/confirm`; sessão fica aberta (reprompt "Confirma?").
- [ ] **Step 2:** Rodar `python -m pytest tests/dictation -v` e `cd skill/lambda && npm test`; esperado FAIL.
- [ ] **Step 3:** Implementar serviço, rotas e intents. O `start_run` real usa `Supervisor.start`; o texto enviado ao agente é o **original** (com segredos, se o dono os falou), só a fala e os logs saem mascarados.
- [ ] **Step 4:** Tudo verde. ADR 0008.
- [ ] **Step 5: Commit**: `feat: ditado de instrucoes por voz com confirmacao`.

### Task J: Ligação no servidor e fim de ciclo (controlador, depois de H e I)

**Files:** Modify `bridge/server.py`; Test `tests/server/test_phase4_wiring.py`.

- [ ] **Step 1:** Testes que falham: `POST /dictation` + `POST /dictation/confirm` com um comando de agente falso inicia uma run e `GET /runs/latest` mostra `concluida`; `Store.interrupt_running()` roda no startup; com `report_on_end` ligado, depois de uma run terminar `/pending` fala "O agente <nome> terminou. Quer ouvir a saída?" e `/result` lê o resumo da run.
- [ ] **Step 2:** Implementar a ligação (routers, `Supervisor` com `on_finish` que dispara push e marca o relatório pendente).
- [ ] **Step 3:** Suíte inteira verde. **Step 4: Commit**: `feat: liga supervisor e ditado ao servidor, fim de ciclo`.

---

## Self-Review

- G4 (supervisor) → H; G6 (ditado com releitura/confirmação, 300 caracteres, máscara) → I; fim de ciclo (G1) → J.
- Contratos: `Supervisor.start` é o `start_run` do ditado; `mask_secrets` usado por supervisor e ditado.
- Fora desta fase: criar projeto (fase 5), aviso proativo e serviço fixo (fase 6).
