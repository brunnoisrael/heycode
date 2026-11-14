# 0060. Remove o gate de tamanho (G12)

## Status

Aceito. Data: 2026-11-14. Decisão do dono. Altera o ADR 0024 (esteira obrigatória) e torna sem efeito o ADR 0057 (exceção da integração inicial ao G12).

## Contexto

O G12 barrava PRs com mais de 400 linhas adicionadas (fora docs e travas). Na prática, cada entrega precisou ser fatiada em pilhas de quatro ou cinco ramos e PRs encadeados, o que atrasou muito o trabalho sem pegar defeito que os demais gates não pegassem. O dono pediu a remoção do gate em todos os lugares.

## Decisão

- O G12 sai de `enabled_gates`; `max_added_lines` e `size_exclude_globs` saem de `scripts/gates/gates.json`.
- `check_diff_size` sai de `scripts/gates/pre_commit.py`; o hook local deixa de avisar sobre tamanho e o CI (`ci_range.py`) deixa de medir o tamanho do intervalo.
- Os demais gates (G1–G8, G11, G13–G16) continuam iguais. O número G12 não é reaproveitado.

## Consequências

- Um PR pode reunir uma entrega inteira; a revisão independente (G15) e a aprovação humana (G11) passam a ser o único freio de tamanho.
- PRs grandes ficam mais difíceis de revisar. Fatiar continua sendo recomendado quando ajuda a revisão, mas não é obrigatório.
- Specs e planos antigos que citam o limite de 400 linhas ficam como registro histórico.
