# Deploy da skill Alexa

Guia para o dono publicar a skill em modo desenvolvimento (so a sua conta) e ligar tudo a ponte local.
Nada aqui e feito automaticamente: exige o seu login na Amazon.

## Instalacao HeyCode nesta maquina (2026-11-13)

- Dominio: `heycode.dev.br`, com DNS delegado ao Cloudflare. O endpoint de controle da ponte e `https://ponte.heycode.dev.br`.
- Tunel nomeado `roomcode`, configurado localmente em `%USERPROFILE%\.cloudflared\config.yml`; os arquivos dessa pasta incluem credenciais e nao devem ser compartilhados ou versionados.
- As tarefas `RoomCodeBridge` e `RoomCodeTunnel` iniciam no logon do usuario Windows, com reinicio em caso de falha. Isso nao garante disponibilidade antes do logon nem com o PC desligado.
- A Lambda da skill em desenvolvimento recebeu o endpoint fixo. Para inspecionar a infraestrutura sem exibir credenciais: `powershell -ExecutionPolicy Bypass -File scripts/diagnose-connection.ps1 -Hostname ponte.heycode.dev.br`.
- Verificado em 2026-11-13: ponte local, conexao externa `/health`, recusa sem segredo e chamada autenticada pelo endereco fixo. O modelo com listagem de projetos foi construido, a Lambda implantada em desenvolvimento e um pedido de listagem enviado pelo simulador com os IDs autorizados retornou fala sem erro. Falta confirmar o fluxo pelo Echo depois desta troca de endereco e apos reiniciar o computador.
- O tunel rapido anterior pode permanecer aberto durante a transicao, mas nao e necessario depois de validar o endereco fixo. Nao altere o DNS ou as credenciais em caso de falha sem antes executar o diagnostico.

## 1. Subir a ponte e o tunel (no PC)

Em dois terminais PowerShell, na raiz do repositorio:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-bridge.ps1
powershell -ExecutionPolicy Bypass -File scripts\start-tunnel.ps1
```

- Na primeira execucao, `run-bridge.ps1` cria o `.env` (git-ignorado) com **dois segredos** de 48 hex, `BRIDGE_SECRET` (segredo de **agente**: hooks e MCP) e `BRIDGE_CONTROL_SECRET` (segredo de **controle**: so a Lambda), mais `BRIDGE_PIN` (4 digitos). Guarde os tres valores; nunca os commite. A ponte nao inicia se um segredo tiver menos de 32 caracteres ou se os dois forem iguais.
- A ponte escuta em `127.0.0.1:8765` (use `$env:BRIDGE_PORT` para outra porta nos dois scripts).
- O tunel imprime uma URL `https://<nome>.trycloudflare.com`. Essa e a sua `BRIDGE_URL`. Ela **muda a cada execucao** do tunel (tunel rapido, sem conta); ao reiniciar, atualize a variavel na Lambda.
- Teste: `curl <url>/health` deve responder `{"ok":true}` e `curl <url>/status` sem header deve dar 401.
- O `cloudflared` instala com `winget install --id Cloudflare.cloudflared -e`. Se nao estiver no PATH, o script usa `C:\Program Files (x86)\cloudflared\cloudflared.exe`.

## 2. Criar a skill no Alexa Developer Console

1. Entre em https://developer.amazon.com/alexa/console/ask com a conta Amazon da sua Alexa.
2. **Create Skill**: nome (ex.: "Ponte Claude"), idioma **Portuguese (BR)**, modelo **Custom**, hosting **Alexa-hosted (Node.js)** (a Lambda e criada para voce).
3. Aba **Build > JSON Editor**: cole o conteudo de `skill/interaction-model-pt-BR.json` e clique em **Save** e **Build Model**.
4. Aba **Code**: substitua `index.js` por `skill/lambda/index.js` e `package.json` por `skill/lambda/package.json`. Clique em **Deploy**.
5. Aba **Test**: ative **Development** para testar por texto ou voz.

## 3. Variaveis de ambiente da Lambda

A skill Alexa-hosted **nao tem tela de variaveis de ambiente**. Nela, os valores vao num arquivo `env.json` ao lado do `index.js`:

1. Aba **Code > New File**, caminho `lambda/env.json`.
2. Conteudo: um objeto JSON com as variaveis da tabela abaixo, por exemplo `{ "BRIDGE_URL": "https://...", "BRIDGE_CONTROL_SECRET": "...", "ALLOWED_SKILL_ID": "...", "ALLOWED_USER_ID": "", "ALLOWED_DEVICE_ID": "" }`.
3. **Save** com o `env.json` aberto, depois **Deploy**.

O `env.json` existe so no editor da skill; `skill/lambda/env.json` esta no `.gitignore` e nunca vai para o repositorio. Valor vazio e ignorado, e variavel de ambiente de verdade vence o arquivo. Na AWS Lambda propria, use Configuration > Environment variables e dispense o arquivo.

A Alexa-hosted roda em Node 16, sem `fetch` global; o `index.js` usa `https` nativo nesse caso, entao nao e preciso instalar nada.

| Variavel | Valor |
|---|---|
| `BRIDGE_URL` | URL `https://...trycloudflare.com` do tunel (sem barra final) |
| `BRIDGE_CONTROL_SECRET` | o valor de `BRIDGE_CONTROL_SECRET` do `.env` (segredo de controle). **A Lambda NAO deve receber o `BRIDGE_SECRET` de agente**: se ela o tivesse, a separacao de segredos perderia o sentido |
| `ALLOWED_USER_ID` | seu userId da Alexa (ver abaixo) |
| `ALLOWED_DEVICE_ID` | deviceId do seu aparelho (ver abaixo) |
| `ALLOWED_SKILL_ID` | applicationId da sua skill (ver abaixo); com ele definido, outra skill e recusada sem chamar a ponte |

### Como descobrir os IDs

Com `ALLOWED_USER_ID` ainda **nao configurado**, a Lambda recusa qualquer pedido e registra no log os IDs vistos.

1. Deixe `ALLOWED_USER_ID` e `ALLOWED_DEVICE_ID` vazios e invoque a skill uma vez ("Alexa, abrir ponte claude" ou pela aba Test).
2. Aba **Code > CloudWatch logs** (ou Logs no console Alexa-hosted): procure a linha com `userId` e `deviceId`.
3. Copie os valores para `ALLOWED_USER_ID` e `ALLOWED_DEVICE_ID`, faca **Deploy** de novo e teste outra vez.

O `applicationId` (formato `amzn1.ask.skill.<uuid>`) aparece no mesmo log, em `session.application.applicationId`, e tambem no Alexa Developer Console (aba **Build > Endpoint** ou **Distribution**, campo "Skill ID"). Copie para `ALLOWED_SKILL_ID`.

Depois disso, outro usuario ou dispositivo e recusado sem nenhuma chamada a ponte.

**O simulador da aba Test tem um `deviceId` proprio**, diferente do seu Echo, e so cabe um `ALLOWED_DEVICE_ID`. Com o ID do simulador, o Echo recebe "Acesso negado"; com o ID do Echo, o simulador recebe. Para pegar o do Echo, fale "Alexa, abrir meu agente" no aparelho e procure no CloudWatch a linha `ACESSO NEGADO. userId=... deviceId=...`.

> **Reimporte o modelo de interacao.** Os intents novos (cancelar agente, avisar o agente aberto, projeto no ditado) so existem depois de colar de novo `skill/interaction-model-pt-BR.json` em **Build > JSON Editor**, **Save** e **Build Model**, e de fazer **Deploy** do novo `index.js`. Sem isso a Alexa nao reconhece as frases novas.

## 4. Ligar os hooks do Claude Code

1. Abra `~/.claude/settings.json` (Windows: `C:\Users\<voce>\.claude\settings.json`).
2. Mescle o bloco `hooks` de `bridge/claude-settings.example.json`. Ajuste o caminho do `hook.py` para onde o repositorio esta (o exemplo usa `~/claude-alexa-bridge/bridge/hook.py`).
3. Defina no ambiente do Claude Code (ou do sistema): `BRIDGE_SECRET` (segredo de **agente**, valor de `BRIDGE_SECRET` no `.env`; o `BRIDGE_CONTROL_SECRET` nunca vai para o ambiente do agente) e, se a ponte nao estiver em `http://127.0.0.1:8765`, `BRIDGE_URL`. O hook roda na mesma maquina da ponte, entao nao precisa do tunel.
4. Reinicie o Claude Code. Os hooks falham abertos: se a ponte estiver fora do ar, o agente segue normal.

## 5. Uso rapido por voz

- "Alexa, pergunte a ponte claude o status" / "o que esta pendente" / "qual o resultado".
- Aprovar: diga "aprovar" com o PIN; negar: "negar". O PIN vem do `.env` (`BRIDGE_PIN`).
- Cancelar: "cancela o agente" / "para o agente" interrompe a execucao mais recente em andamento ("Cancelei o agente claude." ou "Nenhum agente rodando.").
- Avisar o agente aberto: "avise o agente aberto <instrucao>" (mesma releitura e "confirma" do ditado; entra na fila do Claude Code aberto).
- Ditado em dois turnos: diga "peca ao claude" (ou "manda o codex", "diz pro aider"); a Alexa pergunta "Qual e a instrucao para o claude?"; diga a instrucao; ela rele e pede "confirma". A Alexa nao aceita o agente e a instrucao livre na mesma frase.
- Projeto no ditado: "peca ao codex no projeto <nome>", e a instrucao no turno seguinte. Projeto que nao existe em `PROJECTS_ROOT` responde "Nao achei o projeto <nome>." e nada roda.
- Criar projeto: "crie o projeto <nome> com o claude"; a Alexa pergunta "Para que serve o projeto <nome>?"; diga a descricao e depois "confirma".
- Modos: "modo manual", "modo automatico" (aprova tudo, sem PIN), "modo decisoes"; aviso de fim de ciclo: "avisar no fim do ciclo".

## 6. Ponte como servico fixo (tarefa agendada)

Em vez de abrir o `run-bridge.ps1` na mao, instale a tarefa `RoomCodeBridge` (ao logon, janela oculta, reinicia em falha):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-service.ps1 -DryRun            # so mostra
powershell -ExecutionPolicy Bypass -File scripts\install-service.ps1 -ReplaceExisting   # instala
powershell -ExecutionPolicy Bypass -File scripts\uninstall-service.ps1                  # remove
```

- E idempotente: recria a tarefa se ela existir.
- `-ReplaceExisting` encerra quem escuta na porta da ponte **somente** se a linha de comando contiver `server:app`; qualquer outro processo na porta nao e tocado (apenas aviso).
- Teste de fumaca (porta livre, banco e segredo descartaveis, nao mexe no `.env`): `powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1`.

## 7. Tunel nomeado (URL estavel)

O tunel rapido muda de URL a cada execucao. Para um hostname estavel, o dominio precisa estar ativo e delegado na conta Cloudflare do dono. A solicitacao de `heycode.dev.br` nao comprova que ele ja foi registrado ou delegado. Confirme isso no Registro.br e no painel Cloudflare antes de mudar o DNS. A ponte continua escutando somente em loopback.

1. Revise o roteiro (a previa e o padrao; nenhum recurso e criado):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-named-tunnel.ps1 -Hostname ponte.heycode.dev.br
```

2. Depois de conferir o dominio e o destino `http://127.0.0.1:8765`, faca `cloudflared tunnel login` na conta correta e, se o certificado local estiver disponivel, execute o mesmo comando com `-Apply`. Ele cria tunel e DNS apenas quando nao existe configuracao local nem tunel com o mesmo nome. Se houver falha parcial, revise o estado no painel antes de tentar novamente. Se o tunel for gerenciado remotamente ou ja existir, configure-o pelo processo apropriado da Cloudflare e revise o arquivo de configuracao antes de prosseguir; nao substitua o que ja existe.
3. Para um tunel com arquivo YAML e credenciais locais ja provisionados, apresente a previa e instale a tarefa de logon do usuario:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-tunnel-task.ps1 -ConfigPath "$env:USERPROFILE\.cloudflared\config.yml"
powershell -ExecutionPolicy Bypass -File scripts\install-tunnel-task.ps1 -ConfigPath "$env:USERPROFILE\.cloudflared\config.yml" -Apply
powershell -ExecutionPolicy Bypass -File scripts\diagnose-connection.ps1 -Hostname ponte.heycode.dev.br
```

A tarefa `RoomCodeTunnel` reinicia em falha e nao modifica uma tarefa com outra acao. O arquivo indicado deve conter somente o hostname e o destino revisados; proteja as credenciais locais do tunel. O diagnostico verifica a ponte local, o estado da tarefa, `/health` externo e a recusa de `/status` sem credencial. Para testar `/status` autenticado, defina `BRIDGE_CONTROL_SECRET` no ambiente da sessao e acrescente `-Authenticate`; nunca cole o segredo em argumentos ou logs. O diagnostico nao comprova a Alexa.

4. Depois de confirmar saude externa e autorizacao, ajuste `BRIDGE_URL` na Lambda uma unica vez e faca deploy. Teste com o Echo autorizado; apos reinicio e logon, repita o teste sem atualizar a Lambda. O arquivo `env.json` da skill continua com usuario, dispositivo e segredo de controle existentes.

Para retornar ao tunel rapido, reponha na Lambda sua URL ainda ativa e faca deploy antes de encerrar a tarefa `RoomCodeTunnel`. Nao remova DNS, tunel ou arquivos de credenciais de terceiros. A tarefa e por usuario e depende do logon; a reconexao do conector nao significa que a Alexa esteja funcionando.

## 8. Rotacao do segredo

```powershell
powershell -ExecutionPolicy Bypass -File scripts\rotate-secret.ps1 -DryRun
powershell -ExecutionPolicy Bypass -File scripts\rotate-secret.ps1
```

Gera novo segredo no `.env` (`-Which agent|control|both`, padrao `both`) (com backup `.env.bak-<data>`, que guarda o segredo antigo: apague-o), reinicia a tarefa e lista o que atualizar: Lambda (`BRIDGE_CONTROL_SECRET` + Deploy, se o de controle mudou), hooks/ambiente do Claude Code e do Codex e o registro MCP (`BRIDGE_SECRET`, se o de agente mudou) (`scripts\setup-agents.ps1`).

## Seguranca

- Todas as chamadas a ponte levam o header `x-secret`; sem ele, 401 (exceto `/health`). Cada rota aceita so o seu segredo: o de agente vale em `/event`, `/approval`, `/instruction/next` e `/mcp`; o de controle vale em todas as demais. O segredo de agente recebe 401 em `/mode`, entao um agente comprometido nao liga o modo auto sozinho.
- O estado do fim de ciclo, o resumo da sessao e a trava de PIN ficam no SQLite e sobrevivem a reinicio da ponte.
- Comandos perigosos (rm, sudo, git push, deploy, etc.) nunca sao aprovados por voz nos modos manual e decisoes.
- O tunel rapido e publico enquanto estiver aberto: nao o deixe ligado sem necessidade e nao compartilhe a URL.

## 9. Aviso proativo (a Alexa falando sozinha)

Skills custom da Alexa não iniciam conversa. Para o aviso espontâneo ("o agente terminou"), a ponte avisa por dois canais opcionais, sempre com segredos mascarados:

- **ntfy** (push no celular): defina `NTFY_TOPIC` com um nome difícil de adivinhar.
- **Webhook** (voz na sala via Home Assistant): defina `HA_WEBHOOK_URL`. A ponte faz `POST` com `{"title": "...", "message": "..."}` a cada evento que precisa de você (agente aguardando, aprovação por voz, fim de execução).

Exemplo de automação no Home Assistant, com o Alexa Media Player instalado:

```yaml
automation:
  - alias: RoomCode avisa na Alexa
    trigger:
      - platform: webhook
        webhook_id: roomcode
        local_only: true
    action:
      - service: notify.alexa_media_sala
        data:
          message: "{{ trigger.json.message }}"
          data:
            type: announce
```

Depois aponte `HA_WEBHOOK_URL` para `http://<seu-home-assistant>:8123/api/webhook/roomcode`. Falha no webhook nunca derruba a ponte.
