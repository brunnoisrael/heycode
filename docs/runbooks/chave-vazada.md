# Runbook: chave vazada

## Chave privada de uma instalação (computador)

1. A pessoa dona revoga a instalação no app (`DELETE /v1/installations/{id}`): o relay fecha a conexão e recusa qualquer envelope dali em diante.
2. No computador: `heycode pair CÓDIGO --relay URL --force` gera identidade nova.
3. Verifique o `request_log` da conta por pedidos que a pessoa não reconhece.

## Senha ou sessão de conta

1. Encerrar sessões da conta (logout) e redefinir a senha (recuperação de conta é pré-requisito da P6).
2. Revogar as instalações suspeitas.

## Segredos da ponte do dono (`BRIDGE_SECRET`, controle)

`heycode rotate-secret --apply` e `--control --apply`, e atualizar hooks, MCP e Lambda (docs/OPERATIONS.md).

## Banco do relay exposto

Tratar como incidente de segurança: hashes de senha (Argon2id) e de token de sessão estão no banco; invalide todas as sessões, force troca de senha e avise as pessoas afetadas (LGPD).
