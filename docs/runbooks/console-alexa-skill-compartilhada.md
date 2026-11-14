# Skill compartilhada no console da Alexa: o que está configurado e as armadilhas

Estado em 2026-11-14. Complementa `docs/runbooks/beta-fechado.md`. Tudo foi feito pelo navegador (Playwright), com o login feito pelo dono; nada foi enviado para certificação nem publicado.

## O que está configurado

| Item | Valor |
|---|---|
| Skill | **HeyCode**, tipo Custom, pt-BR, "Provision your own", em desenvolvimento |
| Skill ID | `amzn1.ask.skill.fc482e95-ab16-4ba8-8539-c1ff52c48222` (é o `ALEXA_SKILL_ID` do relay) |
| Invocação | `hey code` (duas palavras; nome de uma palavra tem regras mais rígidas na Amazon) |
| Modelo | `skill/interaction-model-pt-BR.json` (23 intents, inclui `RunCommandIntent`), construído sem erros; 2 avisos herdados do modelo do dono (slots só no diálogo) |
| Endpoint | HTTPS `https://staging-api.heycode.dev.br/v1/alexa`, "certificado de autoridade confiável" |
| Account linking | Auth Code Grant; autorização `https://staging-api.heycode.dev.br/oauth/authorize`; token `https://staging-api.heycode.dev.br/oauth/token`; Client ID `heycode-alexa`; segredo igual ao `OAUTH_CLIENT_SECRET` do servidor; HTTP Basic; expiração 3600 s; PKCE desligado |
| Redirect URLs (a Amazon mostra) | `https://pitangui.amazon.com/api/skill/link/<vendorId>`, `https://layla.amazon.com/api/skill/link/<vendorId>`, `https://alexa.amazon.co.jp/api/skill/link/<vendorId>` (ficam em `OAUTH_REDIRECT_URIS`) |
| Teste | ligado em **Development** (vale para os dispositivos da conta de desenvolvedor) |

O `vendorId` não é segredo; o segredo do cliente nunca entra em arquivo do repositório.

## Verificação feita

No simulador, "abrir hey code" gerou um pedido assinado pela Amazon; o relay validou certificado, cadeia, assinatura, janela de tempo e `applicationId` e respondeu `LinkAccount` ("vincule sua conta no aplicativo da Alexa"). É o primeiro teste da verificação contra a Amazon de verdade.

## Armadilhas (para quem repetir)

1. **Não salve a página Endpoint do assistente padrão.** A skill nova vem com um ARN de exemplo de **outra conta da AWS**; troque para HTTPS antes de salvar.
2. **O arquivo do modelo é UTF-8.** Lê-lo como cp1252 produz mojibake ("estÃ¡"), e o console aceita e constrói assim mesmo. Gere o JSON com `json.load(..., encoding="utf-8")` e confira acentos no editor antes de salvar. (Uma nota antiga dizia cp1252: estava errada; teste `test_acentos_do_modelo_ficaram_intactos_em_utf8`.)
3. Importar o modelo: **JSON Editor** → campo de upload (`input[type=file]`) → conferir o texto no editor (`ace`) → Save → **Build skill**. O build pode demorar mais que 2 minutos.
4. O interruptor "Do you allow users to create an account or link..." precisa ser **clicado de verdade** (clique de mouse); disparar `click()` no DOM marca o `input` mas não atualiza a tela, e os campos continuam desabilitados.
5. Depois de salvar o account linking, o console liga sozinho "Allow users to enable skill without account linking": está bem, o relay responde `LinkAccount` a quem ainda não vinculou.
6. Janelas "Rate this page" e "Welcome" aparecem sem avisar e interceptam cliques: feche-as antes (sem enviar feedback).
7. O console mostra o conteúdo dentro de iframes em várias telas (Oracle) e usa componentes próprios (combobox, toggles): localize por texto e por coordenadas quando o rótulo não estiver associado ao campo.

## Ferramentas (neste repositório)

`scripts/ops/` tem o que foi usado: `browser_host.py` (Chromium visível com perfil persistente e porta de depuração só em 127.0.0.1, para o dono logar), `oracle_retry_create.py` (repete a criação da VM) e `alexa_fill_account_linking.py` (preenche o account linking lendo o segredo do servidor sem imprimi-lo). **Feche o Chromium ao terminar**: enquanto a porta de depuração está aberta, qualquer programa local controla a sessão logada.

## Próximos passos

1. Criar a conta no painel (`https://staging-app.heycode.dev.br/app`), parear um computador (`heycode pair CÓDIGO --relay https://staging-api.heycode.dev.br` e `heycode connect`).
2. No aplicativo da Alexa, vincular a conta da skill HeyCode; autorizar o dispositivo no painel; testar por voz.
3. Reenviar o modelo ao console sempre que ele mudar no repositório (JSON Editor → Save → Build).
