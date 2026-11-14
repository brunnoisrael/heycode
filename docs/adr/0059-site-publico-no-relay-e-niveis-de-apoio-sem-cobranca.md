# 0059. Site público servido pelo relay e níveis de apoio sem cobrança

## Status

Aceito. Data: 2026-11-14. Estende o ADR 0046 (painel servido pelo relay) e o ADR 0037 (limites).

## Contexto

O relay só servia o painel logado em `/app`; a raiz respondia 404. O dono quer um site com identidade e uma tela de planos, mas não pode ter empresa nem, por ora, integrar cobrança. A revisão adversarial de 2026-11-13 apontou que a demanda ainda não foi validada. Os limites por conta (2 computadores, 30 atalhos, 200 pedidos por dia) eram constantes no código. Spec: `docs/superpowers/specs/2026-11-14-heycode-site-publico-e-apoio.md`.

## Decisão

- O relay passa a servir páginas públicas estáticas (`/` e `/apoie`) de `src/heycode/relay/site/`, com a mesma CSP do painel e os estáticos na mesma lista fechada. Sem build e sem recurso de terceiros.
- Os limites passam a depender do **nível** da conta (`livre`, `apoiador`, `patrono`), definido em `heycode.relay.plans`. O nível é guardado no relay e **só muda por comando no servidor** (`python -m heycode.relay.grant`); nenhuma rota HTTP o altera.
- Os níveis são apresentados como contribuição voluntária com valor sugerido. O relay não cobra, não integra provedor de pagamento e não registra pagamento. O usuário logado pode registrar interesse em apoiar; isso serve para medir demanda.
- Alternativas rejeitadas: cobrança integrada (exige provedor e situação fiscal indisponíveis); site em hospedagem separada (mais uma peça, sem ganho agora); formulário público de e-mail (spam e LGPD).

## Consequências

- O dono concede níveis à mão e combina a contribuição fora do sistema. Isso não escala, e é aceito enquanto a demanda é medida.
- Receber contribuições recorrentes como pessoa física pode ter efeito fiscal; essa avaliação é do dono e está fora do software.
- Páginas públicas aumentam a superfície exposta da VM; ficam atrás da guarda por IP e do cache da Cloudflare (ADR 0058).
- Os textos do site passam a ser uma promessa pública: recurso não construído precisa estar marcado como "em construção".
