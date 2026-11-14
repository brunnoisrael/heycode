# 0057. Exceção limitada para a integração inicial

## Status

Aceito. Data: 2026-11-13.

## Contexto

O histórico aprovado para integração antecede a aplicação do teto de 400 linhas por alteração. A spec `docs/superpowers/specs/2026-11-13-ajuste-integracao-inicial.md` autoriza uma única integração desse histórico, sem dispensar os outros controles.

## Decisão

Para a base exata `f9e28f2a315160d2c858aa429503381197616445`, se o commit `d01915d62dc0025e676f274b7ce80c01aa16809c` for ancestral do candidato, o G12 mede as adições posteriores a esse commit. Qualquer outra base ou histórico continua sujeito ao teto integral. Os demais gates aplicam-se a toda a integração. Remover a exceção após a integração.

## Consequências

O histórico é integrado de uma vez, com uma alteração de tamanho maior para revisão. Não existe opção genérica de ignorar o teto; mudanças posteriores continuam limitadas. Testes e varreduras continuam obrigatórios.
