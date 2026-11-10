# Instrução por voz para o agente que já está aberto

Data: 2026-11-10. Status: aprovada pelo dono na sessão de 2026-11-10 ("faça e garanta que falo pra echo e meu
claude e ou codex estão recebendo"; a escrita desta spec depois do código foi pedida por ele: "faça no final").

## Problema

"Avise o agente aberto" não chegava à sessão aberta. A Lambda tratava a frase como um ditado para o claude e a
ponte iniciava uma execução nova, sem janela, na raiz dos projetos. A sessão que o dono via na tela não recebia
nada. A fila de instruções (`/instruction`, hook Stop, `buscar_instrucao`) existia, mas nenhuma frase a alimentava.

## Comportamento desejado

- "Avise o agente aberto" e a instrução, depois "confirma", põem a instrução na fila da sessão aberta mais recente.
  Nenhuma execução nova é iniciada.
- A Alexa repete o destino antes de confirmar: "Entendi, para o agente aberto no projeto painel: rode os testes.
  Confirma?"
- Depois do "confirma" ela diz quando a instrução chega: "Ele recebe ao terminar o turno atual." se a sessão está
  no meio de um turno, ou "Ele está parado e só recebe ao fim do próximo turno."
- Sem sessão com atividade recente: "Não achei nenhum agente aberto com atividade recente. Nada foi enviado."
- "Peça ao claude" continua iniciando uma execução nova, como antes.

## Requisitos

Ditado (`bridge/dictation/`):

- `POST /dictation` aceita `target`: `"run"` (padrão, comportamento atual) ou `"aberto"`. Outro valor: 422.
  `agent` só é obrigatório com `"run"`.
- Com `"aberto"`, o destino é a sessão mais recente (`store.newest_session`) com evento nos últimos
  `OPEN_SESSION_WINDOW` segundos (padrão 1800). Agente e projeto vêm da sessão, nunca do pedido.
- A instrução só entra na fila no `confirm`. Expiração do ditado, cancelamento e limite de 300 caracteres valem
  igual. A fala de confirmação mascara segredos.

Fila (`bridge/store/`, `bridge/server.py`, `bridge/mcp/`):

- A instrução é entregue uma única vez, para o mesmo agente e projeto da sessão.
- Instrução não entregue em `INSTRUCTION_TTL` segundos (padrão 1800) expira (`delivered = 2`) e nunca é entregue.
- `buscar_instrucao` (MCP) usa a mesma validade. A descrição das ferramentas manda o agente passar `agent` e
  `project` iguais aos de `registrar_status`.

Entrega (`bridge/hook.py`):

- No evento Stop, a instrução volta como `{"decision":"block","reason":...}` com o prefixo "Instrução do dono,
  ditada pela Alexa e confirmada por voz: ", para o agente saber de onde ela veio.
- O hook continua falhando aberto.

Lambda (`skill/lambda/index.js`):

- `SendInstructionIntent` envia `{target: "aberto", text}` com o segredo de controle. Só mantém a sessão aberta
  para o "confirma" quando a ponte devolve `ok` diferente de `false`.

Instalação:

- A sessão só é vista pela ponte se os hooks de `bridge/claude-settings.example.json` estiverem no
  `settings.json` do Claude Code. Sem eles, a resposta é sempre "não achei nenhum agente aberto".

## Fora do escopo

- Entregar a instrução no meio de um turno, ou acordar uma sessão parada.
- Escolher por voz entre várias sessões abertas. Vale a mais recente.
- Hooks para o Codex. Ele só recebe se chamar `buscar_instrucao`.
- Mudança no modelo de interação.

## Verificação

- `python -m pytest`: `tests/dictation/test_open_target.py`, `tests/server/test_open_agent_e2e.py` (inclui o
  `hook.py` real contra a ponte num uvicorn), `tests/store/test_instructions.py`, `tests/mcp/test_tools.py`,
  `tests/hook/test_hook.py`.
- `node --test` em `skill/lambda`.
- Com a ponte no ar e os hooks instalados: abrir uma sessão do Claude Code, mandar `SendInstructionIntent` e
  `ConfirmIntent` pelo handler da Lambda, e conferir que a sessão responde à instrução e que "qual o resultado"
  fala o resumo dela.
