# 0013. Skill: decisão amarrada ao id, modo falado, projeto por voz e cancelar run

## Status

Aceito. Data: 2026-11-10.

## Contexto

A revisão final (`docs/superpowers/specs/2026-11-10-revisao-final.md`, achados A4, M1, M3 e B1) apontou quatro falhas na skill. Aprovar ou negar valia para "o pedido pendente mais antigo" no momento da chamada, não para o que a Alexa tinha lido ao dono, então um pedido novo podia ser aprovado por engano. O ditado ignorava o projeto citado. Os intents de modo falavam `d.speech`, que a ponte não devolvia, e a Alexa ficava muda. Não havia como cancelar uma run nem avisar o agente aberto por voz. Além disso, a ponte passa a ter dois segredos (agente e controle): a Lambda só precisa do de controle. Spec: `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`.

## Decisão

- A Lambda lê `BRIDGE_CONTROL_SECRET` e o envia em `x-secret`. Ela nunca recebe o segredo de agente.
- `PendingIntent` guarda `approval_id` (devolvido por `/pending`) em `sessionAttributes`. `ApproveIntent` e `DenyIntent` o enviam em `/decide`. Sem `approval_id` na sessão, a skill fala "Pergunte primeiro o que está pendente." e não chama a ponte. A ponte recusa o id que não for o pendente mais antigo.
- `AskAgentIntent` ganha o slot opcional `projeto` (`NOME_PROJETO`); o id resolvido (ou o texto falado) vai em `project` no `/dictation`. A chave só é enviada quando o slot existe. Resposta `ok: false` (projeto inexistente) é falada sem pedir confirmação.
- `SetModeIntent` e `ReportOnEndIntent` falam `d.speech`; se faltar, a Lambda fala uma frase padrão ("Modo automático ativado.", "Aviso de fim de ciclo ligado.").
- Novos intents: `CancelRunIntent` ("cancela o agente", "para o agente") chama `POST /runs/latest/cancel`; `SendInstructionIntent` ("avise o agente aberto {instrucao}") usa o ditado normal com `agent="claude"` e a mesma confirmação.
- Alternativa rejeitada: guardar o id no DynamoDB ou na ponte por usuário. A sessão da Alexa já tem o ciclo certo (pergunta e resposta na mesma conversa) e não adiciona infraestrutura.

## Consequências

Aprovar só funciona depois de perguntar o que está pendente na mesma sessão, o que evita aprovar às cegas. O custo é um passo a mais quando a sessão expira. A skill depende de a ponte (onda 2) implementar `approval_id`, `speech` em `/mode`, `project` em `/dictation` e `/runs/latest/cancel`; até lá, o `approval_id` ausente bloqueia aprovações por voz. O modelo de interação mudou, então é preciso reimportar o JSON no console da Alexa e refazer o build do modelo.
