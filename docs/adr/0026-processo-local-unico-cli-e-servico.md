# 0026. Processo local único, CLI `heycode` e serviço multiplataforma

## Status

Proposto. Data: 2026-11-13.

## Contexto

O MCP é iniciado pelo cliente do agente e não mantém conexão persistente, enquanto a ponte já roda como processo contínuo e monta o MCP em `/mcp` (ADR 0006). A operação é feita por scripts PowerShell e Tarefa Agendada do Windows (ADR 0011). Spec: `docs/superpowers/specs/2026-11-13-heycode-instalavel.md`.

## Decisão

- O componente local é o **processo único** `heycode serve` (ponte FastAPI com `/mcp`). Não há daemon separado do MCP; quando houver conexão de saída para o relay (P3), ela vive neste mesmo processo.
- Interface única em `argparse` (biblioteca padrão): `serve`, `hook`, `init`, `install-service`, `uninstall-service`, `rotate-secret`, `doctor`, `--version`.
- Serviço sempre no nível do usuário: Tarefa Agendada (Windows), LaunchAgent (macOS), `systemd --user` (Linux). Nunca administrador ou root. Comandos mutáveis fazem dry-run por padrão e só agem com `--apply`.
- `heycode hook` falha aberto e importa só a biblioteca padrão, para não atrasar nem travar o agente.
- Alternativas rejeitadas: MCP por `stdio` como processo próprio (duplica estado e política; pode ser um proxy fino no futuro); `click`/`typer` (dependência nova sem necessidade); serviço do Windows com NSSM (dependência e administrador).

## Consequências

Um único artefato para instalar e diagnosticar. Os scripts `run-bridge`, `install-service`, `uninstall-service` e `rotate-secret` do PowerShell saem. Este ADR substitui o ADR 0011 apenas na forma de executar o serviço; túnel nomeado e rotação de segredo continuam. macOS e Linux são validados por geração de artefato e pelo CI, não por execução real do gerenciador de serviço.
