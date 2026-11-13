# 0053. Rotas de comandos locais na ponte e histórico de execuções

## Status

Aceito. Data: 2026-11-13.

## Contexto

O registro local de comandos (ADR 0051) precisa ser alcançado pela voz (via relay) sem dar poder novo ao relay. A ponte já tem o PIN e o bloqueio por tentativas da aprovação por voz. Spec: `docs/superpowers/specs/2026-11-13-heycode-comandos-locais-scripts-e-webhooks.md` §4 e §5.

## Decisão

- Rotas novas na ponte local, todas com o segredo de controle: `GET /voice/commands` (só resumo), `POST /voice/commands/run`, `/confirm`, `/cancel` e `/disable`. Não existe rota para ligar, criar, editar ou remover: isso é só do CLI local.
- Comandos `pin` verificam o PIN na ponte com **o mesmo PIN e o mesmo bloqueio** da aprovação (`pin_lock`: 3 erros bloqueiam por 5 minutos). A verificação fica antes de o executor ser chamado, e o executor só executa com `pin_ok=True`.
- Cada execução grava um evento no histórico (`history`, tipo `command_run`: nome, risco, tipo, resultado, código de saída, duração), **sem a saída**. O store ganha `recent_history(kind, limit)`.
- `GET /voice/audit` (ADR 0049) passa a incluir os eventos recentes de comandos.
- Rejeitado: reaproveitar `/decide` para comandos (mistura aprovações de agente com execuções locais) e guardar a saída no histórico (pode conter segredo).

## Consequências

Um único PIN e um único bloqueio protegem aprovações e comandos. Custo: duplicação pequena da lógica de PIN entre `/decide` e os comandos, a unificar depois.
