# 0041. Account linking por OAuth2 no relay

## Status

Aceito. Data: 2026-11-13.

## Contexto

A skill compartilhada precisa saber a qual conta HeyCode cada requisição pertence. A Amazon exige account linking por OAuth2 (authorization code). Hoje o endpoint da skill aceitava o token de sessão de 12 h (ADR 0036), que a Alexa não consegue renovar. Spec: `docs/superpowers/specs/2026-11-13-heycode-skill-compartilhada.md` §3.

## Decisão

- O relay é servidor OAuth2: `/oauth/authorize` (login do HeyCode) e `/oauth/token` (`authorization_code`, `refresh_token`). Cliente da Alexa pré-registrado por variável de ambiente, com `redirect_uri` de lista fechada e comparação exata; `redirect_uri` inválida não redireciona.
- Código de 10 min e uso único; access token de 1 h; refresh token de 30 dias **rotativo**, com revogação da família quando um refresh já usado reaparece. Tudo guardado como hash; segredo do cliente comparado em tempo constante; PKCE S256 aceito.
- O endpoint da skill passa a aceitar esses tokens além da sessão do app. O token de sessão continua válido para o app e para o `heycode`, mas a Alexa usa o OAuth.
- Rejeitado: provedor externo de identidade (dependência e custo antes de validar) e token de longa duração sem rotação (vazamento duradouro).

## Consequências

A Alexa renova sozinha e a pessoa revincula só ao revogar. Custo: o relay vira servidor de autorização, com superfície de ataque própria (redirecionamento, reuso de código), coberta por testes. Atualiza `docs/security/threat-model.md`.
