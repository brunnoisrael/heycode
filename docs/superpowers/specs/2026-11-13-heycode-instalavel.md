# HeyCode instalável: pacote, CLI e operação multiplataforma

Data: 2026-11-13. Status: aprovada pelo dono em 2026-11-13 ("li e gostei, pode aprovar"; registrado pelo agente a pedido expresso).

Visão: `docs/ROADMAP-HEYCODE.md`. Programa: `docs/superpowers/plans/2026-11-13-heycode-publicavel-e-esteira-de-agentes.md` (trilha P1). Esteira: `docs/superpowers/specs/2026-11-13-esteira-obrigatoria-de-agentes.md`.

## 1. Intenção e porquê

Hoje o HeyCode só roda a partir de um clone, no Windows, com `bridge/` no `sys.path`, `.env` e `bridge.db` dentro do código e scripts PowerShell para operar. Isso impede que qualquer outra pessoa o instale e é a causa do truque de carga de módulo do ADR 0006 (o pacote `bridge/mcp` faz sombra ao SDK `mcp`). A meta desta spec é: **uma pessoa em máquina limpa Windows, macOS ou Linux instala, configura, inicia e diagnostica a ponte local com comandos de um único CLI, sem editar arquivo nenhum à mão**.

## 2. Escopo

Dentro: pacote Python instalável `heycode`; CLI; diretório de dados e configuração do usuário; migração do estado atual; serviço em segundo plano nos três sistemas; rotação de segredo; `doctor`; documentação de entrada; verificação de instalação limpa no CI.

Fora: relay, contas e skill compartilhada (P3/P4); protocolo e identidade (P2); mudança de comportamento de voz, políticas ou agentes (nenhuma regra de negócio muda); túnel Cloudflare (os scripts de túnel ficam como estão e serão substituídos pelo relay).

## 3. Decisões (viram os ADRs 0025 a 0027)

**Pacote (ADR 0025).** Nome `heycode`, layout `src/heycode/`, backend de build `hatchling`, `requires-python = ">=3.11,<3.15"`, versão inicial `0.1.0`. Os subpacotes migram de `bridge/` com os mesmos nomes (`policy`, `store`, `supervisor`, `projects`, `dictation`), exceto `mcp`, que vira `mcp_server`. `bridge/server.py` vira `heycode/app.py` e `bridge/hook.py` vira `heycode/hook.py`. Imports passam a ser absolutos (`heycode.policy.engine`) e o truque de carga de módulo do ADR 0006 é removido. Dependências com faixa compatível no `pyproject.toml` e versões exatas em `constraints.txt`, que o CI usa e o Dependabot atualiza.

**Processo local e CLI (ADR 0026).** O componente local é o **processo único** `heycode serve` (a ponte FastAPI que já monta o MCP em `/mcp`); não há daemon separado do MCP. O CLI usa `argparse` da biblioteca padrão, sem dependência nova. O serviço em segundo plano é gerado por sistema: Tarefa Agendada no Windows, `launchd` (LaunchAgent) no macOS e unidade `systemd --user` no Linux; sempre no nível do usuário, nunca como administrador/root. Este ADR substitui a parte de execução do ADR 0011 (Tarefa Agendada via PowerShell); túnel e rotação de segredo do ADR 0011 seguem valendo.

**Estado e configuração (ADR 0027).** Tudo que hoje fica no clone passa a um diretório do usuário: `HEYCODE_HOME`, se definido; senão `%APPDATA%\heycode` (Windows), `~/Library/Application Support/heycode` (macOS), `$XDG_DATA_HOME/heycode` ou `~/.local/share/heycode` (Linux). Conteúdo: `config.env` (segredos, permissão 0600 onde o sistema suporta) e `heycode.db`. As variáveis `BRIDGE_DB`, `BRIDGE_SECRET`, `BRIDGE_CONTROL_SECRET`, `BRIDGE_PIN`, `BRIDGE_URL` e demais continuam funcionando e **prevalecem** sobre o arquivo (compatibilidade com Lambda, hooks e MCP já configurados).

## 4. Comportamento do CLI

| Comando | O que faz |
|---|---|
| `heycode --version` | Imprime a versão instalada. |
| `heycode init [--import-legacy DIR]` | Cria o diretório de dados e `config.env` com `BRIDGE_SECRET` e `BRIDGE_CONTROL_SECRET` (32 bytes aleatórios cada, distintos) e `BRIDGE_PIN` (6 dígitos) por CSPRNG. Não sobrescreve nada que exista. Com `--import-legacy`, copia `bridge.db` e `.env` do clone antigo se o destino ainda não existir. Nunca imprime segredos. |
| `heycode serve [--host H] [--port P]` | Carrega `config.env` (sem sobrescrever variáveis já definidas) e sobe a ponte em `127.0.0.1:8765` por padrão. |
| `heycode hook [approve] [--agent A]` | Ponto de entrada dos hooks dos agentes (substitui `python .../bridge/hook.py`). **Falha aberta**: qualquer erro termina com saída 0 e não trava o agente; importa só a biblioteca padrão. |
| `heycode install-service [--apply]` / `uninstall-service [--apply]` | Sem `--apply`, imprime o arquivo e os comandos que usaria (dry-run é o padrão). Com `--apply`, instala/remove e é idempotente. |
| `heycode rotate-secret [--apply]` | Gera novo `BRIDGE_SECRET`, guarda backup do `config.env` com permissão restrita, reinicia o serviço se instalado e lista o que atualizar (Lambda, hooks, MCP). Nunca imprime o segredo. |
| `heycode doctor [--json]` | Diagnóstico por camada (§5). Saída 1 se houver falha. |

## 5. `doctor`

Cada verificação devolve `ok`, `aviso` ou `falha`, a camada e uma correção sugerida, sem expor segredos. Camadas: **ambiente** (versão do Python, diretório gravável), **configuração** (segredos presentes, com 32+ caracteres e diferentes entre si; banco abre), **ponte** (processo respondendo em `/health`), **autenticação** (rota protegida devolve 401 sem segredo e 200 com ele; `/mcp` idem), **agentes** (`claude`, `codex`, `aider` no PATH; hook do Claude registrado em `~/.claude/settings.json`), **rede externa** (se `BRIDGE_PUBLIC_URL` estiver definida, alcança `/health` por ela; senão, `aviso`) e **alexa** (sempre `aviso`: não é verificável localmente, com instrução de teste no console). Isso cobre o diagnóstico exigido pelo M0.

## 6. Migração do estado atual

`heycode init --import-legacy <clone>` copia `bridge.db` e `.env` sem alterar o original e sem sobrescrever o destino. O banco copiado abre com o mesmo esquema (nenhuma migração de esquema nesta spec). Os scripts `run-bridge.ps1`, `install-service.ps1`, `uninstall-service.ps1` e `rotate-secret.ps1` são removidos; `smoke.ps1`, `diagnose-connection.ps1`, `setup-agents.ps1` e os de túnel são atualizados para chamar o CLI ou apontar para os novos caminhos.

## 7. Gates e configuração que mudam (pedido humano explícito desta spec)

Por causa da mudança de caminho, esta spec autoriza atualizar, em commits dedicados: `architecture_paths`, `human_review_paths` e `code_globs` em `scripts/gates/gates.json` (de `bridge/...` para `src/heycode/...`); `POLICY_GLOB` em `scripts/gates/diff_coverage.py`; o `--source` de cobertura e a instalação de dependências em `.github/workflows/ci.yml`; e o `CODEOWNERS` (gerado a partir do `gates.json`). Essas alterações exigem aprovação humana no PR, como todo caminho protegido.

## 8. Critérios de aceite

- Em máquina limpa de cada sistema, no CI: instalar a roda recém-construída em um ambiente virtual novo, `heycode init`, `heycode serve` em segundo plano e `heycode doctor --json` sem falhas nas camadas ambiente, configuração, ponte e autenticação.
- Instalar a partir do guia leva menos de 10 minutos medidos por uma pessoa que não conhece o projeto; o CI da instalação limpa termina em menos de 5 minutos.
- Toda a suíte de testes atual continua verde depois da mudança de pacote, com cobertura de ramos de 100% mantida em `policy`.
- `heycode install-service` (dry-run) gera artefato válido nos três sistemas, validado por teste: XML do `launchd` bem formado, unidade `systemd` com as seções esperadas, comando `schtasks` com argumentos corretos; o `--apply` é testado com executor simulado.
- Caminhos com espaços e acentos (ex.: `C:\Users\João Silva\...`) funcionam em `init`, `serve` e no artefato do serviço.
- `heycode hook` com a ponte fora do ar termina com saída 0 em menos de 2 segundos.
- `rotate-secret` mantém backup 0600 e nenhuma saída contém o valor do segredo.

## 9. Riscos

- **Mudança de pacote grande:** mover arquivos e reescrever imports de testes. Mitigação: um commit atômico de `git mv` mais substituição mecânica de imports, verificado pela suíte inteira antes e depois.
- **Plataformas que não tenho aqui:** macOS e Linux são verificados só no CI (matriz já existente); o serviço no macOS e no Linux é validado por geração de artefato, não por execução real do `launchd`/`systemd`. Isso será dito no guia.
- **Permissões no Windows:** 0600 não existe; `%APPDATA%` já é privado ao usuário e o doctor avisa se o diretório estiver fora do perfil.
- **Hooks já configurados** apontam para `python .../bridge/hook.py`: o caminho antigo deixa de existir. `setup-agents.ps1` e a documentação atualizam para `heycode hook`; o `doctor` detecta hook antigo e orienta.
