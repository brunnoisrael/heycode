# Plano: fluxo centralizado sem PR

Spec: `docs/superpowers/specs/2026-11-14-fluxo-centralizado-sem-pr.md` (aprovada pelo dono).

1. Inventariar os worktrees, alterações, dados ignorados e instalações editáveis; preservar os dados antes de remover cópias antigas.
2. Garantir por configuração e teste que pytest importe o código do checkout corrente, inclusive quando outro checkout estiver no caminho Python.
3. Desenhar e testar uma execução dos gates e da revisão independente para commits na `main`, incluindo comparação de commits e registro de evidência sem PR. Verificar as proteções reais do remoto antes de mudar a integração.
4. Registrar um ADR novo se a solução alterar a arquitetura; implementar e testar conforme a spec. Alterações nos gates, workflows ou instruções protegidas dependem de pedido humano explícito para esses caminhos.
5. Atualizar o guia de contribuição e operação com o fluxo que realmente estiver em funcionamento, incluindo instalação isolada e conferência da origem do pacote.
6. Validar os testes locais e os checks no remoto; integrar sem PR somente quando o fluxo e as proteções permitirem.

## Desenho a validar para integração

- Executar a matriz e os gates em uma branch de entrega antes de atualizar `main`; usar a `main` remota como base e o commit exato da entrega como cabeça. Um push que só dispare os checks depois de atualizar `main` não é uma verificação prévia.
- Registrar a evidência associada ao commit e verificar sua presença automaticamente. O formato e o armazenamento precisam substituir o corpo de PR sem deixar conteúdo de contribuição executar comandos.
- A revisão independente deve produzir um resultado verificável para o SHA exato, com identidade distinta do autor e proveniência autenticada. O fluxo precisa falhar fechado se o revisor ou o resultado estiver ausente ou desatualizado.
- Tornar esses resultados exigíveis na proteção da `main`, manter assinaturas, histórico linear e os checks atuais, e testar recusa de entrega sem revisão, sem evidência e com SHA desatualizado.
- Na auditoria de 2026-11-14, o ruleset remoto exigia `gates`, a matriz de testes e assinaturas, mas não listava revisão ou evidência. O CI da `main` executava evidência apenas em PR e disparava `push` apenas na `main`. Não há fluxo prévio sem PR validado nesta auditoria.
