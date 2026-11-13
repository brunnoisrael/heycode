# 0038. Correlação de resposta e quadros do relay sem assinatura

## Status

Aceito. Data: 2026-11-13.

## Contexto

O relay envia pedidos à máquina e precisa associar a resposta ao pedido. O protocolo v1 (ADR 0029) assina os envelopes da instalação, mas o relay não tem chave própria. Spec: `docs/superpowers/specs/2026-11-13-heycode-relay-mvp.md` §3. Modelo de ameaça: `docs/security/threat-model.md`.

## Decisão

- Correlação: o `id` do envelope do pedido (UUIDv7) é o `request_id`. A máquina responde com um envelope assinado cujo payload traz `in_reply_to` com esse id. Campo opcional novo no payload: não sobe a versão do protocolo. O relay só resolve um pedido se a resposta vier da mesma instalação que o recebeu; resposta de outra instalação é ignorada.
- Quadros do relay para a máquina (`instruction`, ack de `status`) usam o mesmo envelope com `sig` vazio no MVP. A conexão é de saída da máquina por TLS e foi autenticada pelo handshake assinado; o relay já é quem entrega as instruções, então um relay comprometido já poderia forjar pedidos, com ou sem assinatura. Chave própria do relay e assinatura nesse sentido ficam como endurecimento da P6.
- Rejeitado: assinar os quadros com chave compartilhada do relay (mais um segredo sem proteger contra o relay comprometido) e campo de correlação obrigatório (quebraria v1).

## Consequências

Resposta atribuída com segurança e sem mudar de versão. Custo: o cliente local deve confiar no TLS do endereço configurado, então precisa validar certificado e nunca aceitar um relay arbitrário sem configuração explícita.
