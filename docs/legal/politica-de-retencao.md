# Política de retenção e exclusão de dados do HeyCode (RASCUNHO)

> Rascunho técnico; revisão do dono antes de publicar.

| Dado | Retenção | Como é apagado |
|---|---|---|
| Conta (e-mail, hash da senha) | Até a exclusão da conta | `DELETE /v1/account` |
| Computadores pareados e chaves públicas | Até a revogação ou a exclusão da conta | Revogação no aplicativo ou exclusão da conta |
| Dispositivos Alexa | Até a revogação ou a exclusão da conta | Revogação no aplicativo ou exclusão da conta |
| Tokens OAuth (hash) | Acesso 1 h; renovação 30 dias (rotativo) | Expiração, reuso detectado, desvinculação ou exclusão da conta |
| Sessões do aplicativo | 12 h | Expiração ou logout |
| Contador diário de pedidos | 30 dias | Rotina de limpeza (a implementar antes do beta aberto) |
| Backups do banco | 30 dias | Rotação do backup; **restauração pode reviver dados já apagados**, então a exclusão deve ser reaplicada (runbook de restauração) |
| Conteúdo dos pedidos e saídas dos agentes | Não é guardado | Memória do serviço, perdida ao reiniciar |

Pedidos de titulares são atendidos em até 15 dias, por `privacy@heycode.dev.br` (a ativar).
