# 0058. Cloudflare na frente e limites em camadas no relay

## Status

Aceito. Data: 2026-11-14. Complementa os ADRs 0037 (limites), 0040 (origem pelo `X-Forwarded-For`) e 0054 (VM com Compose e Caddy).

## Contexto

O relay roda numa VM gratuita de 1 GB exposta à internet. Antes desta decisão só login, cadastro e exclusão de conta tinham limite de taxa; rotas sem login, o WebSocket das máquinas e o endpoint da Alexa não tinham teto de taxa, de tamanho nem de conexões; o limitador guardava chaves para sempre; e cada cálculo de Argon2 (~64 MiB) podia rodar em paralelo sem limite. Uma VM desse porte não absorve ataque volumétrico: o tráfego a derruba antes de qualquer regra dela agir. Spec: `docs/superpowers/specs/2026-11-14-heycode-painel-rotas-e-borda.md`.

## Decisão

Proteger em quatro camadas, cada uma cobrindo o que a anterior não vê:

1. **Cloudflare (plano grátis) como proxy** dos nomes do relay. Ela absorve volume e esconde o IP da VM. O domínio já usa os servidores de nome dela.
2. **Firewall da VM**: 80 e 443 só aceitam as faixas da Cloudflare (`cloudflare-firewall.sh`, lista versionada em `cloudflare-ips.txt`). O filtro fica na cadeia `DOCKER-USER`, porque portas publicadas pelo Docker não passam pelas regras do `ufw`.
3. **Caddy**: só acredita no `CF-Connecting-IP` quando a conexão vem das faixas da Cloudflare (`trusted_proxies`), repassa ao relay um único IP em `X-Forwarded-For`, corta corpo acima de 256 KiB e solta conexões que não enviam o cabeçalho em 10 s.
4. **Relay**: guarda global de 240 pedidos/min por IP, banimento de 15 min para quem insiste, limites por rota, por e-mail e por conta, tetos de corpo e de campo, limites no WebSocket, no máximo 2 Argon2 simultâneos e memória limitada em todas as estruturas. O uvicorn e os contêineres ganham tetos de conexões, memória e processos.

Alternativas rejeitadas: só limites na VM (não segura volume e exigiria compilar o Caddy com plugin de taxa numa máquina fraca); só Cloudflare (quem descobre o IP de origem contorna tudo); baixar a lista de faixas a cada execução (o script passaria a depender de conteúdo remoto; a lista muda raramente e fica revisável no git).

## Consequências

- O dono precisa ligar o proxy nos registros DNS, usar TLS "Full (strict)" e aplicar o firewall na VM; o agente não tem acesso a nenhum dos dois. Até lá, só as camadas 3 e 4 valem.
- A lista de faixas existe em dois lugares (`cloudflare-ips.txt` e `Caddyfile`) e precisa ser atualizada junto. Se a Cloudflare acrescentar uma faixa e a lista ficar velha, parte dos visitantes recebe tempo esgotado; `cloudflare-firewall.sh remove` desfaz o filtro.
- Limites e banimentos ficam em memória e por processo (ADR 0035): reiniciar o relay os zera.
- O limite por e-mail permite a um atacante atrasar o login do dono em até 15 min; sessões já abertas não são afetadas. Aceito em troca de barrar força bruta distribuída.
- Usuários atrás do mesmo IP (CGNAT, escritório) dividem a cota de 240 pedidos/min; o painel usa poucos pedidos por tela.
- A Cloudflare passa a ver o tráfego em claro (ela termina o TLS). O conteúdo já é mínimo por desenho: o relay não guarda nem repassa comandos em texto além do que a voz pede.
- Não validado em VM real nesta entrega: `caddy validate` do novo Caddyfile, o script de firewall e a renovação do certificado atrás do proxy. O runbook em `infra/vps/README.md` traz a conferência de cada um.
