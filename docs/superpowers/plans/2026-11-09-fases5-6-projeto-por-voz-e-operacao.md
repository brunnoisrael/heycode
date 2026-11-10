# Fases 5 e 6: criar projeto por voz, serviço fixo e endurecimento, plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pela Alexa o dono cria um projeto novo (pasta, git, gates de spec, `AGENTS.md`) e já dispara o agente na primeira tarefa; a ponte roda como serviço fixo, com aviso proativo opcional e endurecimento.

**Architecture:** `bridge/projects` cria e prepara o projeto e usa o `Supervisor` existente. Confirmação unificada em `/confirm` e `/cancel` (projeto pendente primeiro, depois ditado). Scripts instalam a ponte como tarefa agendada do Windows. A skill ganha o intent de criar projeto e a checagem do ID da skill.

**Tech Stack:** Python 3.14, FastAPI, git, PowerShell, Node 24 (`node:test`).

**Spec:** `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (G5, §9 fases 5 e 6, §10)

## Global Constraints

- Todo commit `feat|fix|test|refactor` leva o trailer `Spec: docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`; commit que toca `skill/interaction-model-pt-BR.json`, `bridge/store/*`, `bridge/policy/*`, `bridge/mcp/*` ou `bridge/supervisor/*` leva **um ADR novo** (reservados: 0009 criar projeto, 0010 intents de projeto, 0011 serviço fixo).
- Criar projeto: pasta **sempre dentro** de `PROJECTS_ROOT` (padrão `~/Documents/Projetos`), nome vira slug `[a-z0-9-]` de até 40 caracteres, sem sobrescrever pasta existente, sem `..` nem separadores; confirmação por voz obrigatória (como o ditado: 60 s de validade, um pendente).
- O projeto criado já nasce com os gates: git local (`main`), `AGENTS.md`, `docs/superpowers/specs/`, `docs/adr/`, `scripts/gates/` e `.githooks/` copiados deste repositório, `core.hooksPath=.githooks`, commit inicial `chore: scaffold`.
- A primeira tarefa do agente é **escrever a spec** do projeto (o gate de spec vale para os projetos novos também), com a descrição ditada.
- Segredos nunca em voz nem em log sem máscara (`policy.redact.mask_secrets`).
- O serviço fixo não inclui credenciais da conta Cloudflare/Alexa do dono: o que exige login dele é só documentado e roteirizado.
- Hooks e adaptadores falham abertos; compatibilidade dos endpoints existentes.

## Review Focus

- Nome de projeto malicioso por voz (`../x`, `C:\Windows`, `con`, vazio, só símbolos) nunca cria fora de `PROJECTS_ROOT`.
- Projeto já existente: não sobrescreve e fala que já existe.
- `/confirm` sem nada pendente fala isso e não inicia nada; depois de confirmar, uma segunda confirmação não repete.
- `ALLOWED_SKILL_ID` definido e `applicationId` diferente: recusa sem chamar a ponte.
- O script do serviço é idempotente e não deixa duas pontes disputando a porta.

## Contratos compartilhados

`bridge/projects/service.py`:
```python
def slugify(name: str) -> str   # ValueError se vazio após limpeza
def scaffold_project(root: str, slug: str, template_repo: str) -> str   # cria e prepara; devolve o caminho; FileExistsError se já existir
class ProjectCreator:
    def __init__(self, root: str, template_repo: str, start_run: Callable[[str, str, str | None], int],
                 ttl: float = 60.0, clock=time.time) -> None
    def propose(self, name: str, agent: str, description: str) -> dict   # {"speech": str, "ok": bool}
    def confirm(self) -> dict    # {"speech": str, "run_id"?: int, "path"?: str}
    def cancel(self) -> dict
```
`start_run(agent, prompt, project)` é o `_start_run` de `bridge/server.py` (o `cwd` resolve para `PROJECTS_ROOT/<slug>`).

HTTP (auth `x-secret`): `POST /projects` `{name, agent, description}` → `{speech, ok}`; `POST /confirm` → `{speech, run_id?}` (confirma o pendente: projeto antes de ditado); `POST /cancel` → `{speech}`.

Skill: `CreateProjectIntent` (slots `nome` tipo customizado `NOME_PROJETO`, `agente` tipo `AGENTE`, `descricao` `AMAZON.SearchQuery`; amostras "crie o projeto {nome} com o {agente} para {descricao}", "começa um projeto {nome} com o {agente} {descricao}"); `ConfirmIntent` e `CancelDictationIntent` passam a chamar `/confirm` e `/cancel`.

---

### Task K1: Criar projeto (backend) (+ ADR 0009)

**Files:** Create `bridge/projects/{__init__,service}.py`, `bridge/projects/routes.py`, `docs/adr/0009-criar-projeto-por-voz.md`; Modify `bridge/server.py`; Test `tests/projects/test_service.py`, `tests/server/test_projects_wiring.py`.

- [ ] **Step 1:** Testes que falham (diretório temporário como `root`; este repositório como `template_repo`): `slugify` ("Meu App Legal!" → `meu-app-legal`, `../x` → `x`, `con` e vazio → `ValueError`, 60 caracteres → 40); `scaffold_project` cria git com branch `main`, `AGENTS.md`, `docs/adr`, `docs/superpowers/specs`, `scripts/gates/commit_msg.py`, `.githooks/commit-msg`, `core.hooksPath=.githooks`, um commit inicial `chore: scaffold` e **os hooks funcionam no projeto novo** (um `feat:` sem `Spec:` é recusado); `FileExistsError` se existir; `ProjectCreator` com relógio e `start_run` falsos: `propose` fala o nome final e a descrição mascarada, `confirm` cria e chama `start_run(agent, prompt_com_pedido_de_spec, slug)` uma vez, sem pendente fala que não há nada, expira em 61 s, segundo `propose` substitui, projeto existente → `ok False`; ligação no servidor: `POST /projects` + `POST /confirm` cria a pasta em `PROJECTS_ROOT` (temp) e inicia uma run falsa; `/confirm` com ditado pendente confirma o ditado; `/cancel` limpa.
- [ ] **Step 2:** `python -m pytest tests/projects tests/server -q`; esperado FAIL.
- [ ] **Step 3:** Implementar serviço, rotas e a ligação em `server.py` (`/confirm` e `/cancel` unificados; os endpoints `/dictation/confirm` e `/dictation/cancel` continuam funcionando). O prompt da primeira tarefa manda o agente escrever a spec em `docs/superpowers/specs/` antes de qualquer código e seguir o `AGENTS.md`.
- [ ] **Step 4:** Suíte inteira verde; ADR 0009.
- [ ] **Step 5: Commit**: `feat: criar projeto por voz com scaffold e gates`.

### Task K2: Skill, intents de projeto e checagem do ID da skill (+ ADR 0010)

**Files:** Modify `skill/lambda/index.js`, `skill/interaction-model-pt-BR.json`; Create `docs/adr/0010-intents-de-projeto.md`; Test `skill/lambda/test/projects.test.js` (e ajustar `dictation.test.js` para `/confirm` e `/cancel`).

- [ ] **Step 1:** Testes que falham (`node:test`, `fetch` mockado): `CreateProjectIntent` faz `POST /projects` com `{name, agent, description}` e mantém a sessão aberta com "Confirma?"; `ConfirmIntent` chama `POST /confirm`; `CancelDictationIntent` chama `POST /cancel`; `ALLOWED_SKILL_ID` definido e `applicationId` diferente → fala de acesso negado e nenhum `fetch`; `ALLOWED_SKILL_ID` ausente → segue (o userId/deviceId continuam obrigatórios); intents antigos intactos.
- [ ] **Step 2:** `cd skill/lambda && npm test`; esperado FAIL.
- [ ] **Step 3:** Implementar. Modelo: tipo `NOME_PROJETO` (valores de exemplo: `meu app`, `painel`, `bot de estudos`) e o intent conforme o contrato. Registrar no ADR 0010 a limitação de slots personalizados (podem devolver valores fora da lista).
- [ ] **Step 4:** `npm test` verde; JSON do modelo válido; ADR 0010.
- [ ] **Step 5: Commit**: `feat: intents de criar projeto e checagem do ID da skill`.

### Task L: Serviço fixo, tunnel nomeado roteirizado e smoke (+ ADR 0011)

**Files:** Create `scripts/install-service.ps1`, `scripts/uninstall-service.ps1`, `scripts/setup-named-tunnel.ps1`, `scripts/rotate-secret.ps1`, `scripts/smoke.ps1`, `docs/adr/0011-servico-fixo-e-tunel.md`; Modify `docs/DEPLOY-ALEXA.md`.

- [ ] **Step 1:** `install-service.ps1`: cria a tarefa agendada `RoomCodeBridge` (ao logon do usuário, janela oculta, reinicia em falha) que roda `scripts/run-bridge.ps1`; idempotente (recria se existir); `-ReplaceExisting` encerra qualquer processo escutando na porta da ponte **somente se** a linha de comando contiver `server:app`; `-DryRun` mostra o que faria. `uninstall-service.ps1` remove a tarefa.
- [ ] **Step 2:** `setup-named-tunnel.ps1`: roteiro do túnel nomeado do `cloudflared` (`tunnel login`, `tunnel create`, `tunnel route dns`, `config.yml`, serviço) com `-DryRun`; as partes que exigem login interativo do dono só imprimem o comando e pausam com instrução, nunca tentam burlar.
- [ ] **Step 3:** `rotate-secret.ps1`: gera novo `BRIDGE_SECRET` no `.env` (backup antes), reinicia a tarefa e imprime o que atualizar (Lambda e MCP). `smoke.ps1`: sobe a ponte numa porta livre com banco temporário, confere `/health`, 401 sem header, `/mcp` 401 sem credencial e 200 com, `POST /mode`, e encerra o processo que iniciou.
- [ ] **Step 4:** Rodar `smoke.ps1` (real) e os demais com `-DryRun`; anexar as saídas ao relatório. Atualizar `docs/DEPLOY-ALEXA.md` (serviço, túnel nomeado, `ALLOWED_SKILL_ID`, como descobrir os IDs). ADR 0011.
- [ ] **Step 5: Commit**: `feat: servico fixo, tunel nomeado roteirizado, rotacao de segredo e smoke`.

### Task M: Aviso proativo opcional (controlador, depois de K1)

- [ ] Testes que falham: com `HA_WEBHOOK_URL` definido, `Notification` e fim de run fazem `POST` JSON `{title, message}` num servidor HTTP falso; sem a variável, nada é chamado; falha do webhook nunca derruba a ponte. Implementar `notify()` em `bridge/server.py` chamando ntfy e o webhook. Documentar Home Assistant + Alexa Media Player em `docs/DEPLOY-ALEXA.md`. Commit: `feat: aviso proativo opcional via webhook do Home Assistant`.

### Task N: Fechamento (controlador)

- [ ] Renomear o produto para **RoomCode** em README, AGENTS.md, títulos e textos de fala da skill que citam o nome antigo (o diretório e o repositório remoto ficam para o dono); reescrever o README com o fluxo real; rodar suíte Python, `npm test` e `scripts/smoke.ps1`; executar `scripts/setup-agents.ps1` de verdade com a ponte como serviço; revisão final do branch.

---

## Self-Review

- G5 (iniciar projeto) → K1, K2; §9 fase 6 (túnel estável, aviso proativo, endurecimento) → L, M; allowlist de skill → K2.
- Contratos: `start_run(agent, prompt, project)` é o `_start_run` da fase 4; `/confirm` unifica projeto e ditado sem quebrar `/dictation/*`.
- Fora do escopo de execução: login Cloudflare e publicação na conta Alexa (exigem credenciais do dono).
