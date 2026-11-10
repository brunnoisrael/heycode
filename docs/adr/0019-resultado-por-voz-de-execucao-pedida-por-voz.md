# 0019. Execução pedida por voz sempre devolve o resultado por voz

## Status

Aceito. Data: 2026-11-10. Altera o ADR 0017 no ponto "sucesso continua dependendo de `report_on_end`".

## Contexto

O ADR 0017 pôs toda falha na fila de voz e deixou o sucesso dependendo de `report_on_end`, que vem desligado.
Na prática o dono pedia algo pelo Echo, ouvia "Enviado ao claude." e a resposta do agente nunca voltava. Quem
pede por voz quer a resposta por voz. Spec:
`docs/superpowers/specs/2026-11-10-resultado-por-voz-de-execucao-pedida-por-voz.md`.

## Decisão

- `_start_run` em `bridge/server.py` é o único caminho da voz (ditado e projeto novo). Ele guarda o id da
  execução em um conjunto em memória. No fim, execução desse conjunto com status `concluida` entra na fila de
  voz (`runs.reported = 0`, ADR 0015), sem olhar `report_on_end`.
- `/status` passa a falar o aviso mais antigo da fila, falha ou resultado, antes do status da sessão:
  "O agente claude terminou no projeto X. Resultado: ...". `/pending` e `/result` ficam como estão.
- `report_on_end` continua valendo para execução iniciada por `POST /runs` e para execução cancelada.
- Alternativa rejeitada: ligar `report_on_end` por padrão. Mudaria também as execuções que não vieram da voz e
  seria desfeito por um "desligar aviso de fim de ciclo".
- Alternativa rejeitada: coluna `runs.origin`. O conjunto em memória basta, porque um reinício interrompe as
  execuções em andamento e execução interrompida não é avisada.

## Consequências

- O dono ouve a resposta do agente na primeira pergunta que fizer depois do fim, inclusive "qual o status".
- O aviso é consumido ao ser falado. Se a resposta da Alexa se perder, o resultado segue em `/runs/latest`.
- A resposta é lida como o agente a escreveu, até 400 caracteres, mascarada. Resposta longa é cortada.
- A Alexa continua sem falar sozinha: sem pergunta do dono, só o push (ntfy ou webhook) avisa.
