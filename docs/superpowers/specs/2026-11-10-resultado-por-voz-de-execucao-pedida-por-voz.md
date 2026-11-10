# Execução pedida por voz sempre devolve o resultado por voz

Data: 2026-11-10. Status: aprovada pelo dono na sessão de 2026-11-10 ("garanta que falo pra echo e meu claude e ou
codex estão recebendo e retornam pra echo quando terminam passando pedido ou o que ele deu de saída").

## Problema

O dono dita uma instrução, diz "confirma" e ouve "Enviado ao claude.". Se a execução termina bem, a resposta do
agente não volta. Ela só entrava na fila de voz com o aviso de fim de ciclo (`report_on_end`) ligado, que vem
desligado. A falha já volta sempre (ADR 0017); o sucesso não.

## Comportamento desejado

- Toda execução iniciada por voz (ditado confirmado ou projeto criado por voz) que termina bem entra na fila de
  voz, com ou sem aviso de fim de ciclo.
- "Qual o status" começa pelo resultado: "O agente claude terminou no projeto Projetos. Resultado: ok." e segue
  com o status da sessão. Falado uma vez.
- "Tem algo pendente" continua dizendo "O agente codex terminou no projeto X. Quer ouvir a saída?", e "qual o
  resultado" lê o resumo.
- Execução que não veio da voz (`POST /runs`) e execução cancelada continuam dependendo de `report_on_end`.

## Requisitos

- `_start_run`, o caminho único da voz, registra o id da execução. No fim, execução registrada com status
  `concluida` é marcada como não falada (`runs.reported = 0`).
- O registro fica em memória. Um reinício da ponte interrompe as execuções em andamento, então nada se perde.
- `/status` fala o aviso mais antigo ainda não falado, falha ou resultado, antes do status da sessão, e o marca
  como falado. A ordem de chegada da fila é mantida.
- O resultado falado é o resumo já gravado (até 400 caracteres, mascarado ao gravar) e passa por `say`.
- `/pending` e `/result` não mudam.

## Fora do escopo

- Fala espontânea da Alexa. O resultado continua dependendo de o dono perguntar, ou do push.
- Repetir o pedido original na fala. A fala traz agente, projeto e a resposta do agente.
- Mudanças na Lambda, no modelo de interação e no esquema do banco.

## Verificação

- `python -m pytest`, com `tests/server/test_voice_run_result.py`: sucesso por voz em `/pending`, `/result` e
  `/status` com `report_on_end` desligado, uma vez só; run direta e cancelada fora da fila; resultado mascarado;
  projeto criado por voz.
- Com a ponte reiniciada, pelo handler da Lambda: `AskAgentIntent`, `ConfirmIntent` e `StatusIntent` para o
  claude e para o codex. A Alexa fala "terminou ... Resultado: ok".
