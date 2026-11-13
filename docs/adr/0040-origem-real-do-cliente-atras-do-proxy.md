# 0040. Origem real do cliente atrás do proxy da plataforma

## Status

Aceito. Data: 2026-11-13.

## Contexto

O relay limita taxa de login e tentativas de pareamento por IP de origem (ADR 0037, ADR 0030). Atrás do proxy da plataforma, o IP visto pelo processo é o do proxy: sem tratamento, um único atacante bloquearia login e pareamento de todos, ou todos dividiriam o mesmo limite. Spec: `docs/superpowers/specs/2026-11-13-heycode-relay-mvp.md` §5.

## Decisão

O contêiner roda `uvicorn --proxy-headers --forwarded-allow-ips "*"`, de modo que a origem vem do `X-Forwarded-For` posto pelo proxy. Isso só é seguro enquanto a porta do contêiner **não** é exposta direto (só o proxy chega nela); se for exposta, o valor `*` deve ser trocado pelo IP do proxy, senão a origem pode ser forjada e o limite contornado. O requisito está comentado no `infra/Dockerfile` e em `infra/README.md`. Rejeitado: limite global sem origem (um abusador derruba todos) e confiar no cabeçalho sem restringir a rede (permite forjar).

## Consequências

Limites por pessoa de verdade. Custo: dependência de a plataforma sobrescrever `X-Forwarded-For` (Fly.io e proxies comuns fazem); mudar de plataforma exige rever esta configuração.
