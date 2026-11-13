# Runbook: domínio quase expirando

`heycode.dev.br` sustenta o relay, a skill e o account linking; se expirar, o produto para.

1. Renovação automática e trava de domínio ligadas no registrador; renovar por vários anos.
2. **Segundo administrador** no registrador com acesso para renovar sem o dono.
3. Alerta de expiração 60, 30 e 7 dias antes, para dois e-mails diferentes.
4. Se já expirou: renovar no período de carência do registrador; os DNS voltam sozinhos. Não troque o endereço da skill (exige nova certificação).
