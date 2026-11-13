# HeyCode instalável (P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma pessoa em máquina limpa Windows, macOS ou Linux instala, configura, inicia e diagnostica a ponte local só com o CLI `heycode`.

**Architecture:** O código de `bridge/` vira o pacote `src/heycode/` (mesmos subpacotes, `mcp` → `mcp_server`), com um módulo `paths`/`config` para o diretório do usuário, um CLI `argparse`, geradores de serviço por sistema e um `doctor` por camada. Nenhuma regra de negócio de voz, política ou agente muda.

**Tech Stack:** Python 3.11 a 3.14, `hatchling`, FastAPI, uvicorn, httpx, `mcp>=1.30,<2`, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-11-13-heycode-instalavel.md` (precisa estar com `Status: aprovada` antes da Tarefa P1.2). ADRs 0025, 0026, 0027.

## Global Constraints

- `requires-python = ">=3.11,<3.15"`; nome do pacote `heycode`; versão `0.1.0`; layout `src/heycode/`.
- Estado e configuração em `HEYCODE_HOME`, senão `%APPDATA%\heycode` / `~/Library/Application Support/heycode` / `$XDG_DATA_HOME/heycode` ou `~/.local/share/heycode`; arquivos `config.env` (0600) e `heycode.db`.
- Variáveis de ambiente (`BRIDGE_DB`, `BRIDGE_SECRET`, `BRIDGE_CONTROL_SECRET`, `BRIDGE_PIN`, `BRIDGE_URL`, `BRIDGE_PUBLIC_URL`, `PROJECTS_ROOT`, etc.) prevalecem sobre o arquivo.
- Segredos por CSPRNG: `BRIDGE_SECRET` e `BRIDGE_CONTROL_SECRET` com 32 bytes aleatórios (64 hex), distintos; `BRIDGE_PIN` com 6 dígitos. Nunca impressos.
- `heycode hook` falha aberto: qualquer erro sai com 0, só biblioteca padrão, menos de 2 s com a ponte fora do ar.
- Comandos mutáveis (`install-service`, `uninstall-service`, `rotate-secret`) fazem dry-run por padrão; `--apply` age e é idempotente. Serviço sempre no nível do usuário.
- Nenhuma regra de política, voz ou agente muda; cobertura de ramos de 100% em `policy` mantida.
- Cada tarefa é um commit (`feat|fix|refactor|test`) com trailer `Spec:` e até 400 linhas adicionadas (G12; renomeações puras não contam). Commits ficam locais até o dono publicar.

## Review Focus

1. **Caminho com espaços e acentos** (`C:\Users\João Silva\...`) em `init`, `serve` e no artefato do serviço: esperado = funciona, com aspas corretas.
2. **`init` repetido ou com `config.env` existente:** esperado = nunca sobrescreve segredo, informa o que já existe.
3. **Importação legada com destino já existente ou origem sem `.env`:** esperado = não sobrescreve, copia o que existir e relata o resto.
4. **`rotate-secret` interrompido ou sem serviço instalado:** esperado = backup íntegro, `config.env` nunca fica vazio ou parcial (escrita atômica).
5. **Hook antigo (`python .../bridge/hook.py`) ainda registrado depois da mudança:** esperado = `doctor` detecta e orienta; o hook novo não quebra o agente.
6. **Porta 8765 em uso ou ponte já rodando:** esperado = `serve` falha com mensagem clara; `doctor` distingue "outra coisa na porta" de "ponte saudável".

## File Structure

- Create: `pyproject.toml`, `constraints.txt`, `src/heycode/__init__.py`, `src/heycode/cli.py`, `src/heycode/paths.py`, `src/heycode/config.py`, `src/heycode/service.py`, `src/heycode/doctor.py`
- Move (`git mv`): `bridge/{policy,store,supervisor,projects,dictation}` → `src/heycode/`, `bridge/mcp` → `src/heycode/mcp_server`, `bridge/server.py` → `src/heycode/app.py`, `bridge/hook.py` → `src/heycode/hook.py`
- Modify: `scripts/gates/{gates.json,diff_coverage.py}`, `.github/workflows/ci.yml`, `.github/CODEOWNERS`, `tests/**` (imports), `README.md`, `docs/DEPLOY-ALEXA.md`, `CONTRIBUTING.md`
- Delete: `bridge/requirements.txt`, `scripts/{run-bridge,install-service,uninstall-service,rotate-secret}.ps1`
- Docs: `docs/QUICKSTART.md`, `docs/OPERATIONS.md`

---

### Task P1.1: Spec e ADRs (já redigidos)

- [ ] Spec `2026-11-13-heycode-instalavel.md` e ADRs 0025 a 0027 revisados e com spec `Status: aprovada` dada por uma pessoa. Sem isso, nada abaixo começa.

### Task P1.2: Esqueleto do pacote e `heycode --version`

**Files:**
- Create: `pyproject.toml`, `constraints.txt`, `src/heycode/__init__.py`, `src/heycode/cli.py`
- Test: `tests/cli/test_cli_version.py`

**Interfaces:**
- Produces: `heycode.__version__: str` (`"0.1.0"`); `heycode.cli.main(argv: list[str] | None = None) -> int`; entrada `[project.scripts] heycode = "heycode.cli:main"`.

- [ ] **Step 1:** Teste `test_version_imprime_a_versao` (`main(["--version"])` retorna 0 e imprime `0.1.0`), `test_sem_argumentos_mostra_ajuda_e_retorna_2`, `test_pyproject_declara_faixa_de_python` (lê `pyproject.toml` com `tomllib`: `requires-python == ">=3.11,<3.15"`, nome `heycode`).
- [ ] **Step 2:** `python -m pytest tests/cli -q`; esperado FAIL (módulo inexistente).
- [ ] **Step 3:** Criar `pyproject.toml` (hatchling, pacote `src/heycode`, dependências `fastapi>=0.135,<1`, `uvicorn>=0.42,<1`, `httpx>=0.28,<1`, `mcp>=1.30,<2`) e `constraints.txt` com as versões exatas hoje em `bridge/requirements.txt`; `cli.main` com `argparse` e subcomandos ainda vazios.
- [ ] **Step 4:** `python -m pip install -e . -c constraints.txt` e `python -m pytest tests/cli -q`; esperado PASS.
- [ ] **Step 5:** Commit `feat: esqueleto do pacote heycode e comando --version`.

### Task P1.3: Mover `bridge/` para `src/heycode/` (commit atômico)

**Files:**
- Move: ver File Structure. Modify: todos os `import`s em `src/heycode/**` e `tests/**`; `scripts/gates/gates.json`, `scripts/gates/diff_coverage.py`, `.github/workflows/ci.yml`, `.github/CODEOWNERS`. Delete: `bridge/requirements.txt`.
- Test: suíte inteira existente.

**Interfaces:**
- Produces: `heycode.app.app` (o `FastAPI` que era `server.app`), `heycode.hook.run(argv: list[str]) -> int` (o corpo hoje executado no nível do módulo), `heycode.mcp_server.server` (o que era `bridge/mcp/server.py`).
- Consumes: `heycode.__version__` (P1.2).

- [ ] **Step 1:** `python -m pytest -q` e guardar a contagem verde de referência (esperado: todos passando).
- [ ] **Step 2:** `git mv` de cada item; renomear `mcp` → `mcp_server`; ajustar imports para absolutos (`from heycode.policy.engine import decidir`); remover `_load_mcp_module` de `app.py` e importar `heycode.mcp_server.server` diretamente; envolver o corpo de `hook.py` em `run(argv)` com `try/except` que retorna 0.
- [ ] **Step 3:** Reescrever imports dos testes (`from bridge.x` → `from heycode.x`; o `conftest` de `tests/server` passa a importar `heycode.app`); atualizar `gates.json` (`bridge/` → `src/heycode/`, `bridge/mcp` → `src/heycode/mcp_server`, `code_globs`), `POLICY_GLOB = "src/heycode/policy/*"`, `--source=src/heycode,scripts/gates` e instalação por `-e . -c constraints.txt` no CI; regenerar o `CODEOWNERS` a partir do `gates.json`.
- [ ] **Step 4:** `python -m pytest -q`; esperado: mesma contagem do Step 1, tudo PASS. Rodar também `python -m ruff check --config scripts/gates/ruff.toml src tests`.
- [ ] **Step 5:** Confirmar `git diff --numstat -M main..HEAD` sem estourar 400 linhas adicionadas (renomeações puras não contam).
- [ ] **Step 6:** Incluir os ADRs 0025 e 0026 no mesmo commit (o gate G3 exige ADR novo para mexer em caminhos de arquitetura). Commit `refactor: move bridge para o pacote heycode`.

### Task P1.4: Diretório do usuário, `init` e importação legada

**Files:**
- Create: `src/heycode/paths.py`, `src/heycode/config.py`
- Modify: `src/heycode/cli.py`, `src/heycode/app.py` (caminho do banco)
- Test: `tests/cli/test_paths.py`, `tests/cli/test_config_init.py`

**Interfaces:**
- Produces:
  - `paths.home(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path`
  - `paths.db_path(env=None) -> Path` (respeita `BRIDGE_DB`) e `paths.config_file(env=None) -> Path`
  - `config.load_env_file(path: Path) -> dict[str, str]` e `config.apply_env(values: Mapping[str, str], environ=os.environ) -> None` (só define o que faltar)
  - `config.init_home(home: Path) -> dict[str, str]` (retorna `{"created": [...], "kept": [...]}`; gera segredos; escrita atômica 0600)
  - `config.import_legacy(src: Path, home: Path) -> dict[str, list[str]]` (`copied`, `skipped`, `missing`)
- Consumes: `cli.main` (P1.2).

- [ ] **Step 1:** Testes: `test_home_por_sistema` (Windows/macOS/Linux, com `HEYCODE_HOME`, `XDG_DATA_HOME` e padrão), `test_db_path_respeita_bridge_db`, `test_init_cria_segredos_distintos_de_64_hex_e_pin_de_6_digitos`, `test_init_nao_sobrescreve_config_existente`, `test_init_cria_arquivo_com_permissao_0600` (pula no Windows), `test_apply_env_nao_sobrescreve_variavel_ja_definida`, `test_import_legacy_copia_sem_apagar_origem`, `test_import_legacy_nao_sobrescreve_destino`, `test_import_legacy_origem_sem_env_relata_missing`, `test_init_com_caminho_com_espacos_e_acentos` (`João Silva`).
- [ ] **Step 2:** `python -m pytest tests/cli/test_paths.py tests/cli/test_config_init.py -q`; esperado FAIL.
- [ ] **Step 3:** Implementar `paths` e `config`; escrever com arquivo temporário no mesmo diretório e `os.replace`; `chmod 0o600` fora do Windows; saída do `init` lista nomes, nunca valores; ligar o subcomando `init [--import-legacy DIR]`; fazer `app.py` usar `paths.db_path()` quando `BRIDGE_DB` não estiver definido.
- [ ] **Step 4:** `python -m pytest -q`; esperado PASS.
- [ ] **Step 5:** Commit `feat: diretorio do usuario, init e importacao do estado legado` com o ADR 0027.

### Task P1.5: `serve` e `hook` no CLI

**Files:**
- Modify: `src/heycode/cli.py`, `bridge/claude-settings.example.json` → `docs/claude-settings.example.json` (comando `heycode hook`), `scripts/setup-agents.ps1`
- Test: `tests/cli/test_serve_hook.py`

**Interfaces:**
- Produces: subcomandos `serve [--host H] [--port P]` (carrega `config.env` com `config.apply_env` e chama `uvicorn.run("heycode.app:app", host=H, port=P)`) e `hook [approve] [--agent A]` (chama `heycode.hook.run(argv)`).
- Consumes: `config.load_env_file`, `config.apply_env`, `heycode.hook.run`.

- [ ] **Step 1:** Testes: `test_serve_carrega_config_sem_sobrescrever_ambiente` (uvicorn simulado), `test_serve_porta_ocupada_da_mensagem_clara`, `test_hook_com_ponte_fora_do_ar_sai_com_0_em_menos_de_2s`, `test_hook_nao_importa_fastapi` (verifica `sys.modules`), `test_hook_aceita_approve_e_agent`.
- [ ] **Step 2:** `python -m pytest tests/cli/test_serve_hook.py -q`; esperado FAIL.
- [ ] **Step 3:** Implementar os dois subcomandos com import tardio (`serve` importa uvicorn só ao executar); mover o exemplo de configuração dos hooks e atualizar `setup-agents.ps1`.
- [ ] **Step 4:** `python -m pytest -q`; esperado PASS.
- [ ] **Step 5:** Commit `feat: comandos serve e hook no CLI`.

### Task P1.6: Serviço multiplataforma e `rotate-secret`

**Files:**
- Create: `src/heycode/service.py`
- Modify: `src/heycode/cli.py`, `src/heycode/config.py`; Delete: `scripts/{run-bridge,install-service,uninstall-service,rotate-secret}.ps1`
- Test: `tests/cli/test_service.py`, `tests/cli/test_rotate_secret.py`

**Interfaces:**
- Produces: `service.ServiceSpec` (dataclass: `path: Path | None`, `content: str`, `install: list[list[str]]`, `uninstall: list[list[str]]`); `service.render(platform: str, exe: str, home: Path) -> ServiceSpec`; `service.install(*, platform=None, apply=False, runner=subprocess.run) -> list[str]` e `service.uninstall(...)`; `config.rotate_secret(home: Path, now: Callable[[], float] = time.time) -> Path` (devolve o caminho do backup).
- Consumes: `paths.home`, `config.init_home`.

- [ ] **Step 1:** Testes: `test_render_windows_gera_comando_schtasks` (logon do usuário, sem privilégio elevado, caminho com espaços entre aspas), `test_render_macos_gera_plist_valido` (`plistlib.loads` aceita; `RunAtLoad`, `KeepAlive`, `ProgramArguments` com `serve`), `test_render_linux_gera_unidade_systemd_user` (seções `[Unit]`, `[Service]`, `[Install]`, `ExecStart`, `Restart=on-failure`), `test_dry_run_nao_executa_nada`, `test_apply_chama_o_executor_e_e_idempotente`, `test_nunca_pede_administrador`, `test_rotate_secret_gera_backup_0600_e_nao_imprime_o_valor`, `test_rotate_secret_interrompido_nao_deixa_config_parcial`, `test_rotate_secret_sem_servico_instalado_funciona`.
- [ ] **Step 2:** `python -m pytest tests/cli/test_service.py tests/cli/test_rotate_secret.py -q`; esperado FAIL.
- [ ] **Step 3:** Implementar `render`/`install`/`uninstall` por sistema e `rotate_secret` com escrita atômica; ligar `install-service`, `uninstall-service`, `rotate-secret`; remover os quatro `.ps1`.
- [ ] **Step 4:** `python -m pytest -q`; esperado PASS.
- [ ] **Step 5:** Commit `feat: servico multiplataforma e rotacao de segredo no CLI` com o ADR 0026 se ainda não incluído.

### Task P1.7: `doctor`

**Files:**
- Create: `src/heycode/doctor.py`
- Modify: `src/heycode/cli.py`
- Test: `tests/cli/test_doctor.py`

**Interfaces:**
- Produces: `doctor.Check` (dataclass: `name: str`, `layer: str`, `status: Literal["ok","aviso","falha"]`, `detail: str`, `fix: str`); `doctor.run_checks(env: Mapping[str, str], home: Path, *, http=urllib.request.urlopen, which=shutil.which, py_version=sys.version_info) -> list[Check]`; subcomando `doctor [--json]` (saída 1 se houver `falha`).
- Consumes: `paths`, `config`.

- [ ] **Step 1:** Testes: `test_python_fora_da_faixa_falha`, `test_diretorio_sem_escrita_falha`, `test_segredos_ausentes_ou_curtos_ou_iguais_falham`, `test_ponte_fora_do_ar_falha_na_camada_ponte`, `test_porta_ocupada_por_outro_servico_e_distinta_de_ponte_saudavel`, `test_rota_protegida_sem_segredo_deve_dar_401`, `test_agente_ausente_no_path_e_aviso`, `test_hook_antigo_do_bridge_e_detectado_e_orienta`, `test_rede_externa_sem_url_e_aviso`, `test_alexa_e_sempre_aviso`, `test_saida_json_e_valida_e_nao_contem_segredos`, `test_exit_code_1_quando_ha_falha`.
- [ ] **Step 2:** `python -m pytest tests/cli/test_doctor.py -q`; esperado FAIL.
- [ ] **Step 3:** Implementar as verificações por camada (ambiente, configuração, ponte, autenticação, agentes, rede externa, alexa) com executor HTTP e `which` injetáveis; mensagem de `fix` em português para cada falha.
- [ ] **Step 4:** `python -m pytest -q`; esperado PASS.
- [ ] **Step 5:** Commit `feat: comando doctor por camada`.

### Task P1.8: Instalação limpa no CI e documentação de entrada

**Files:**
- Create: `docs/QUICKSTART.md`, `docs/OPERATIONS.md`
- Modify: `.github/workflows/ci.yml` (job `instalacao-limpa`), `README.md`, `docs/DEPLOY-ALEXA.md`, `CONTRIBUTING.md`, `scripts/{smoke,diagnose-connection}.ps1`
- Test: `tests/cli/test_docs_paths.py`

**Interfaces:**
- Consumes: todos os subcomandos de P1.2 a P1.7.

- [ ] **Step 1:** Testes: `test_docs_nao_citam_caminhos_removidos` (nenhum `.md` ativo cita `run-bridge.ps1`, `bridge/hook.py` ou `bridge/requirements.txt`, exceto ADRs e planos históricos), `test_quickstart_cita_todos_os_subcomandos`.
- [ ] **Step 2:** `python -m pytest tests/cli/test_docs_paths.py -q`; esperado FAIL.
- [ ] **Step 3:** Escrever o guia (instalar → `init` → `serve` → `install-service` → registrar hooks e MCP → `doctor`), `OPERATIONS.md` (reiniciar, rotacionar, recuperar) e atualizar README e DEPLOY; criar o job `instalacao-limpa` (matriz Windows, macOS e Linux com Python 3.12; constrói a roda, cria venv novo, instala só a roda, `heycode init`, `heycode serve` em segundo plano, espera `/health`, `heycode doctor --json`, falha se camadas ambiente, configuração, ponte ou autenticação não forem `ok`, e se passar de 5 minutos).
- [ ] **Step 4:** `python -m pytest -q`; esperado PASS. Medir à mão uma instalação a partir do guia e anotar o tempo no commit.
- [ ] **Step 5:** Commit `docs: guia de instalacao e job de instalacao limpa no CI`.

## Self-Review

- **Cobertura da spec:** pacote e imports (P1.2, P1.3), estado e `init` (P1.4), `serve`/`hook` (P1.5), serviço e `rotate-secret` (P1.6), `doctor` (P1.7), instalação limpa e docs (P1.8), gates e CI (P1.3), migração legada (P1.4).
- **Verificação que não dá para fazer aqui:** serviço real em macOS e Linux e o CI de instalação limpa; ficam para o primeiro push.
- **Proporção:** os passos listam testes e assinaturas, sem corpos de função.
