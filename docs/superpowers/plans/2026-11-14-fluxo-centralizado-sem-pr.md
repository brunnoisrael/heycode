# Plano: fluxo centralizado sem PR

Spec: `docs/superpowers/specs/2026-11-14-fluxo-centralizado-sem-pr.md` (aprovada e revisada pelo dono).

1. Inventariar worktrees, alterações, dados ignorados e instalações editáveis; preservar os dados necessários.
2. Testar e garantir que pytest use o checkout corrente mesmo com outra instalação editável.
3. Executar CI nas branches de entrega usando a main como base; exigir atualização da branch quando a main avançar. Validar spec, ADR, commits, testes e demais gates técnicos no SHA exato.
4. Gerar evidência automaticamente dos resultados do CI, sem seção manual ou PR. Testar falha de resultados ausentes, cancelados ou malsucedidos.
5. Retirar exigências de revisão por outra conta e assinatura de commit, conforme pedido do dono, mantendo histórico linear, restrições de exclusão e force push e checks técnicos.
6. Registrar ADR, atualizar as instruções, testar localmente e no GitHub e integrar na main sem PR. Verificar que a proteção efetiva exige os checks de qualidade.
