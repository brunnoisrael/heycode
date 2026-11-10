# Deploy da skill Alexa

Guia para o dono publicar a skill em modo desenvolvimento (so a sua conta) e ligar tudo a ponte local.
Nada aqui e feito automaticamente: exige o seu login na Amazon.

## 1. Subir a ponte e o tunel (no PC)

Em dois terminais PowerShell, na raiz do repositorio:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-bridge.ps1
powershell -ExecutionPolicy Bypass -File scripts\start-tunnel.ps1
```

- Na primeira execucao, `run-bridge.ps1` cria o `.env` (git-ignorado) com `BRIDGE_SECRET` (48 hex) e `BRIDGE_PIN` (4 digitos). Guarde os dois valores; nunca os commite.
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

Na aba **Code**, defina (Alexa-hosted: arquivo/seccao de variaveis de ambiente; na AWS Lambda propria: Configuration > Environment variables):

| Variavel | Valor |
|---|---|
| `BRIDGE_URL` | URL `https://...trycloudflare.com` do tunel (sem barra final) |
| `BRIDGE_SECRET` | o mesmo valor do `.env` |
| `ALLOWED_USER_ID` | seu userId da Alexa (ver abaixo) |
| `ALLOWED_DEVICE_ID` | deviceId do seu aparelho (ver abaixo) |

### Como descobrir os IDs

Com `ALLOWED_USER_ID` ainda **nao configurado**, a Lambda recusa qualquer pedido e registra no log os IDs vistos.

1. Deixe `ALLOWED_USER_ID` e `ALLOWED_DEVICE_ID` vazios e invoque a skill uma vez ("Alexa, abrir ponte claude" ou pela aba Test).
2. Aba **Code > CloudWatch logs** (ou Logs no console Alexa-hosted): procure a linha com `userId` e `deviceId`.
3. Copie os valores para `ALLOWED_USER_ID` e `ALLOWED_DEVICE_ID`, faca **Deploy** de novo e teste outra vez.

Depois disso, outro usuario ou dispositivo e recusado sem nenhuma chamada a ponte.

## 4. Ligar os hooks do Claude Code

1. Abra `~/.claude/settings.json` (Windows: `C:\Users\<voce>\.claude\settings.json`).
2. Mescle o bloco `hooks` de `bridge/claude-settings.example.json`. Ajuste o caminho do `hook.py` para onde o repositorio esta (o exemplo usa `~/claude-alexa-bridge/bridge/hook.py`).
3. Defina no ambiente do Claude Code (ou do sistema): `BRIDGE_SECRET` (mesmo valor do `.env`) e, se a ponte nao estiver em `http://127.0.0.1:8765`, `BRIDGE_URL`. O hook roda na mesma maquina da ponte, entao nao precisa do tunel.
4. Reinicie o Claude Code. Os hooks falham abertos: se a ponte estiver fora do ar, o agente segue normal.

## 5. Uso rapido por voz

- "Alexa, pergunte a ponte claude o status" / "o que esta pendente" / "qual o resultado".
- Aprovar: diga "aprovar" com o PIN; negar: "negar". O PIN vem do `.env` (`BRIDGE_PIN`).
- Modos: "modo manual", "modo automatico" (aprova tudo, sem PIN), "modo decisoes"; aviso de fim de ciclo: "avisar no fim do ciclo".

## Seguranca

- Todas as chamadas a ponte levam o header `x-secret`; sem ele, 401 (exceto `/health`).
- Comandos perigosos (rm, sudo, git push, deploy, etc.) nunca sao aprovados por voz nos modos manual e decisoes.
- O tunel rapido e publico enquanto estiver aberto: nao o deixe ligado sem necessidade e nao compartilhe a URL.
