# 0064. Versionamento e gates técnicos sem PR

## Status

Aceito. Data: 2026-11-14. Spec: `docs/superpowers/specs/2026-11-14-fluxo-centralizado-sem-pr.md`.

## Contexto

O CI só verificava branches de entrega por PR e a evidência exigia texto manual. O dono pediu integração sem PR, gates de qualidade e de SDLC e retirada de exigências de conta revisora, assinatura de commit e limite artificial de tamanho G12.

## Decisão

O CI roda em branches de entrega atualizadas com a main e valida o commit exato antes da integração. A evidência é gerada automaticamente pelo CI a partir dos resultados dos gates e da matriz. Não há aprovação por revisor, conta de bot, assinatura de commit obrigatória ou limite G12. O histórico permanece linear, sem exclusão da main ou force push.

O ruleset da main exige os gates técnicos e a matriz existentes. Sua alteração e a integração devem ser verificadas no remoto, mantendo os checks de qualidade e SDLC. Resultados ausentes ou cancelados não são sucesso.

## Consequências

As entregas deixam de depender de PR, configuração de outra conta ou formulário manual. Os logs e o resumo do CI registram o resultado real. Alterações posteriores exigem nova execução do CI para o novo SHA.
