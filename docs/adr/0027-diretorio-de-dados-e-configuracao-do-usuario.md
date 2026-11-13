# 0027. Diretório de dados e configuração do usuário

## Status

Proposto. Data: 2026-11-13.

## Contexto

`bridge.db` e `.env` ficam dentro do clone (ADR 0003, ADR 0014), com comandos aprovados e segredos misturados ao código. Um pacote instalado não pode gravar em seu próprio diretório. Spec: `docs/superpowers/specs/2026-11-13-heycode-instalavel.md`.

## Decisão

- Um diretório por usuário: `HEYCODE_HOME` se definido; senão `%APPDATA%\heycode` (Windows), `~/Library/Application Support/heycode` (macOS), `$XDG_DATA_HOME/heycode` ou `~/.local/share/heycode` (Linux). Cria com permissão restrita onde o sistema suporta.
- Arquivos: `config.env` (segredos, 0600) e `heycode.db`.
- As variáveis de ambiente (`BRIDGE_DB`, `BRIDGE_SECRET`, `BRIDGE_CONTROL_SECRET`, `BRIDGE_PIN`, `BRIDGE_URL` e as demais) prevalecem sobre `config.env`, mantendo compatibilidade com Lambda, hooks e MCP já configurados.
- Segredos gerados por CSPRNG (`secrets`), distintos entre si (ADR 0014), e nunca impressos.
- Migração por `heycode init --import-legacy <clone>`: copia sem sobrescrever e sem apagar a origem.
- Alternativas rejeitadas: `platformdirs` (dependência pequena, mas a regra aqui cabe em 20 linhas e é testável); manter `.env` no diretório atual (depende de onde o comando roda).

## Consequências

O estado sobrevive a atualizações do pacote e fica fora do repositório. O esquema do banco não muda nesta decisão. No Windows não há 0600; o diretório fica no perfil do usuário e o `doctor` avisa se estiver fora dele. Quem já roda a ponte a partir do clone precisa executar a importação uma vez.
