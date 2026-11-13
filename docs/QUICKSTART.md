# Início rápido: do zero ao primeiro status

Meta: instalar, configurar, iniciar e diagnosticar a ponte local só com o CLI `heycode`, em menos de 10 minutos. Vale para Windows, macOS e Linux (Python 3.11 a 3.14).

## 1. Instalar

```bash
pipx install heycode          # quando publicado no PyPI
# ou, a partir de um clone deste repositório:
pipx install .                # alternativa: python -m pip install .
heycode --version
```

## 2. Criar a configuração

```bash
heycode init
```

Cria o diretório do usuário (`%APPDATA%\heycode`, `~/Library/Application Support/heycode` ou `~/.local/share/heycode`; mude com `HEYCODE_HOME`) com `config.env`, que guarda **dois segredos** distintos (agente e controle) e um PIN de 6 dígitos, gerados aleatoriamente. Nunca sobrescreve o que existe e nunca imprime os valores.

Vinha rodando a ponte direto do clone antigo? Traga o estado sem apagar nada:

```bash
heycode init --import-legacy /caminho/do/clone
```

## 3. Iniciar a ponte

```bash
heycode serve                 # em primeiro plano, porta 8765
heycode install-service       # mostra o que faria (dry-run)
heycode install-service --apply   # deixa em segundo plano, no seu usuário, sem administrador
```

O serviço usa Tarefa Agendada (Windows), LaunchAgent (macOS) ou `systemd --user` (Linux). Remover: `heycode uninstall-service --apply`.

## 4. Ligar os agentes

- **Claude Code:** mescle o bloco `hooks` de [`claude-settings.example.json`](claude-settings.example.json) em `~/.claude/settings.json`. Os comandos são `heycode hook` e `heycode hook approve`; falham abertos, então se a ponte estiver fora do ar o agente segue normal.
- **MCP (Claude Code e Codex):** registre `http://127.0.0.1:8765/mcp` com o segredo de **agente** (`BRIDGE_SECRET`); no Windows, `scripts\setup-agents.ps1` faz isso.
- **Alexa:** veja [DEPLOY-ALEXA.md](DEPLOY-ALEXA.md) (skill, Lambda e túnel). A Lambda usa o segredo de **controle**.

## 5. Conferir

```bash
heycode doctor
```

Mostra, por camada (ambiente, configuração, ponte, autenticação, agentes, rede externa e Alexa), o que está certo e o que fazer quando não está. Sai com código 1 se houver falha; `--json` para ferramentas. A camada da Alexa é sempre um aviso, porque só dá para testar no simulador do console e no Echo.

## Referência dos comandos

| Comando | O que faz |
|---|---|
| `heycode init` | Cria diretório e segredos; `--import-legacy DIR` importa o estado antigo |
| `heycode serve` | Sobe a ponte (`--host`, `--port`) |
| `heycode hook` | Ponto de entrada dos hooks dos agentes (`approve`, `--agent`) |
| `heycode install-service` | Instala o serviço (`--apply` para executar) |
| `heycode uninstall-service` | Remove o serviço (`--apply` para executar) |
| `heycode rotate-secret` | Troca o segredo com backup (`--apply`; `--control` para o de controle) |
| `heycode doctor` | Diagnóstico por camada (`--json`) |

Problemas? Veja [OPERATIONS.md](OPERATIONS.md).
