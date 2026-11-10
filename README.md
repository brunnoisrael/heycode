# 🎙️ claude-alexa-bridge

Pergunte à Alexa o que o seu **Claude Code** está fazendo, ouça quando ele precisar de você e **aprove comandos por voz** (com PIN).

```
Claude Code ──hooks──▶ Ponte local (FastAPI) ◀──túnel HTTPS── Skill Alexa (Lambda)
                              │
                              └──▶ push no celular (ntfy.sh)
```

## Exemplos
- "Alexa, pergunte ao meu agente qual o status" → *"No projeto meu-app, o agente está trabalhando, rodando o comando pytest."*
- "Alexa, peça ao meu agente o resumo" → lê a última resposta do Claude.
- "Alexa, pergunte ao meu agente se tem algo pendente" → *"O agente quer rodar: npm test. Diga aprovar com o seu PIN, ou negar."*
- "Aprovar com o PIN 1234" → o hook `PermissionRequest` libera o comando.

## Segurança (leia antes de usar)
- Todos os endpoints exigem o header `x-secret`. **Nunca** exponha o servidor sem ele.
- Aprovação por voz exige `BRIDGE_PIN`. Sem PIN, a função fica desligada. 3 erros bloqueiam por 5 min.
- Só comandos `Bash` podem ser aprovados por voz, e nunca os destrutivos (`rm`, `sudo`, `git push`, `--force`, deploy, `curl | sh`...; veja `NEVER_BY_VOICE`). Esses caem no prompt normal.
- Sem resposta em 40 s, o Claude Code mostra o prompt normal (ou você responde pelo Remote Control no celular).
- A Alexa só lê a primeira palavra dos comandos no status, para não vazar segredos. Ao pedir aprovação, lê o comando para você saber o que está liberando.
- Um PIN falado pode ser ouvido por quem está na sala. Use por sua conta e risco.
- Considere Cloudflare Access no túnel e restrinja a Lambda ao seu Skill ID.

## Instalação

### 1. Ponte local
```bash
cd bridge && pip install -r requirements.txt
export BRIDGE_SECRET="$(openssl rand -hex 24)"   # guarde este valor
export BRIDGE_PIN="1234"                          # troque
export NTFY_TOPIC="um-nome-dificil-de-adivinhar"  # opcional
uvicorn server:app --host 127.0.0.1 --port 8765
```

### 2. Hooks do Claude Code
Copie o conteúdo de `bridge/claude-settings.example.json` para `~/.claude/settings.json` (ajuste o caminho e use `python` no Windows). Exporte `BRIDGE_SECRET` no mesmo terminal em que roda o `claude`. Confira com `/hooks` dentro do Claude Code.

### 3. Túnel HTTPS
```bash
cloudflared tunnel --url http://127.0.0.1:8765   # teste rápido
```
Para uso contínuo, crie um túnel nomeado ou use Tailscale Funnel.

### 4. Skill Alexa
1. No [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask): *Create Skill* → pt-BR → Custom → Alexa-hosted (Node.js).
2. Aba *Build* → *JSON Editor*: cole `skill/interaction-model-pt-BR.json` → *Save* e *Build*.
3. Aba *Code*: cole `skill/lambda/index.js`, adicione as dependências do `package.json` e defina `BRIDGE_URL` (URL do túnel) e `BRIDGE_SECRET`.
4. *Deploy* → aba *Test* → "abrir meu agente".

A skill em modo de desenvolvimento funciona na sua conta sem certificação.

### Aviso proativo
Skills custom não falam sozinhas. Combine com `NTFY_TOPIC` (push no celular) e, se quiser voz espontânea, Home Assistant + Alexa Media Player ou uma Rotina disparada por sensor virtual.

## Ideias de evolução
- Multi-sessão ("status do projeto X")
- Modo "não perturbe"
- Migrar para o Claude Agent SDK para callbacks de permissão nativos
