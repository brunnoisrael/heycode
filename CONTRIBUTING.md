# Como contribuir com o HeyCode

Todo o código deste projeto é produzido por agentes, e pessoas também podem contribuir. O processo é o mesmo para todos e está em [`docs/SDLC.md`](docs/SDLC.md).

## Em resumo

1. Abra uma issue descrevendo o problema, quem é afetado e o risco.
2. Mudança de comportamento começa por uma **spec** em `docs/superpowers/specs/`. Ela só vale com `Status: aprovada`, dado por uma pessoa mantenedora.
3. Mudança de arquitetura exige um **ADR novo** em `docs/adr/` (use `docs/adr/0000-template.md`).
4. Escreva o plano, depois o teste que falha, depois o código mínimo.
5. Commits no formato `tipo: descrição` (`feat|fix|docs|chore|test|refactor`); `feat`, `fix`, `test` e `refactor` levam o trailer `Spec: docs/superpowers/specs/<arquivo>.md`.
6. Um PR por entrega do plano, sem limite de linhas. Preencha a seção **Evidência** com a saída real dos comandos.

## Ambiente

```bash
python -m pip install -r requirements-dev.txt -e . -c constraints.txt
git config core.hooksPath .githooks   # uma vez por clone
python -m pytest
```

Os hooks locais falham cedo, mas o CI refaz tudo; contorná-los (`--no-verify`) não adianta e não é aceito.

## O que exige aprovação humana

Só a aprovação da spec (`Status: aprovada`). Os demais PRs passam pelo CI e pela revisão independente de um agente (`agent-review`); não há aprovação humana por caminho (ADR 0061).

## Segurança

Nunca coloque segredos em código, logs, issues ou PRs. Vulnerabilidades: veja [`SECURITY.md`](SECURITY.md).
