# 0061. Remover os gates de revisão de PR

## Status

Aceito. Data: 2026-11-14, por pedido explícito do dono.

## Contexto

As verificações G11 e G15 exigiam uma aprovação por outra conta e um bot configurado, embora o dono tenha determinado que revisão de PR não é mais gate. Consulte a spec `docs/superpowers/specs/2026-11-14-sem-gate-de-revisao-pr.md`.

## Decisão

Remover os jobs e a lógica obrigatória de revisão humana e de bot, inclusive CODEOWNERS usado para essa exigência. A revisão permanece possível, sem bloquear a integração. Permanecem as verificações de spec aprovada, ADR, formato, testes, segurança, tamanho e assinatura exigida pela main.

## Consequências

A ausência de revisão independente aumenta o risco de erros não detectados; testes e verificações automáticas continuam obrigatórios. Alterações de gates ainda exigem pedido humano conforme AGENTS.md.
