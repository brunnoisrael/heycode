# 0037. Cotas gratuitas e limite de latência do relay

## Status

Aceito. Data: 2026-11-13.

## Contexto

O dono paga a infraestrutura e a Alexa dá poucos segundos de resposta. Spec: `docs/superpowers/specs/2026-11-13-heycode-relay-mvp.md` §3, §5 e §8 (decisões 3 e 4).

## Decisão

- Gratuito: 1 conta, até 2 instalações por conta, 200 pedidos por dia por conta, uma conexão WebSocket ativa por instalação, retenção de 30 dias do log de pedidos (sem conteúdo). Estouro devolve erro claro, nunca derruba os agentes.
- A resposta síncrona à skill espera até 4 s pela máquina; depois, devolve "em andamento" e o resultado segue pela fila assíncrona. Máquina sem conexão devolve "offline" na hora.
- Não há cobrança no MVP; política paga exige ADR próprio.
- Rejeitado: sem cota (risco de custo ilimitado); espera síncrona maior (a Alexa encerra a sessão).

## Consequências

Custo limitado e experiência previsível. Custo: os números são chute inicial e serão revistos com uso real.
