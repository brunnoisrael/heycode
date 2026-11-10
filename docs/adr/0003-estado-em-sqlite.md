# 0003. Estado da ponte em SQLite

## Status

Aceito. Data: 2026-11-09.

## Contexto

Até a fase 1 a ponte guardava sessões e aprovações em dicts em memória. Um reinício perdia políticas, histórico e o estado das aprovações, e o motor de políticas (spec §2 G1/G2, §7, §10) precisa de configuração por agente e projeto que sobreviva a reinícios. A ponte roda como processo único numa máquina pessoal, sem infraestrutura adicional.

## Decisão

Usar SQLite (módulo `sqlite3` da stdlib) por meio de `bridge/store/db.py`, com as tabelas `policy`, `sessions`, `approvals` e `history`. A conexão usa `check_same_thread=False` protegida por um lock. O arquivo é definido por `BRIDGE_DB` (padrão `bridge/bridge.db`). A política é resolvida por campo, com precedência agente+projeto > projeto > agente > global. Na subida, as aprovações pendentes viram `expired` (sem reanexar).

Alternativas rejeitadas: dicts em memória (perdem tudo no reinício, sem histórico) e Postgres (exige servidor extra e operação, desproporcional para um único processo local).

## Consequências

Persistência sem dependência nova e testes rápidos com `:memory:`. O acesso é serializado por um lock, suficiente para a carga esperada. Limita a ponte a uma instância por arquivo; escalar para várias instâncias exigiria outro armazenamento. O arquivo `.db` guarda comandos aprovados e deve ficar fora do versionamento.
