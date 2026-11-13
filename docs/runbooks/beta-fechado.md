# Roteiro do beta fechado da skill compartilhada

Pré-requisitos **do dono** (nada disso é feito por agente): conta de desenvolvedor Amazon (com administrador adicional, se a Amazon permitir), nome de invocação validado pela Amazon e checagem de marca, relay em staging no ar com TLS e e-mails do domínio ativos, documentos de `docs/legal/` revisados e publicados em URL pública, e as variáveis `ALEXA_SKILL_ID`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OAUTH_REDIRECT_URIS` configuradas no relay.

## Configurar a skill no console da Amazon

1. Endpoint: HTTPS em `https://staging-api.heycode.dev.br/v1/alexa`, com certificado de domínio confiável.
2. Account linking: Authorization Code Grant; URI de autorização `https://staging-app.heycode.dev.br/oauth/authorize` (ou o host que servir o relay); URI de token `https://staging-api.heycode.dev.br/oauth/token`; credenciais do cliente iguais às do relay; copie as `redirect_uri` que o console mostra para `OAUTH_REDIRECT_URIS`.
3. Modo de teste: convide só os testadores (verifique no console o limite atual de testadores).

## Roteiro de cada testador

1. Instalar o HeyCode, `heycode init`, `heycode pair CÓDIGO --relay https://...`, `heycode connect`.
2. Vincular a conta pelo aplicativo da Alexa; autorizar o dispositivo no aplicativo do HeyCode quando a skill pedir.
3. "Alexa, abrir HeyCode": esperado "conectado ao computador X". Derrubar `heycode connect`: esperado "offline".
4. Revogar o dispositivo e confirmar que a skill volta a pedir autorização.
5. Excluir a conta e confirmar que o computador deixa de conectar.

## O que registrar

Falhas de reconhecimento (sotaque, nomes de projeto), tempo de resposta, mensagens confusas, passos em que a pessoa travou lendo só a documentação. **Pronto quando:** ao menos duas pessoas externas completam instalação, pareamento, vínculo e uma abertura por voz usando só a documentação. As intents completas (status, aprovar, ditado) dependem do porte do Lambda (trilha seguinte).
