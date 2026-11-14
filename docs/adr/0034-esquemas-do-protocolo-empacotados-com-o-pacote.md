# 0034. Esquemas do protocolo empacotados com o pacote

## Status

Aceito. Data: 2026-11-13.

## Contexto

O ADR 0029 define os esquemas em `protocol/v1/` na raiz do repositório, como contrato visível para o relay e para revisão (G9). Mas o pacote instalado (`pipx install heycode`, ADR 0025) não contém a raiz do repositório, e o componente local precisa validar envelopes em tempo de execução. Spec: `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md` §3.

## Decisão

A fonte única continua sendo `protocol/v1/*.schema.json`. O build copia essa pasta para `heycode/_protocol/v1` (`force-include` do hatch) e `heycode.protocol` procura primeiro a cópia empacotada e, em desenvolvimento, a pasta da raiz do repositório. Não há segunda cópia versionada. Rejeitado: duplicar os esquemas dentro de `src/` (divergem) e embuti-los como dicionários Python (ilegíveis para o relay).

## Consequências

Um único arquivo por esquema, validado igual no repositório e no pacote instalado. Custo: o desenvolvimento em worktree precisa de `PYTHONPATH=src` ou instalação editável apontando para o worktree certo.
