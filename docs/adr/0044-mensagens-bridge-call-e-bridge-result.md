# 0044. Mensagens `bridge-call` e `bridge-result` no protocolo v1

## Status

Aceito. Data: 2026-11-13.

## Contexto

As intents do Lambda do dono são, no fundo, chamadas HTTP à ponte local com a fala pronta na resposta. No modo compartilhado o relay precisa fazer o mesmo sem túnel. O protocolo v1 (ADR 0029) só tem `instruction`, que carrega texto e não serve para status, aprovação, modo ou projetos. Spec: `docs/superpowers/specs/2026-11-13-heycode-intents-no-modo-compartilhado.md` §3.

## Decisão

- Dois tipos novos, aditivos, no mesmo v1: `bridge-call` (relay → máquina, payload `{method, path, body?}`) e `bridge-result` (máquina → relay, payload `{status, body, in_reply_to}`, assinado pela instalação). A correlação usa `in_reply_to` (ADR 0038).
- O relay não conhece o segredo da ponte nem monta URLs: ele só diz método e caminho lógicos; quem decide se a chamada é permitida e a executa é a máquina (ADR 0045).
- Um cliente antigo que não conhece os tipos ignora o quadro (envelope inválido); o relay recebe só a falha por tempo e fala a frase de falha. Não há quebra silenciosa.
- Rejeitado: reaproveitar `instruction` com texto estruturado (mistura semântica e escapa da validação do esquema) e abrir um túnel HTTP genérico para a ponte (poder amplo demais).

## Consequências

O porte das intents usa um único canal tipado e validado por esquema. Custo: dois esquemas novos a manter e um tipo a mais no enum de `envelope`; versão do protocolo não muda, registrada em `protocol/CHANGELOG.md`.
