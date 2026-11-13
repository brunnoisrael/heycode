# 0030. Identidade por instalação com Ed25519

## Status

Aceito. Data: 2026-11-13.

## Contexto

O segredo compartilhado atual não isola usuários. Spec: `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md` §4.

## Decisão

Cada instalação gera um par Ed25519 no primeiro `heycode pair`; a privada fica só no diretório de dados (ADR 0027), o relay guarda a pública. Envelopes assinados sobre JSON canônico. Anti-replay: janela de 10 min de `id` e `ts` dentro de ±2 min. Rotação assinada pela chave antiga; revogação pelo dono da conta. Pareamento: código de 8 caracteres, uso único, 5 min, 5 tentativas, confirmação nos dois lados. Dispositivo Alexa associado por (conta, instalação), nunca allowlist global. O caminho do dono (segredo + allowlist) fica intacto. Rejeitado: segredo compartilhado por usuário (vaza por cópia) e mTLS (operação pesada para o usuário).

## Consequências

Conta A não aciona a máquina de B. Custo: dependência `cryptography` (passa por G8) e gestão de chaves; perda da chave exige novo pareamento.
