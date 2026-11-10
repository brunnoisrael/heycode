# Spike: integração da ponte (MCP HTTP + aprovações + próxima instrução) com Codex e Aider

Data: 2026-11-09. Teste somente-leitura: apenas `--help`, `--version`, leitura de arquivos locais e documentação web. Nada foi instalado, nenhuma config alterada, nenhum agente foi executado de fato com um modelo. A única escrita fora deste relatório foi o schema JSON do app-server gerado no scratchpad temporário.

Versões: `codex-cli 0.155.1`; `aider 0.86.2`.

## Tabela comparativa

| Requisito da ponte | Codex 0.155.1 | Aider 0.86.2 |
|---|---|---|
| Cliente MCP | SIM, nativo. Streamable HTTP, stdio, bearer token, OAuth | NÃO. Nenhuma referência a "mcp" no código instalado; PR upstream aberto |
| Config MCP HTTP | `[mcp_servers.<nome>]` com `url = ...` em `~/.codex/config.toml` ou `codex mcp add <n> --url ...` | Não existe |
| Override por linha de comando (sem mexer na global) | SIM: `-c 'mcp_servers.bridge.url="..."'` (TOML dotted path), `--ignore-user-config`, `-p perfil` | N/A para MCP; opções gerais via flags/env `AIDER_*` |
| Políticas de aprovação | `-a on-request\|never` (flag da CLI interativa), `-s read-only\|workspace-write\|danger-full-access`, `--approve-for-me` | Só `--yes-always` (sim a tudo) ou perguntar no terminal. Sem sandbox |
| Hook externo allow/deny por requisição | SIM, de dois jeitos: (1) hook `PermissionRequest`/`PreToolUse` (command); (2) protocolo `codex app-server` com requests `item/commandExecution/requestApproval` etc. | NÃO. Só `--notifications-command` (aviso, sem decisão) |
| Headless | `codex exec "prompt" -C dir --json -o arq` | `aider --message "..."` ou `--message-file`, com `--yes-always` |
| Saída final estruturada | SIM: `--json` (JSONL de eventos), `-o` (última mensagem), `--output-schema` | NÃO há JSON. Texto no stdout + `.aider.chat.history.md` + `--llm-history-file` |
| Continuar com nova instrução | `codex exec resume <id>\|--last "prompt"`; também `codex queue`, `turn/steer` no app-server | Nova invocação com `--restore-chat-history` + `--chat-history-file` (reidrata histórico, sem sessão real) |
| Aderência à fase 3 | ALTA | BAIXA (só via wrapper/processo) |

## 1. Codex

### a) MCP

Evidência:

```
$ codex mcp --help      -> Commands: list get add remove login logout
$ codex mcp add --help  -> Usage: codex mcp add [OPTIONS] <NAME> (--url <URL> | -- <COMMAND>...)
      --url <URL>   URL for a streamable HTTP MCP server
      --bearer-token-env-var <ENV_VAR>
      --oauth-client-id / --oauth-resource ...
```

Sintaxe de config.toml (documentação oficial https://learn.chatgpt.com/docs/extend/mcp, antiga developers.openai.com/codex/mcp):

```toml
[mcp_servers.bridge]
url = "http://127.0.0.1:8765/mcp"
bearer_token_env_var = "BRIDGE_TOKEN"     # enviado como Authorization: Bearer
http_headers = { "X-Foo" = "bar" }
startup_timeout_sec = 20                  # default 10
enabled_tools = ["next_instruction"]      # allow list
```

Override sem tocar na config global (flag `-c`, valor parseado como TOML, caminho com pontos):

```
codex exec -c 'mcp_servers.bridge.url="http://127.0.0.1:8765/mcp"' \
           -c 'mcp_servers.bridge.bearer_token_env_var="BRIDGE_TOKEN"' "..."
```

Do `--help`: "Override a configuration value that would otherwise be loaded from `~/.codex/config.toml`. Use a dotted path (`foo.bar.baz`)". A existência da flag `-c` está confirmada; a forma exata `mcp_servers.<n>.url=` por `-c` decorre da regra de dotted path e NÃO foi testada em execução (e a página de docs não traz exemplo de `-c` para MCP). Alternativas confirmadas no help: `--ignore-user-config` ("Do not load `$CODEX_HOME/config.toml`; auth still uses `CODEX_HOME`") e `-p <perfil>` ("Layer `$CODEX_HOME/<name>.config.toml` on top of the base user config"); também dá para apontar `CODEX_HOME` para um diretório dedicado (não testado).

Estado local (`codex mcp list`): servidores já presentes são apenas internos do app (`codex_app`, `cua_repl`, `node_repl`). Nenhum servidor HTTP do usuário.

### b) Aprovação e interceptação

Config local atual (`~/.codex/config.toml`, só leitura): `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, `approvals_reviewer = "user"`, e `notify = [ "...codex-computer-use.exe", "turn-ended" ]`. Ou seja, hoje o Codex desta máquina não pede aprovação nenhuma; para a ponte decidir, é preciso sobrescrever com `-a on-request` e `-s workspace-write`/`read-only`.

CLI (`codex --help`):

```
-a, --ask-for-approval <APPROVAL_POLICY>
   - on-request: The model decides when to ask the user for approval
   - never:      Never ask for user approval Execution failures are immediately returned to the model
-s, --sandbox: read-only | workspace-write | danger-full-access
--approve-for-me   Route approval requests through automatic review using the workspace-write sandbox
```

Observações: o help desta versão lista só `on-request` e `never` (o `untrusted` do Codex antigo NÃO aparece; não confirmei se o config.toml ainda o aceita). `codex exec --help` NÃO tem `-a`; aceita `-s`, `--approve-for-me`, `--dangerously-bypass-approvals-and-sandbox`. Em exec a política vem do config (`-c approval_policy="on-request"`, plausível, não testado).

Mecanismos externos de decisão por requisição (todos confirmados na doc ou no schema, nenhum executado):

1. Hooks (feature `hooks` = stable/true em `codex features list`). Doc https://learn.chatgpt.com/docs/hooks:
   - Local: `~/.codex/hooks.json`, `~/.codex/config.toml`, `<repo>/.codex/hooks.json`, `<repo>/.codex/config.toml`.
   - Eventos: `SessionStart, SessionEnd, PreToolUse, PermissionRequest, PostToolUse, UserPromptSubmit, Stop, Interrupt` e outros.
   - `PermissionRequest` "runs when Codex is about to ask for approval"; o hook (tipo `command`) recebe JSON no stdin (`session_id, cwd, hook_event_name, tool_name, tool_input...`) e responde no stdout `{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"|"deny","message":"..."}}}`. Se nenhum hook decide, segue o fluxo normal. "Any deny wins".
   - `PreToolUse` pode barrar Bash, apply_patch, chamadas MCP (`permissionDecision: "deny"`, ou exit code 2). `"ask"` não é suportado.
   - Tipos de handler: só `command` e `mcp_tool`; não há handler HTTP. O hook `command` pode ser um script Python que faz POST/IPC para a ponte e devolve a decisão.
   - Hooks não-gerenciados exigem confiança prévia; existe `--dangerously-bypass-hook-trust` no `codex exec`. NÃO CONFIRMADO se hooks disparam em `codex exec` (a doc não menciona).
2. Protocolo `codex app-server` (experimental; `--listen stdio:// | unix:// | ws://IP:PORT`, com `--ws-auth`). Schema gerado com `codex app-server generate-json-schema`: o servidor envia ao cliente requests `item/commandExecution/requestApproval`, `item/fileChange/requestApproval`, `item/permissions/requestApproval` (campos: `command`, `cwd`, `reason`, `threadId`, `turnId`, `proposedExecpolicyAmendment`...). O cliente responde com `accept`, `acceptForSession`, `acceptWithExecpolicyAmendment`, recusa etc. Também há `thread/start`, `thread/resume`, `turn/start`, `turn/steer`. É o caminho "oficial" de ponte: a ponte vira o cliente (como o app/VSCode) e decide cada aprovação. Custo: protocolo JSON-RPC marcado como experimental e sujeito a mudança.
3. `notify` (config.toml): só notificação de fim de turno (`turn-ended`), sem poder de decisão.
4. Execpolicy `.rules` (existe `--ignore-rules`): regras estáticas, não decisão dinâmica. Não aprofundado.
5. Elicitação MCP (`tool_call_mcp_elicitation` = stable): servidores MCP podem pedir confirmação; também aparece `McpServerElicitationRequest` no schema do app-server. Não testado.

### c) Headless

```
codex exec -C <DIR> -s workspace-write --json -o <arquivo_ultima_msg> --skip-git-repo-check "prompt"
```

Flags confirmadas no `codex exec --help`: `-C/--cd <DIR>`, `--json` ("Print events to stdout as JSONL"), `-o/--output-last-message <FILE>`, `--output-schema <FILE>` (JSON Schema da resposta final), `--ephemeral` (não persiste sessão), `--skip-git-repo-check`, `--ignore-user-config`, `--ignore-rules`, `-m`, `-p`, `-c k=v`, `--add-dir`. Prompt por argumento ou stdin (`-`). Política de aprovação: não há `-a` no exec; usar `-s` e/ou `-c approval_policy=...` (não testado) ou hooks; em modo `never` falhas voltam ao modelo.

Esquema exato dos eventos JSONL (nomes de campos) NÃO foi verificado (não executei).

### d) Fim de ciclo e nova instrução

- `codex exec resume [SESSION_ID] [PROMPT]` com `--last` ("Resume the most recent recorded session") ou UUID/nome de thread; prompt `-` lê do stdin. Também existe `codex exec fork`.
- A ponte pega o `session_id`/thread id dos eventos `--json` (campo exato não confirmado) ou de `~/.codex/session_index.jsonl` / `~/.codex/sessions/` (existem localmente).
- `codex queue --thread <UUID|nome> --message <TEXT>` ("Queue a message for an existing session"): enfileira mensagem para sessão existente (semântica exata não verificada).
- Via app-server: `turn/start` e `turn/steer` na mesma thread, mantendo o processo vivo (melhor para loop contínuo).
- Também dá para o próprio agente puxar a "próxima instrução": a ponte expõe uma tool MCP (`next_instruction`) que bloqueia/retorna o texto do usuário. Funciona na prática só se o prompt inicial mandar o agente chamá-la em loop; depende do modelo, e de timeouts de tool MCP (não confirmado).

## 2. Aider

### a) MCP

Não suporta. Evidência: `aider --help` (520 linhas) não contém nenhuma opção com "mcp"; `grep -rli mcp` em `...\uv\tools\aider-chat\Lib\site-packages\aider\*.py` retornou vazio (o litellm embutido tem `experimental_mcp_client`, mas o aider não o usa). Web: PR upstream "Add MCP support" (#3672) e "Add MCP Support with LiteLLM" (#3937) aparecem como abertos/não mesclados no que consegui ver; não confirmei o estado atual (fonte não oficial). Existem wrappers de terceiros que expõem o Aider COMO servidor MCP (qduc/aider-mcp, disler/aider-mcp-server, sengokudaikon/aider-mcp-server), o que é o sentido inverso do desejado (o Aider seria a ferramenta, não o cliente). Não há arquivo de config nem flag de override para MCP. Config geral do Aider: `.aider.conf.yml` e env `AIDER_*` (padrão do próprio help).

### b) Aprovação

Não há política/sandbox. Só: perguntas interativas de confirmação (`confirm_ask` em `aider/io.py`), e `--yes-always` ("Always say yes to every confirmation"). No código, `self.yes` é tri-estado (True, False, None) mas a CLI só expõe `--yes-always`; não há flag para "sempre não". Comandos shell sugeridos pelo modelo (`--suggest-shell-commands`, default ligado) passam pela confirmação. Não há hook externo de decisão. O único callback é `--notifications-command COMMAND` ("a command to run for notifications instead of the terminal bell", quando a resposta do LLM está pronta): serve para avisar, não para decidir. Para a ponte interceptar aprovações teria que rodar o aider em PTY e responder y/n lendo o prompt (frágil), ou usar o aider como biblioteca Python e subclassar `InputOutput.confirm_ask` (não testado; API não estável oficialmente, mas o código está instalado localmente).

### c) Headless

```
cd <DIR> && aider --message "prompt" --yes-always --no-pretty --no-stream --no-auto-commits --no-check-update --no-analytics --chat-history-file <arq> --llm-history-file <arq2> [--model X] [--file a.py]
```

Confirmado no help: `--message/-m` ("send the LLM, process reply then exit"), `--message-file/-f`, `--yes-always`, `--no-pretty`, `--no-stream`, `--auto-commits/--no-auto-commits`, `--file`, `--read`, `--chat-history-file` (default `.aider.chat.history.md`), `--llm-history-file`, `--exit`. Não existe saída JSON. A "saída final" é o stdout (texto) e o markdown do histórico. Precisa de chave de API/modelo configurados (`--api-key`, `--set-env`, `--model`); não verifiquei se há chave configurada nesta máquina (não há `~/.aider*`). Diretório: não há flag `-C`; usar o cwd do processo (ou `--file` com caminhos).

### d) Fim de ciclo e nova instrução

Sem sessão persistente em processo. Para continuar: nova invocação de `aider --message "<nova instrução>" --restore-chat-history --chat-history-file <mesmo arquivo>` (`--restore-chat-history`: "Restore the previous chat history messages (default: False)"), o que reidrata o contexto a partir do markdown (reconstrução aproximada, e limitada por `--max-chat-history-tokens`). Alternativa: `--load <arquivo>` executa comandos `/` na inicialização. Alternativa interativa: manter aider em PTY e escrever a próxima instrução no stdin; frágil. Não testado.

## Recomendação final

### Codex: suporta de verdade (confirmado pela documentação e help; não executado)
- Cliente MCP streamable HTTP com bearer token: sim. Ponte MCP HTTP em `127.0.0.1` funciona, registrada via `-c` ou `codex mcp add` (este último escreve em `~/.codex/config.toml`, evitar).
- Decisão de aprovação por requisição: sim, via hook `PermissionRequest` (script `command` chamando a ponte) ou via `codex app-server` (JSON-RPC, a ponte responde `accept`/recusa).
- Headless com JSON e continuação: `codex exec --json -o` + `codex exec resume`.

### Aider: o que realmente tem
- Execução headless por `--message` e histórico em arquivo. Nada de MCP, nada de hook de aprovação, nada de JSON.

### Mínimo aceitável para a fase 3
1. Alvo principal: Codex. Implementar a ponte MCP HTTP (tool `next_instruction`/`report_result`) e invocar `codex exec -C <dir> -s workspace-write --json -o <f> -c 'mcp_servers.bridge.url="..."' "prompt"`; guardar o id da sessão e usar `codex exec resume <id> "<nova instrução>"` a cada ciclo. Passar `-c approval_policy="on-request"` (a config do usuário está em `never`) ou `--ignore-user-config`.
2. Aprovação por requisição como segunda etapa: hook `PermissionRequest` command (script Python) que consulta a ponte; ou migrar para `codex app-server` se quiser decidir/relayar aprovações em tempo real (ex.: pela voz/Alexa). Se isso atrasar, aceitável na fase 3: `-s workspace-write` + política fixa, sem decisão dinâmica.
3. Aider: fora do escopo da fase 3 como agente "completo". Se for incluído, só no modo degradado: `--message` + `--yes-always` + `--restore-chat-history`, sem MCP e sem aprovação por requisição (o risco de `--yes-always` precisa ser aceito explicitamente, sem sandbox).

## O que NÃO consegui confirmar

- Nenhum comando de agente foi executado com modelo; todo comportamento de runtime (JSONL, resume, hooks, app-server) é inferido de help, schema e docs.
- Que `-c 'mcp_servers.<n>.url=...'` funciona de fato por linha de comando (decorre da regra de dotted path; a doc não dá exemplo).
- Se hooks (inclusive `PermissionRequest`) disparam em `codex exec` e se exigem `--dangerously-bypass-hook-trust` ou confiança persistida.
- Se `approval_policy="untrusted"` ainda é aceito no config.toml da 0.155.1 (o help lista só `on-request` e `never`) e como passar a política no `exec` (sem `-a`).
- Nomes exatos dos campos/eventos do `--json` (inclusive onde vem o id da sessão) e semântica de `codex queue`.
- Se o Codex envia `Authorization` para servidor HTTP em `127.0.0.1` sem TLS e como lida com `startup_timeout_sec` em tools MCP bloqueantes.
- Estado atual do suporte a MCP no Aider upstream (só fontes secundárias da web); chaves/modelo do Aider configurados nesta máquina; comportamento real de `--restore-chat-history` em `--message`.
- Estabilidade do protocolo `app-server` (marcado experimental).
