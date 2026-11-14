# Ajuste da esteira para integração inicial

Data: 2026-11-13. Status: aprovada pelo dono nesta conversa para a exceção única descrita abaixo.

## Problema

A integração já desenvolvida adiciona aproximadamente 15.700 linhas verificadas pelo G12, acima do limite de 400 por integração. A regra impede incorporar a base existente de uma vez. A exigência remota de PR foi removida a pedido do dono; assinatura verificada e testes continuam exigidos pelo GitHub.

## Proposta para aprovação

Permitir **uma única integração inicial** do histórico atualmente preparado no commit `d01915d` e de correções estritamente necessárias à sua validação, sem aplicar a essa integração o teto numérico de 400 linhas. O teto continua obrigatório para as alterações seguintes. A exceção deve identificar explicitamente o commit inicial, não pode virar uma opção genérica controlada por variável ou rótulo, e deve ser removida após a integração. O mecanismo concreto precisa ser revisado junto com o plano e com um ADR novo para a mudança de governança.

Continuam obrigatórios: specs aprovadas e trailers, testes da matriz, cobertura, varredura de segredos e dependências, análise de lint, assinaturas verificadas e proteção contra force push. A mudança não aprova nem autoriza eliminar falhas de segurança. A integração deve ser produzida com assinatura verificada; o PR existente pode ser usado como meio opcional, sem voltar a ser exigência geral.

## Operação e validação

Antes de qualquer deploy: backup do banco, pacote gerado do commit integrado à `main` remota, build, teste de saúde e registro do commit em `VERSION`. Preservar a allowlist do dono e o comportamento já aprovado do modo auto. Confirmar separadamente os fluxos de login, autorização e isolamento; não afirmar que todo risco foi eliminado.

## Limites

Esta aprovação não altera credenciais nem dispensa os demais gates. O mecanismo aprovado fixa os identificadores da base e do histórico de integração e aplica o limite normalmente às mudanças posteriores.
