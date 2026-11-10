# 0017. Falha de execução sempre avisada por voz, com o motivo dado pelo agente

## Status

Aceito. Data: 2026-11-10.

## Contexto

Uma execução do supervisor (ADR 0007) que falhava ficava muda. O resumo gravado em falha era a cauda do stdout,
que no claude é o rabo do JSON de saída e no codex é um evento JSON embrulhado, então a mensagem de erro real se
perdia. E a execução só entrava na fila de voz (`runs.reported = 0`, ADR 0015) com `report_on_end` ligado, que vem
desligado. O dono ouvia "Enviado ao claude." e mais nada. A regra do projeto proíbe ler saída em voz alta sem
resumo e sem mascarar segredos, o que impede simplesmente ler a cauda. Spec:
`docs/superpowers/specs/2026-11-10-falha-de-run-avisada-por-voz.md`.

## Decisão

- `bridge/supervisor/failure.py` extrai o motivo da falha da saída do agente: o objeto de
  `claude -p --output-format json` (campo `result`, depois `errors`, `error`, `subtype`) e os eventos de
  `codex exec --json` (`turn.failed`, depois `error`, depois item de erro). JSON de erro embutido na mensagem é
  trocado pelo `error.message` que ele carrega. Saída não reconhecida devolve `None` e `_finish` usa a cauda, como
  antes. O parser nunca levanta.
- O motivo extraído é gravado em uma linha e cortado pelo começo; a cauda segue cortada pelo fim. O critério de
  falha (código de saída diferente de zero) não muda.
- A fila de voz que já existe passa a receber toda execução `falhou`, sem olhar `report_on_end`. Sucesso e
  cancelamento continuam dependendo de `report_on_end`. Não há coluna, tabela nem rota nova.
- `/status`, `/pending` e `/result` falam a falha mais antiga não falada ("O agente claude falhou no projeto X:
  motivo.") e a marcam como falada na mesma chamada. A falha já traz o motivo, então não há a pergunta "Quer ouvir
  a saída?" nem um segundo passo.
- A fala usa só a última linha do resumo, até 200 caracteres, passa por `say`, e se recusa a ler texto com cara de
  JSON: nesse caso diz que não identificou o motivo e manda olhar no computador.
- Alternativa rejeitada: ligar `report_on_end` por padrão. Resolveria a falha, mas faria todo sucesso virar aviso,
  contra a escolha do dono, e ainda leria o rabo do JSON.
- Alternativa rejeitada: coluna nova `runs.error` e uma fila só de falhas. Mais esquema e mais rotas para o mesmo
  efeito; `summary` e `reported` bastam.
- Alternativa rejeitada: falar a falha só em `/pending` e `/result`. A pergunta que o dono faz é "qual o status",
  e ela seguiria falando de outra sessão.
- Alternativa rejeitada: pedir ao claude `--output-format stream-json` para ter eventos de erro. Muda o comando de
  todas as execuções para ganhar o que o campo `result` já entrega.

## Consequências

- O dono ouve a falha e o motivo na primeira pergunta que fizer, mesmo com o aviso de fim de ciclo desligado.
- O aviso é consumido ao ser falado, inclusive por `/status` e `/pending`, que antes só liam. Se a resposta da
  Alexa se perder, a falha não se repete por voz; ela continua em `/runs/latest` e `/runs/<id>`.
- A mensagem é lida como o agente a escreveu, em geral em inglês e com nomes de modelo e versões. Fica legível,
  mas não traduzida.
- O parser depende do formato de saída do claude e do codex. Se o formato mudar, a extração devolve `None`, o
  resumo volta a ser a cauda e a fala cai em "não consegui identificar o motivo": degrada, não quebra.
- A heurística contra JSON cru também barra uma mensagem legítima que contenha chaves. Risco aceito: é preferível
  calar o motivo a ler JSON em voz alta.
- Execução `interrompida` por reinício e erro interno do supervisor continuam sem aviso.
