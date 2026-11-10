# Falha de execução avisada por voz, com motivo legível

Data: 2026-11-10. Status: aprovada pelo dono na sessão de 2026-11-10 ("manda bala e teste pra ver se corrige").

## Problema

O dono dita uma instrução, diz "confirma" e ouve "Enviado ao claude.". Se a execução falha, ele não fica sabendo.
Hoje a falha é muda por dois motivos:

1. O resumo gravado não diz o que aconteceu. Em falha, `_finish` guarda os últimos 400 caracteres do stdout. No
   claude isso é o rabo do JSON de saída. Exemplo real de hoje: a execução falhou com
   `API Error: 400 Claude Code 2.1.207 does not support this model; version 2.1.290 or newer is required. Run
   'claude update'`, e o resumo gravado termina em `"terminal_reason":"api_error","fast_mode_state":"off",...}`.
   No codex o erro real, `The 'gpt-6.1-terra' model is not supported when using Codex with a ChatGPT account`,
   chega embrulhado em dois níveis de JSON dentro dos eventos `error` e `turn.failed`.
2. A falha não chega à voz. A execução só entra na fila de `/pending` e `/result` com o aviso de fim de ciclo
   (`report_on_end`) ligado, e ele vem desligado. O push só existe com `NTFY_TOPIC` ou `HA_WEBHOOK_URL`. Uma
   execução que falha em dez segundos não aparece em lugar nenhum, e "qual o status" segue falando de outra sessão.

## Comportamento desejado

- O resumo de uma execução que falhou traz a mensagem de erro que o agente deu.
- Uma execução que falhou é sempre avisada por voz, com ou sem aviso de fim de ciclo. Na próxima vez que o dono
  perguntar "qual o status", "tem algo pendente" ou "qual o resultado", a Alexa começa por:
  "O agente claude falhou no projeto Projetos: API Error: 400 Claude Code 2.1.207 does not support this model;
  version 2.1.290 or newer is required. Run 'claude update', ..."
- O aviso é dado uma vez. Depois de falado, a falha continua em `/runs/latest` e `/runs/<id>`.
- Execução que termina bem, ou que o dono cancelou, continua respeitando `report_on_end`.

## Requisitos

Resumo de falha (`bridge/supervisor/`):

- Claude: o motivo sai do objeto de `--output-format json`. Ordem: campo `result`; lista `errors`; `error` ou
  `message`; `subtype` diferente de `success`. O objeto pode ser a saída inteira ou a última linha JSON.
- Codex: o motivo sai dos eventos `--json`. Ordem: último `turn.failed`; último `error`; último `item.completed`
  com item do tipo `error` (aviso do codex, só vale se não houver erro de turno).
- JSON de erro embutido na mensagem é trocado pela mensagem que ele carrega (`error.message`), em até quatro níveis.
- Aider e agentes desconhecidos: como hoje, as últimas linhas da saída (stdout e stderr vêm juntos).
- Saída que não é JSON, ou JSON sem mensagem, cai no comportamento atual. O parser nunca levanta exceção e nunca
  impede a finalização.
- O motivo é gravado em uma linha, mascarado, cortado em 400 caracteres pelo começo. A cauda da saída continua
  cortada pelo fim.
- O status não muda: falha é código de saída diferente de zero ou erro ao abrir o processo.

Aviso por voz (`bridge/server.py`):

- No fim de uma execução com status `falhou`, a execução é marcada como não falada (`runs.reported = 0`), qualquer
  que seja o `report_on_end`.
- `/status`, `/pending` e `/result` falam a falha mais antiga ainda não falada e a marcam como falada. Em
  `/status` a fala da falha vem antes do status da sessão. Em `/pending`, aprovação pendente tem prioridade e não
  consome a falha.
- A fila mantém a ordem de chegada: um fim de ciclo bem-sucedido anterior (com `report_on_end` ligado) é falado
  antes.
- O push (ntfy e webhook) segue com as mesmas condições. Só o texto muda: título "claude falhou" e o motivo curto.

Fala segura:

- A fala usa só a última linha do resumo, com espaços normalizados e no máximo 200 caracteres.
- Texto com cara de JSON (`{`, `}` ou `"chave":`) não é lido. A Alexa diz: "O agente claude falhou no projeto X.
  Não consegui identificar o motivo; veja a saída no computador."
- O motivo passa pela máscara de segredos duas vezes: ao gravar o resumo e em `say`, o caminho único das falas.

## Fora do escopo

- Tratar como falha a execução do claude que sai com código zero e `is_error` verdadeiro.
- Traduzir ou resumir a mensagem do agente. Ela é lida como veio, em geral em inglês.
- Avisar a execução `interrompida` por reinício da ponte e o erro interno do supervisor.
- Fala espontânea da Alexa. O aviso continua dependendo de o dono perguntar, ou do push.
- Mudanças na Lambda, no modelo de interação e no esquema do banco.

## Verificação

- `python -m pytest`, com testes novos em `tests/supervisor/test_failure.py`, `tests/supervisor/test_manager.py` e
  `tests/server/test_run_failure_voice.py`: parser do claude com o JSON de erro real, parser do codex com os
  eventos reais, fallback, falha em `/pending`, `/result` e `/status` com `report_on_end` desligado, sucesso fora
  da fila, segredo mascarado, JSON cru não lido.
- Com a ponte reiniciada: ditar uma instrução ao claude enquanto ele falha por versão antiga, dizer "confirma" e
  perguntar "qual o status". A Alexa fala a falha e o motivo.
