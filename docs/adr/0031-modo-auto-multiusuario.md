# 0031. Modo auto no cenário multiusuário

## Status

Aceito. Data: 2026-11-13.

## Contexto

O ADR 0002 define `auto` sem piso, protegido pela allowlist do dono, o que não existe para terceiros. Spec: `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md` §5.

## Decisão

O caminho do dono mantém o ADR 0002 integralmente. Para instalações pareadas via relay, `auto` é opt-in por instalação, ligado e confirmado no computador, nunca ligável só por voz na primeira vez; outra conta ou dispositivo não associado não o liga. Depois de ligado, vale por voz. Rejeitado: `auto` ligável por voz desde o início (risco de acionamento por terceiro) e remover `auto` (perde a promessa de experiência).

## Consequências

Segurança multiusuário com atrito de um passo único. Custo: o primeiro uso de `auto` exige estar no computador. Atualiza `docs/security/threat-model.md` (G10).
