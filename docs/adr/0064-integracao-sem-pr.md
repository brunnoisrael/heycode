# 0064. Validar a entrega antes da integração sem PR

## Status

Aceito. Data: 2026-11-14. Spec: `docs/superpowers/specs/2026-11-14-fluxo-centralizado-sem-pr.md`.

## Contexto

O CI da main executava somente após o push direto, e evidência dependia do corpo de PR. O dono aprovou um fluxo sem PR com revisão independente para o commit exato, preservando testes, gates e regras de proteção. O ADR 0061 removeu revisão em PR; essa decisão não volta a exigir PR.

## Decisão

Executar o CI também em branches de entrega atualizadas com a main, usando a main como base. Validar a evidência na mensagem do commit de entrega. Verificar o parecer de uma identidade GitHub configurada, distinta do autor, como status `heycode-review` do SHA exato. A ausência de identidade, autor ou parecer aprovado falha fechada. O workflow pode ser executado novamente após o parecer por `workflow_dispatch`.

A proteção da main deve exigir, além dos checks existentes, `evidencia` e `revisao-independente` para que ambos sejam verificados antes da integração. A revisão e o CI devem ser associados ao mesmo SHA; a main deve permanecer ancestral desse SHA. A configuração do revisor deve apontar para uma conta controlada de forma independente e com permissão para emitir status.

## Consequências

A integração depende da configuração efetiva da identidade revisora e da atualização do ruleset remoto. Sem essas condições o fluxo não está pronto e não se deve integrar. O status é uma declaração da conta revisora, não prova automática da qualidade da análise. Credenciais de autoria e revisão devem permanecer separadas. Alterações posteriores exigem novos checks e parecer.
