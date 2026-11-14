# Como contribuir com o HeyCode

Todo o código deste projeto é produzido por agentes, e pessoas também podem contribuir. O processo é o mesmo para todos e está em [`docs/SDLC.md`](docs/SDLC.md).

## Em resumo

1. Abra uma issue descrevendo o problema, quem é afetado e o risco.
2. Mudança de comportamento começa por uma **spec** em `docs/superpowers/specs/`. Ela só vale com `Status: aprovada`, dado por uma pessoa mantenedora.
3. Mudança de arquitetura exige um **ADR novo** em `docs/adr/` (use `docs/adr/0000-template.md`).
4. Escreva o plano, depois o teste que falha, depois o código mínimo.
5. Commits no formato `tipo: descrição` (`feat|fix|docs|chore|test|refactor`); `feat`, `fix`, `test` e `refactor` levam o trailer `Spec: docs/superpowers/specs/<arquivo>.md`.
6. Prepare cada entrega em branch atualizada com `main`, sem PR.
7. Confira os gates e testes do CI para o SHA exato antes de integrar na `main`. A evidência é registrada automaticamente no CI.

## Ambiente

```bash
python -m pip install -r requirements-dev.txt -e . -c constraints.txt
git config core.hooksPath .githooks   # uma vez por clone
python -c "import heycode; print(heycode.__file__)"  # confirme o checkout instalado
python -m pytest
```

O pytest prioriza `src/` do checkout atual, mesmo se outra cópia editável estiver instalada. Para os demais comandos Python, use um ambiente virtual próprio e confirme o caminho impresso acima.

## Integração sem PR

O CI executa os gates técnicos e a matriz no SHA da branch. Se a `main` avançar, atualize a branch e repita o CI para o novo SHA. Integre por avanço linear após os checks; não são exigidos PR, conta revisora ou assinatura de commit.

Os hooks locais falham cedo, mas o CI refaz tudo; contorná-los (`--no-verify`) não adianta e não é aceito.

## O que exige aprovação humana

Só a aprovação da spec (`Status: aprovada`). Não há aprovação humana ou por bot em PR (ADR 0061) nem conta revisora obrigatória (ADR 0064).

## Segurança

Nunca coloque segredos em código, logs, issues ou PRs. Vulnerabilidades: veja [`SECURITY.md`](SECURITY.md).
