# Como contribuir com o HeyCode

Todo o código deste projeto é produzido por agentes, e pessoas também podem contribuir. O processo é o mesmo para todos e está em [`docs/SDLC.md`](docs/SDLC.md).

## Em resumo

1. Abra uma issue descrevendo o problema, quem é afetado e o risco.
2. Mudança de comportamento começa por uma **spec** em `docs/superpowers/specs/`. Ela só vale com `Status: aprovada`, dado por uma pessoa mantenedora.
3. Mudança de arquitetura exige um **ADR novo** em `docs/adr/` (use `docs/adr/0000-template.md`).
4. Escreva o plano, depois o teste que falha, depois o código mínimo.
5. Commits no formato `tipo: descrição` (`feat|fix|docs|chore|test|refactor`); `feat`, `fix`, `test` e `refactor` levam o trailer `Spec: docs/superpowers/specs/<arquivo>.md`.
6. Prepare cada entrega em branch atualizada com `main`, sem PR, com até 400 linhas adicionadas (sem docs e travas). Inclua `## Evidência` e um bloco com comando e saída reais na mensagem do commit final.
7. Confira o CI e o parecer independente para o SHA exato antes de integrar na `main`; se algum check ou o revisor não estiver configurado, a entrega fica pendente.

## Ambiente

```bash
python -m pip install -r requirements-dev.txt -e . -c constraints.txt
git config core.hooksPath .githooks   # uma vez por clone
python -c "import heycode; print(heycode.__file__)"  # confirme o checkout instalado
python -m pytest
```

O pytest prioriza `src/` do checkout atual, mesmo se outra cópia editável estiver instalada. Para os demais comandos Python, use um ambiente virtual próprio e confirme o caminho impresso acima.

## Integração sem PR

O fluxo ainda precisa ser ativado no remoto: configure `INDEPENDENT_REVIEWER` com o login da conta revisora independente e acrescente `evidencia` e `revisao-independente` aos checks obrigatórios da `main`, mantendo os checks existentes. Não integre antes de validar a configuração e os checks no mesmo SHA.

A conta revisora, depois de examinar o diff e os resultados, publica para o SHA exato um status GitHub com contexto `heycode-review` e estado `success`. A API identifica a conta que publicou o status; autoria e revisão precisam usar contas diferentes. O CI falha sem parecer válido. Depois de publicado o parecer, execute novamente os jobs que falharam. Se a `main` avançar, atualize a branch e repita a revisão e os checks para o novo SHA.

Os hooks locais falham cedo, mas o CI refaz tudo; contorná-los (`--no-verify`) não adianta e não é aceito.

## O que exige aprovação humana

Só a aprovação da spec (`Status: aprovada`). O parecer independente para o commit é emitido fora de PR conforme o ADR 0064; não há aprovação humana ou por bot em PR (ADR 0061).

## Segurança

Nunca coloque segredos em código, logs, issues ou PRs. Vulnerabilidades: veja [`SECURITY.md`](SECURITY.md).
