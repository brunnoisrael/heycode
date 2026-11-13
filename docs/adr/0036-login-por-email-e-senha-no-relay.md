# 0036. Login por e-mail e senha no relay (MVP)

## Status

Aceito. Data: 2026-11-13.

## Contexto

Contas são necessárias para pareamento e roteamento. Spec: `docs/superpowers/specs/2026-11-13-heycode-relay-mvp.md` §4 e §8 (decisão 2).

## Decisão

- Cadastro por e-mail e senha; hash Argon2id (`argon2-cffi`). Senha mínima de 10 caracteres.
- Sessão por token opaco aleatório de 256 bits, guardado só como hash SHA-256 no banco, validade de 12 horas, revogável.
- Resposta de login idêntica para e-mail inexistente e senha errada (sem enumeração) e limite de taxa por origem.
- A verificação de e-mail por link e provedores externos (Google, Amazon) ficam para depois; o account linking da Alexa (P4) usa esta conta.
- Rejeitado: provedor externo no MVP (dependência de terceiro antes de validar o produto); JWT (revogação mais difícil).

## Consequências

Sem dependência externa no início. Custo: o HeyCode passa a guardar hashes de senha e precisa de rotina de recuperação de conta antes da P6. Atualiza `docs/security/threat-model.md`.
