# 0063. Preservar conexões de saída dos contêineres na borda

## Status

Aceito. Data: 2026-11-14.

## Contexto

A allowlist de origem do ADR 0058 filtrava também conexões iniciadas pelos contêineres para portas 80 e 443, pois o Docker encaminha ambos os sentidos pela cadeia DOCKER-USER. Isso impedia, por exemplo, baixar certificados e dependências HTTPS. A spec `docs/superpowers/specs/2026-11-14-heycode-painel-rotas-e-borda.md` exige que a borda preserve o funcionamento da Alexa.

## Decisão

Antes de verificar as faixas da Cloudflare, devolver ao processamento normal do Docker os pacotes recebidos das interfaces de bridge `docker0` e `br+`. O tráfego recebido da interface pública continua submetido à allowlist e ao descarte padrão.

## Consequências

Os contêineres voltam a iniciar conexões web. A regra depende dos nomes padrão das bridges do Docker; interfaces alternativas exigem revisão e teste. Testes simulam as regras geradas para IPv4 e IPv6.
