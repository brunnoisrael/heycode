# 0007. Supervisor de agentes headless

## Status

Aceito. Data: 2026-11-09.

## Contexto

A fase 4 da spec (`docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`, G4, G6 e §10) quer que, depois da
confirmação do ditado, a ponte inicie um agente (Claude, Codex ou Aider), guarde a saída e avise no fim. O spike
(`docs/superpowers/specs/2026-11-09-spike-codex-aider.md`) mostrou que os três têm modo headless, que o Codex tem um
`app-server` JSON-RPC experimental e que o Aider só roda por processo. O modo auto não tem piso (ADR 0002).

## Decisão

- Processo filho, não `codex app-server`: `bridge/supervisor` roda `subprocess.Popen` por execução, em thread própria,
  e guarda tudo na tabela `runs` do store (`rodando`, `concluida`, `falhou`, `cancelada`, `interrompida`). Um único
  mecanismo cobre os três agentes; o app-server é experimental e só serve ao Codex.
- Os comandos vêm de um mapa injetável (`commands`), com padrão `codex`, `claude`, `aider`; os testes usam `python -c`
  e nunca chamam agente real. `build_command` rejeita agente desconhecido com `ValueError`.
- Modos e sandbox: `auto` roda sem restrição (`codex exec -s danger-full-access`, `claude -p
  --dangerously-skip-permissions`); `manual` e `decisoes` rodam com sandbox restrito (`-s workspace-write`, `claude -p`
  com permissão padrão). O Aider não tem sandbox e roda igual em todos os modos (`--yes-always`), só depois da
  confirmação do ditado; o risco é aceito.
- Resumo: última mensagem do agente (Codex: arquivo de `-o`; Claude: campo `result` do JSON; Aider: cauda do stdout),
  no máximo 400 caracteres, com `mask_secrets` (`bridge/policy/redact.py`). Código de saída diferente de zero vira
  `falhou` com as últimas linhas da saída, também mascaradas.
- Cancelamento mata a árvore inteira (`taskkill /T /F` no Windows, `killpg` fora dele) e marca `cancelada`.
- No startup, `interrupt_running` converte execuções `rodando` em `interrompida`; não há reanexação (§10).
- Falhas ao iniciar ou ao finalizar viram `falhou`; `on_finish` que lança exceção é ignorado. A ponte nunca cai por
  causa de um agente.
- Flags conferidos com `--help` nesta máquina: `codex exec` tem `-C/--cd`, `-s/--sandbox`
  (`read-only|workspace-write|danger-full-access`), `--json`, `-o/--output-last-message` e `--skip-git-repo-check`;
  `claude` tem `-p/--print`, `--output-format` (`text|json|stream-json`, só com `--print`) e
  `--dangerously-skip-permissions`; `aider` tem `--message/-m`, `--yes-always`, `--no-pretty` e `--no-auto-commits`.
  Nada foi executado com modelo; o formato real dos eventos do Codex e a falta de `-C` no Claude e no Aider (usa-se o
  `cwd` do processo) seguem do help.
- Alternativas rejeitadas: `codex app-server` como base (experimental, um agente só) e PTY com respostas y/n (frágil).

## Consequências

- Um caminho único para iniciar, cancelar e consultar execuções, com resultado persistido em `runs` e rotas
  `/runs` autenticadas.
- Sem reanexo: reiniciar a ponte perde o acompanhamento de execuções em andamento (os processos órfãos não são
  mortos), registrado como `interrompida`.
- O resumo do Claude e do Codex depende do formato de saída das CLIs; se mudar, cai para a cauda do stdout.
- O modo auto e o Aider rodam sem sandbox; a mitigação é a confirmação obrigatória do ditado (ADR 0008).
