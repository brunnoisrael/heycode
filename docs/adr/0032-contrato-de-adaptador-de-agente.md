# 0032. Contrato de adaptador de agente

## Status

Aceito. Data: 2026-11-13.

## Contexto

Claude Code, Codex e Aider oferecem capacidades diferentes e a voz não pode prometer o que o agente não faz. Spec: `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md` §6.

## Decisão

Protocol Python com `capabilities()`, `start`, `instruct`, `cancel`, `resume`, `result`. Capacidades `START`, `INSTRUCT_OPEN_SESSION`, `CANCEL`, `RESUME`, `READ_RESULT`; chamar não declarada levanta `UnsupportedCapability`. Um teste de conformidade único roda contra os três adaptadores no CI. Adaptadores falham abertos. Rejeitado: interface mínima sem capacidades declaradas.

## Consequências

Agentes intercambiáveis e respostas honestas por voz. Custo: adaptador novo precisa passar na conformidade.
