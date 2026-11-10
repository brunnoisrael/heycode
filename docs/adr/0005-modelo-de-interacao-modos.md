# 0005. Modelo de interação para modos por voz e allowlist da skill

## Status

Aceito. Data: 2026-11-09.

## Contexto

A fase 2 introduz os modos manual, auto e decisões e a flag `report_on_end` (ADR 0004), que o dono precisa trocar por voz. Além disso, a skill fica exposta publicamente na Alexa, e a spec (§10) exige que a Lambda só atenda o dono. Spec: `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (§7, §8, §10).

## Decisão

- Dois intents novos no modelo pt-BR: `SetModeIntent` (slot `modo`, tipo customizado `MODO` com ids `manual`, `auto`, `decisoes`; sinônimos de `auto`: "automático", "tudo liberado") e `ReportOnEndIntent` (slot `ligado`, tipo `LIGADO` com `ligar`/`desligar`; sem slot significa ligar).
- A Lambda resolve o modo pelo id da resolução de entidade e, na falta dela, normaliza o texto falado (sem acento, minúsculo). Modo desconhecido não chama a ponte; a skill pergunta de novo.
- Trocar de modo, inclusive para auto, não exige PIN (restrição da fase 2). O PIN segue obrigatório para aprovar comandos por voz.
- Allowlist em um request interceptor: compara `userId` e `deviceId` com `ALLOWED_USER_ID` e `ALLOWED_DEVICE_ID`, lidos do ambiente a cada requisição. Falha do interceptor vira fala de acesso negado, via error handler, antes de qualquer handler ou `fetch`.
- Se uma das variáveis não estiver configurada, a skill recusa, pede a configuração e registra no log os IDs vistos, para o dono copiá-los do CloudWatch.
- Alternativas rejeitadas: checar a allowlist dentro de cada handler (fácil esquecer um); depender só do `x-secret` (não protege a Lambda em si); exigir PIN para mudar de modo (contraria a decisão do dono).

## Consequências

- Todo intent novo ou antigo passa pela allowlist sem código extra.
- O primeiro uso exige um ciclo de configuração: invocar a skill, ler os IDs no log e definir as variáveis.
- Os IDs aparecem em log; o log da Lambda deve ficar restrito ao dono.
- Um userId vazado não basta: o deviceId também precisa coincidir, mas ambos são identificadores, não segredos fortes.
