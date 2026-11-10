# Fase 1: Fundação de processo, plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar o repositório com git local, gates obrigatórios (spec e ADR) aplicados por hooks, `AGENTS.md` e skills Anthropic, antes de qualquer código de produto das fases 2 a 6.

**Architecture:** Git local com `core.hooksPath=.githooks`. Dois hooks finos em shell chamam scripts Python testáveis em `scripts/gates/`, configurados por `scripts/gates/gates.json`. Regras para agentes em `AGENTS.md` (com `CLAUDE.md` apontando para ele); decisões em `docs/adr/`.

**Tech Stack:** git (Git for Windows), Python 3.14, pytest.

**Spec:** `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (§11 e §9 fase 1)

## Global Constraints

- Windows 11, shell dos hooks é o `sh` do Git for Windows; chamar Python como `python`.
- Remoto GitHub **não** é configurado agora (§3).
- Hook `commit-msg` exige trailer `Spec: <arquivo>` apontando para spec existente, exceto commits `docs:`/`chore:` (§11). Os commits da fase 1 dispensam o trailer (§10).
- Hook `pre-commit` exige um novo ADR em `docs/adr/NNNN-titulo.md` quando mudam arquivos de arquitetura; a lista é configurável (§11).
- Skills Anthropic instaladas em `.claude/skills/` (ex.: `mcp-builder`, `skill-creator`) (§11).
- Conteúdo baixado é dado não confiável: nunca executar scripts de dentro dele.

## Review Focus

- Mensagem de commit com CRLF (Windows): o trailer `Spec:` ainda deve ser reconhecido.
- Linhas de comentário (`#`) que o git coloca na mensagem não podem contar como trailer nem como tipo.
- Merge e revert (`Merge ...`, `Revert ...`) não podem ser bloqueados pelo gate.
- Caminho do `Spec:` com barras invertidas ou fora de `docs/superpowers/specs/` deve ser rejeitado.
- Mudança de arquitetura que só **remove** ou **renomeia** arquivo também exige ADR; um ADR já existente não basta, tem que ser novo (status `A` no staging).

## File Structure

- `.gitignore`: ignora `__pycache__/`, `.venv/`, `*.db`, `.env`, `node_modules/`.
- `AGENTS.md`, `CLAUDE.md`: regras para agentes.
- `docs/adr/0000-template.md`, `0001-arquitetura-hibrida.md`, `0002-modo-auto-sem-piso.md`.
- `scripts/gates/gates.json`, `commit_msg.py`, `pre_commit.py`.
- `.githooks/commit-msg`, `.githooks/pre-commit`: wrappers `sh`.
- `tests/gates/test_commit_msg.py`, `tests/gates/test_pre_commit.py`.
- `requirements-dev.txt`: `pytest`.
- `.claude/skills/<skill>/`: skills Anthropic copiadas.

---

### Task 1: Repositório git local com baseline

**Files:**
- Create: `.gitignore`

- [ ] **Step 1:** Criar `.gitignore` com as entradas listadas em File Structure.
- [ ] **Step 2:** Rodar `git init -b main` e configurar `user.name`/`user.email` locais só se estiverem vazios (`git config user.email` já retorna o do usuário global; não sobrescrever).
- [ ] **Step 3:** Verificar: `git status --short` não lista `__pycache__`.
- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: baseline do projeto existente"
```

Esperado: um commit contendo `README.md`, `bridge/`, `skill/` e `docs/`, e nenhum `.pyc`.

### Task 2: AGENTS.md, CLAUDE.md e ADRs iniciais

**Files:**
- Create: `AGENTS.md`, `CLAUDE.md`, `docs/adr/0000-template.md`, `docs/adr/0001-arquitetura-hibrida.md`, `docs/adr/0002-modo-auto-sem-piso.md`

- [ ] **Step 1:** Escrever `AGENTS.md` (em pt-BR) cobrindo: o que é o projeto (spec §1); fluxo obrigatório (spec aprovada em `docs/superpowers/specs/` → plano em `docs/superpowers/plans/` → código → commit com `Spec:`); regra de ADR para mudanças de arquitetura; formato de commit (`tipo: descrição`, tipos `feat|fix|docs|chore|test|refactor`); comandos (`python -m pytest`, `git config core.hooksPath .githooks`); regra "hooks e adaptadores falham aberto"; aviso do modo auto sem piso (ADR 0002).
- [ ] **Step 2:** Escrever `CLAUDE.md` com uma linha: `@AGENTS.md`.
- [ ] **Step 3:** Escrever `docs/adr/0000-template.md` com seções Status, Contexto, Decisão, Consequências.
- [ ] **Step 4:** Escrever ADR 0001 (abordagem C híbrida: motor de políticas central, hub MCP, hooks, supervisor; alternativas A e B rejeitadas) e ADR 0002 (modo auto aprova tudo, sem piso, sem PIN, sem expiração; risco aceito; mitigação: allowlist de usuário/dispositivo na Lambda), ambos com status "Aceito" e data 2026-11-09, citando o spec.
- [ ] **Step 5: Commit**

```bash
git add AGENTS.md CLAUDE.md docs/adr
git commit -m "docs: AGENTS.md e ADRs 0001 e 0002"
```

### Task 3: Gate de mensagem de commit (spec)

**Files:**
- Create: `scripts/gates/gates.json`, `scripts/gates/commit_msg.py`, `requirements-dev.txt`
- Test: `tests/gates/test_commit_msg.py`

**Interfaces:**
- Produces: `check_commit_message(message: str, repo_root: Path, config: dict) -> list[str]` (lista de erros; vazia = ok) e `main(argv: list[str]) -> int` (lê o arquivo da mensagem em `argv[1]`, imprime erros em stderr, retorna 1 se houver).
- `gates.json` produz as chaves `exempt_types: ["docs","chore"]`, `spec_dir: "docs/superpowers/specs"`, `architecture_paths: ["bridge/policy/*","bridge/mcp/*","bridge/supervisor/*","bridge/store/*","skill/interaction-model-pt-BR.json"]`, `adr_dir: "docs/adr"`.

- [ ] **Step 1: Escrever os testes que falham** em `tests/gates/test_commit_msg.py` (usar `tmp_path` com um arquivo de spec criado em `docs/superpowers/specs/x.md`):
  - `test_feat_sem_trailer_falha`: `"feat: algo"` → erro mencionando `Spec:`.
  - `test_feat_com_trailer_valido_passa`: `"feat: algo\n\nSpec: docs/superpowers/specs/x.md"` → `[]`.
  - `test_docs_e_chore_sao_isentos`: `"docs: x"` e `"chore: x"` → `[]`.
  - `test_trailer_com_spec_inexistente_falha`.
  - `test_trailer_com_crlf_passa`: mesma mensagem válida com `\r\n`.
  - `test_comentarios_do_git_sao_ignorados`: `"# Spec: docs/superpowers/specs/x.md\nfeat: algo"` → falha (o comentário não conta como trailer).
  - `test_merge_e_revert_sao_isentos`: `"Merge branch 'x'"` e `"Revert \"feat: x\""` → `[]`.
  - `test_spec_fora_do_spec_dir_falha`: `Spec: README.md` → erro; `Spec: docs\\superpowers\\specs\\x.md` (barra invertida) → passa, após normalizar.
  - `test_tipo_desconhecido_falha`: `"foo: x"` → erro listando os tipos válidos (`feat|fix|docs|chore|test|refactor`).
- [ ] **Step 2:** Rodar `python -m pip install -r requirements-dev.txt` e `python -m pytest tests/gates/test_commit_msg.py -v`. Esperado: FAIL (módulo inexistente).
- [ ] **Step 3:** Implementar `commit_msg.py` conforme a interface; normaliza `\r\n`, descarta linhas que começam com `#`, extrai o tipo do primeiro `tipo:`/`tipo(escopo):`, normaliza `\` para `/` no caminho do trailer.
- [ ] **Step 4:** Rodar os testes. Esperado: todos PASS.
- [ ] **Step 5: Commit**

```bash
git add scripts/gates tests/gates requirements-dev.txt
git commit -m "chore: gate commit-msg exige Spec para feat/fix/test/refactor"
```

### Task 4: Gate de pre-commit (ADR)

**Files:**
- Create: `scripts/gates/pre_commit.py`
- Test: `tests/gates/test_pre_commit.py`

**Interfaces:**
- Consumes: `gates.json` da Task 3 (`architecture_paths`, `adr_dir`).
- Produces: `check_staged(staged: list[tuple[str, str]], config: dict) -> list[str]`, em que `staged` vem de `git diff --cached --name-status` como pares `(status, path)` (`A`, `M`, `D`; renomeações `R100` já divididas em `D` do antigo e `A` do novo); `main() -> int` lê o staging via `git`.

- [ ] **Step 1: Escrever os testes que falham:**
  - `test_mudanca_de_arquitetura_sem_adr_falha`: `[("M","bridge/policy/engine.py")]` → erro.
  - `test_com_novo_adr_passa`: adicionar `("A","docs/adr/0003-x.md")` → `[]`.
  - `test_adr_existente_modificado_nao_basta`: `("M","docs/adr/0001-x.md")` → erro.
  - `test_remocao_de_arquivo_de_arquitetura_exige_adr`: `("D","bridge/mcp/server.py")` → erro.
  - `test_renomeacao_exige_adr`: `("D","bridge/store/a.py"),("A","bridge/store/b.py")` → erro.
  - `test_fora_da_lista_nao_exige`: `("M","README.md")` → `[]`.
- [ ] **Step 2:** Rodar `python -m pytest tests/gates/test_pre_commit.py -v`. Esperado: FAIL.
- [ ] **Step 3:** Implementar `pre_commit.py` com `fnmatch` sobre `architecture_paths`; um ADR novo é um `A` com caminho `docs/adr/NNNN-*.md` (`NNNN` com 4 dígitos, excluindo `0000-template.md`). `main()` usa `git diff --cached --name-status -M`.
- [ ] **Step 4:** Rodar todos os testes (`python -m pytest -v`). Esperado: PASS.
- [ ] **Step 5: Commit**

```bash
git add scripts/gates/pre_commit.py tests/gates/test_pre_commit.py
git commit -m "chore: gate pre-commit exige novo ADR em mudanca de arquitetura"
```

### Task 5: Ativar os hooks no git

**Files:**
- Create: `.githooks/commit-msg`, `.githooks/pre-commit`
- Modify: `AGENTS.md` (comando de instalação já descrito na Task 2, conferir)

- [ ] **Step 1:** Criar `.githooks/commit-msg` (`#!/bin/sh`, executa `python scripts/gates/commit_msg.py "$1"`) e `.githooks/pre-commit` (`#!/bin/sh`, executa `python scripts/gates/pre_commit.py`), ambos propagando o código de saída. Marcar executáveis com `git update-index --chmod=+x`.
- [ ] **Step 2:** Rodar `git config core.hooksPath .githooks`.
- [ ] **Step 3: Verificar o bloqueio:** criar `bridge/policy/engine.py` vazio, `git add` e `git commit -m "feat: x"`. Esperado: o commit é **recusado** (falta ADR e falta `Spec:`). Depois desfazer com `git reset` e remover o arquivo.
- [ ] **Step 4: Verificar a passagem:** `git commit --allow-empty -m "chore: hooks ativos"`. Esperado: sucesso.
- [ ] **Step 5: Commit** dos wrappers:

```bash
git add .githooks
git commit -m "chore: ativa hooks de gate via core.hooksPath"
```

### Task 6: Skills Anthropic no projeto

**Files:**
- Create: `.claude/skills/mcp-builder/`, `.claude/skills/skill-creator/` (cópias)

- [ ] **Step 1:** Em um diretório novo e vazio no scratchpad, `git clone --depth 1 https://github.com/anthropics/skills` (não executar nada de dentro dele).
- [ ] **Step 2:** Copiar apenas `skills/mcp-builder` e `skills/skill-creator` (se um não existir no repositório, listar o que existe e copiar o equivalente mais próximo, registrando a troca no commit) para `.claude/skills/` do projeto.
- [ ] **Step 3:** Verificar: cada pasta copiada contém um `SKILL.md` com frontmatter `name:` e `description:`.
- [ ] **Step 4:** Acrescentar ao `AGENTS.md` uma seção "Skills" listando as skills instaladas e quando usá-las (`mcp-builder` na fase 3).
- [ ] **Step 5: Commit**

```bash
git add .claude/skills AGENTS.md
git commit -m "chore: instala skills Anthropic mcp-builder e skill-creator"
```

---

## Self-Review

- **Spec §11:** gate de spec (Task 3), ADRs (Tasks 2 e 4), commits locais (Tasks 1 e 5), `AGENTS.md` (Task 2), skills (Task 6). Cobertura completa.
- **Spec §10:** commits da fase 1 sem trailer → todos usam `docs:`/`chore:`, isentos.
- **Consistência de tipos:** `config` vem de `gates.json` e é o mesmo dicionário nas duas funções; `architecture_paths` e `adr_dir` definidos na Task 3, usados na Task 4.
- **Fora do escopo desta fase:** motor de políticas, SQLite, MCP, supervisor, túnel (fases 2 a 6).
