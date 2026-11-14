# 0043. Dispositivos por conta e instalação padrão

## Status

Aceito. Data: 2026-11-13.

## Contexto

A proteção do dono é uma allowlist global de usuário e dispositivo na Lambda (ADR 0002 e AGENTS.md), que não existe para terceiros. A pessoa precisa controlar quais Echos acionam sua máquina e qual máquina responde. Spec: `docs/superpowers/specs/2026-11-13-heycode-skill-compartilhada.md` §5 e ADR 0031.

## Decisão

- Associação persistente por (conta, instalação, dispositivo). Dispositivo desconhecido numa requisição autêntica **não executa nada**; vira solicitação pendente que a conta dona aprova ou nega no app. Revogação volta o dispositivo ao estado desconhecido. Nunca allowlist global.
- Instalação padrão por conta, definida no app. Com uma só instalação ela é usada; com várias e sem padrão a skill pede a escolha no app e não executa. Nunca se roteia para instalação de outra conta.
- Exclusão da conta apaga associações, tokens e instalações.
- Rejeitado: aprovar o dispositivo por voz (o primeiro Echo não está autorizado a se autorizar) e escolher a máquina por voz a cada pedido (atrito e erro de reconhecimento).

## Consequências

Cada Echo é autorizado uma vez, no app. Custo: um passo de configuração por dispositivo e por máquina extra.
