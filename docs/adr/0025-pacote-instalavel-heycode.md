# 0025. Pacote instalável `heycode` com layout `src/`

## Status

Aceito. Data: 2026-11-13.

## Contexto

O código vive em `bridge/` e depende de estar no `sys.path` (`from policy.engine import ...`); o pacote `bridge/mcp` faz sombra ao SDK `mcp`, e o ADR 0006 contorna isso carregando o módulo por caminho de arquivo. Não há `pyproject.toml`, então ninguém instala o projeto com `pipx` ou `pip`. Spec: `docs/superpowers/specs/2026-11-13-heycode-instalavel.md`.

## Decisão

- Pacote `heycode` em `src/heycode/`, construído com `hatchling`, `requires-python = ">=3.11,<3.15"` (a mesma matriz do CI).
- Subpacotes com os nomes atuais, exceto `mcp` → `mcp_server`; `server.py` → `app.py`; `hook.py` permanece como módulo `heycode.hook`.
- Imports absolutos (`heycode.policy.engine`); remove-se o truque de carga de módulo do ADR 0006.
- Dependências com faixa compatível em `pyproject.toml` (`fastapi`, `uvicorn`, `httpx`, `mcp>=1.30,<2`) e versões exatas em `constraints.txt`, usado no CI.
- Alternativas rejeitadas: manter `bridge/` e adicionar só um `pyproject.toml` (perpetua o `sys.path` e a sombra do `mcp`); `setuptools` como backend (funciona, mas exige mais configuração para o layout `src`); fixar tudo no `pyproject.toml` (quebra a instalação junto de outras ferramentas via `pipx`).

## Consequências

Instalação por `pipx install heycode` (quando publicado) e `pip install .` hoje. Os testes passam a importar `heycode.*`. Os caminhos protegidos e de arquitetura em `scripts/gates/gates.json` mudam de `bridge/...` para `src/heycode/...`. Ao subir o `mcp` além da faixa é preciso revisar a API (a 2.x renomeou o FastMCP).
