# 0028. Migração de `bridge/` para `src/heycode/`

## Status

Aceito. Data: 2026-11-13.

## Contexto

Execução da trilha P1 (ADR 0025 a 0027): o código sai de `bridge/` e vira o pacote instalável `heycode`. Spec: `docs/superpowers/specs/2026-11-13-heycode-instalavel.md`.

## Decisão

- Migração em **um commit atômico** (`git mv` mais reescrita mecânica de imports), verificada pela suíte inteira antes e depois (668 testes, mesma contagem).
- `bridge/mcp` vira `heycode.mcp_server` e `bridge/server.py` vira `heycode.app`; o carregamento por caminho de arquivo do ADR 0006 deixa de existir.
- `bridge/hook.py` vira `heycode.hook` com a função `run(argv)`, que sempre devolve 0; fica executável por `python -m heycode.hook` e, na tarefa P1.5, por `heycode hook`.
- Os modelos copiados para projetos criados por voz (`scripts/gates` e `.githooks`) viajam dentro do pacote em `heycode/_template/` (`force-include` do hatchling) e `heycode.templates.template_root()` escolhe o pacote ou, no clone, a raiz do repositório.
- O caminho padrão do banco continua provisório dentro do pacote até a tarefa P1.4 (diretório do usuário).
- `scripts/gates/gates.json`, `diff_coverage.py`, `ci.yml` e `CODEOWNERS` passam a apontar para `src/heycode/...`, como a spec autoriza.

## Consequências

Imports absolutos e instalável por `pip install .`. Quem registrou hooks com `python .../bridge/hook.py` precisa trocar o comando (o `doctor` da P1.7 detecta). Clones antigos com `bridge.db` e `.env` usam `heycode init --import-legacy` (P1.4).
