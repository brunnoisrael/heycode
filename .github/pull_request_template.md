## O que muda e por quê

<!-- Uma ou duas frases. Qual problema, para quem. -->

## Rastreabilidade

- Spec aprovada: `docs/superpowers/specs/...`
- Plano e tarefa: `docs/superpowers/plans/...` (uma tarefa por PR)
- ADR novo (se mudou arquitetura): `docs/adr/NNNN-...`

## Evidência

<!-- G16: cole a saída REAL dos comandos (testes, gates, lint). Sem saída colada, o PR é bloqueado. -->

```
$ python -m pytest -q
```

## Checklist

- [ ] Testes novos para o comportamento, vistos falhar antes de passar
- [ ] Docs e `CHANGELOG.md` atualizados quando há mudança visível
- [ ] Não toquei gates, workflows, `AGENTS.md`, `.claude/` ou CODEOWNERS (ou há pedido humano explícito)
- [ ] Nenhum segredo em código, log ou texto deste PR
