# 0055. A imagem do relay copia o que o wheel embute

## Status

Aceito. Data: 2026-11-14.

## Contexto

A primeira instalação real do pacote de VM (ADR 0054) revelou duas falhas que os testes locais não pegaram: o `pyproject.toml` embute `scripts/gates` e `.githooks` no wheel (`force-include`, ADR 0025) e o `infra/Dockerfile` não os copiava, então `pip install .` quebrava com "Forced include not found"; e o `ufw` conflita com o `iptables-persistent` que as imagens da Oracle trazem (no Ubuntu 24.04 o `ufw` declara `Breaks`).

## Decisão

- O `Dockerfile` do relay passa a copiar `scripts/gates` e `.githooks` junto de `src` e `protocol`. Rejeitado: remover o `force-include` só para o relay (o pacote instalável do dono precisa deles) e instalar com `--no-build-isolation` ou fora do wheel (esconde a divergência).
- `infra/vps/setup-server.sh` remove `iptables-persistent` e `netfilter-persistent` antes de instalar o `ufw`, esvazia a cadeia `INPUT` herdada e deixa o `ufw` como único dono do firewall (22, 80 e 443).
- Regra de processo: pacote de infraestrutura só conta como validado depois de rodar numa máquina real; o README registra o que foi conferido.

## Consequências

A imagem constrói e o servidor sobe com firewall previsível. Custo: o `Dockerfile` acompanha o `force-include` (se o `pyproject` embutir outra pasta, a imagem precisa copiá-la; vale um teste de construção no CI quando houver Docker no pipeline).
