# 0033. Endpoint da skill em HTTPS próprio

## Status

Aceito. Data: 2026-11-13.

## Contexto

A skill compartilhada não pode exigir que cada pessoa configure uma Lambda. Spec: `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md` §9, decisão 2.

## Decisão

A skill compartilhada aponta para um endpoint HTTPS próprio no relay (`api.heycode.dev.br`), um salto até a máquina do usuário. A Lambda atual com allowlist do dono continua apenas para o caminho do dono até o beta fechado validar o novo caminho. Rejeitado: Lambda por usuário (configuração demais) e Lambda central como proxy (salto extra de latência).

## Consequências

Menor latência e zero configuração AWS para a pessoa. Custo: operar endpoint e certificado (P3), e a Amazon exige certificado válido e validação de assinatura de requisição.
