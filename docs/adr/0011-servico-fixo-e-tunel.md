# 0011. Serviço fixo, túnel nomeado e rotação de segredo

## Status

Aceito. Data: 2026-11-09.

## Contexto

Até a fase 5 a ponte subia à mão (`run-bridge.ps1`) e o túnel rápido do Cloudflare mudava de URL a cada execução, obrigando a editar a Lambda sempre. A fase 6 pede operação estável e endurecimento. Spec: `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (§9 fase 6, §10). O login na conta Cloudflare e na Alexa pertence ao dono e não pode ser automatizado.

## Decisão

- A ponte roda como tarefa agendada `RoomCodeBridge` (ao logon do usuário, janela oculta, reinício em falha, uma instância), criada por `scripts/install-service.ps1` e removida por `uninstall-service.ps1`. O script é idempotente (recria a tarefa). `-ReplaceExisting` só encerra o processo da porta se a linha de comando contiver `server:app`, para não derrubar um processo alheio nem deixar duas pontes disputando a porta. `-DryRun` existe em todos os scripts mutáveis.
- O túnel nomeado do `cloudflared` é apenas roteirizado (`setup-named-tunnel.ps1`): passos interativos (login, serviço com administrador) imprimem o comando e pausam; o script nunca guarda nem burla credenciais.
- `rotate-secret.ps1` gera novo `BRIDGE_SECRET` com backup do `.env`, reinicia a tarefa e lista o que atualizar (Lambda, hooks, MCP). Em `-DryRun` não escreve nada nem imprime o segredo.
- `smoke.ps1` sobe a ponte numa porta livre com banco temporário e segredo descartável, verifica `/health`, 401 sem header, `/mcp` 401 sem e 200 com credencial, `POST /mode`, e encerra apenas o processo que iniciou.
- A Lambda recebe `ALLOWED_SKILL_ID` como terceiro filtro, documentado em `docs/DEPLOY-ALEXA.md`.
- Alternativas rejeitadas: serviço do Windows via NSSM ou similar (dependência extra, exige administrador); tarefa ao boot (roda fora da sessão do usuário, sem acesso a `claude`/`codex` no PATH e ao perfil); automatizar o login Cloudflare (credenciais do dono fora do escopo).

## Consequências

- A ponte volta sozinha após logon ou falha, e a URL do túnel nomeado passa a ser fixa depois de um ajuste único na Lambda.
- A tarefa roda só com o usuário logado; sem logon, a ponte não sobe (aceito: os agentes também dependem da sessão).
- Rotar o segredo exige atualizar manualmente a Lambda e os agentes; o backup do `.env` guarda o segredo antigo e deve ser apagado.
- O smoke não cobre a Lambda nem o túnel, apenas a ponte local.
