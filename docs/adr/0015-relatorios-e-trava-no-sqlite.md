# 0015. Relatórios e trava de PIN no SQLite

## Status

Aceito. Data: 2026-11-10.

## Contexto

A revisão final (`docs/superpowers/specs/2026-11-10-revisao-final.md`, achados M5, B6 e B1) mostrou três estados vivendo só em memória: a lista `_unreported` (fim de ciclo ainda não falado), o dicionário `_summaries` (resumo do transcript, necessário porque cada evento regravava a sessão) e o dicionário `lock` (erros de PIN e bloqueio). Um reinício da ponte (tarefa agendada, falha, deploy) apagava o aviso de fim de ciclo e **zerava a trava de PIN**, o que permitia a quem erra o PIN reiniciar a contagem. Spec: `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`. Complementa o ADR 0003 (estado em SQLite).

## Decisão

- `runs.reported INTEGER NOT NULL DEFAULT 1`: `0` significa "fim de ciclo ainda não falado". O fim de uma execução com `report_on_end` ligado grava `0`; `/result` grava `1` ao falar. Bancos antigos recebem a coluna por `ALTER TABLE` no startup. Execuções `interrompida` nunca geram aviso (o startup as marca `reported=1`, e `first_unreported` as ignora).
- O resumo do transcript é gravado em `sessions.summary` e **não é sobrescrito** pelos eventos seguintes: `upsert_session` usa `COALESCE(novo, antigo)`, e o servidor só passa resumo no `Stop`.
- Tabela `pin_lock` (linha única: `fails`, `until`) guarda a trava de PIN; `/decide` lê e grava via `Store`.
- `POST /runs/latest/cancel` (segredo de controle) cancela a execução `rodando` mais recente por `Supervisor.cancel` e responde `{"speech"}`; registrada antes de `/runs/{run_id}` para não ser capturada como id.
- Alternativa rejeitada: arquivo JSON separado para a trava. Um segundo mecanismo de persistência não traz ganho sobre o SQLite que a ponte já usa.

## Consequências

- Aviso de fim de ciclo, resumo e trava de PIN sobrevivem a reinício; o aviso não se repete depois de lido.
- Reiniciar a ponte deixou de ser um jeito de zerar a trava de PIN.
- Toda leitura de `/pending` e `/decide` passa a fazer uma consulta ao banco (custo desprezível neste volume).
- O esquema ganhou uma migração leve; novas colunas devem seguir o mesmo padrão (`PRAGMA table_info` + `ALTER TABLE`).
