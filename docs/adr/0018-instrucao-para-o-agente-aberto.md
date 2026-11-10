# 0018. "Avise o agente aberto" vai para a fila da sessão aberta, não para uma execução nova

## Status

Aceito. Data: 2026-11-10.

## Contexto

A fila de instruções (ADR 0006) entrega texto a uma sessão aberta pelo hook Stop ou por `buscar_instrucao`, mas
nenhuma frase da skill a alimentava. `SendInstructionIntent` virava um ditado para o claude (ADR 0008) e iniciava
uma execução sem janela (ADR 0007). O dono dizia "avise o agente aberto" e a sessão na tela não recebia nada.
Spec: `docs/superpowers/specs/2026-11-10-instrucao-para-o-agente-aberto.md`.

## Decisão

- O ditado ganha um destino: `target` `"run"` (padrão) ou `"aberto"`. O fluxo de confirmação, a expiração, o
  cancelamento e a exclusão mútua com a criação de projeto são os mesmos; só muda o que o `confirm` faz.
- Com `"aberto"`, a ponte escolhe a sessão mais recente com evento nos últimos `OPEN_SESSION_WINDOW` segundos
  (1800). Agente e projeto vêm da sessão. A Alexa fala o projeto antes do "confirma".
- O `confirm` chama `store.add_instruction`. A entrega continua sendo a do ADR 0006, uma única vez, casando agente
  e projeto.
- `pop_instruction` ganha validade: instrução não entregue em `INSTRUCTION_TTL` segundos (1800) é marcada
  `delivered = 2` e nunca sai. O valor 2 reusa a coluna que já existe; não há mudança de esquema.
- O hook Stop prefixa a instrução com "Instrução do dono, ditada pela Alexa e confirmada por voz: ".
- A Lambda manda só `{target, text}` com o segredo de controle. Ela não lê a fila, que segue exigindo o segredo
  de agente (ADR 0014).
- Alternativa rejeitada: a Lambda chamar `POST /instruction` direto. Pula a confirmação por voz e obriga a Lambda
  a saber agente e projeto.
- Alternativa rejeitada: a voz escolher a sessão. Mais um turno de diálogo para um caso raro; vale a mais recente
  e a Alexa diz qual é.
- Alternativa rejeitada: sem validade na fila. Uma instrução dita hoje seria executada dias depois, na próxima
  vez que alguém abrisse o projeto.

## Consequências

- A instrução chega à sessão que o dono vê, no fim do turno atual. Sessão parada só recebe no fim do próximo
  turno, e a Alexa avisa isso.
- Depende dos hooks do Claude Code instalados. Sem eles a ponte não vê sessão e recusa o pedido.
- O Codex não tem hook Stop; só recebe se chamar `buscar_instrucao` com o mesmo agente e projeto.
- Execução headless do supervisor também dispara os hooks e conta como sessão. Se ela for a mais recente, é ela
  o "agente aberto" até a sessão interativa gerar um evento.
- O resultado da instrução volta por "qual o resultado", que lê o resumo da sessão gravado no Stop.
