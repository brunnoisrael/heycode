# Níveis de apoio: ver pedidos e conceder

Decisão: ADR 0059. O relay não cobra nem registra pagamento. O nível de cada conta só muda por este comando, rodado no servidor; não existe rota HTTP para isso.

## Ver quem pediu para apoiar

```bash
cd /opt/heycode/infra/vps
docker compose exec relay python -m heycode.relay.grant interest
```

Mostra o e-mail, o nível desejado e o nível atual de cada conta que clicou em "Quero apoiar" no painel. Esse número é a medida de interesse antes de qualquer cobrança.

## Conceder ou retirar um nível

```bash
docker compose exec relay python -m heycode.relay.grant set pessoa@exemplo.com apoiador   # ou patrono
docker compose exec relay python -m heycode.relay.grant set pessoa@exemplo.com livre      # volta ao nível Livre
```

A mudança vale na hora e aparece no rastro da pessoa como "Nível de apoio concedido". Voltar ao nível Livre não apaga nada: quem está acima do limite só não consegue criar mais.

## Limites de cada nível

| Nível | Computadores | Atalhos | Pedidos por dia |
|---|---|---|---|
| Livre | 2 | 30 | `RELAY_DAILY_QUOTA` (200 por padrão) |
| Apoiador | 4 | 100 | 1000 |
| Patrono | 8 | 300 | 3000 |

Os valores ficam em `src/heycode/relay/plans.py`. As páginas `/` e `/apoie` repetem os números em texto; o teste `test_niveis_do_site_batem_com_os_do_relay` falha se ficarem diferentes.

## O que este fluxo não cobre

- Receber a contribuição: é combinado fora do sistema, por e-mail, com quem pediu.
- Efeito fiscal de receber contribuições recorrentes como pessoa física: avaliação do dono.
- Avisar a pessoa: o relay não envia e-mail.
