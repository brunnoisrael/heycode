# 0022. Visibilidade de projetos e atividades por voz

## Status

Aceito. Data: 2026-11-12.

## Contexto

A spec `docs/superpowers/specs/2026-11-12-roomcode-operacao-e-conversa.md` pede listagem de projetos, seleção e status sem expor prompts, caminhos ou segredos. Sessões de hooks não provam que um processo permanece ativo.

## Decisão

A ponte oferece rotas autenticadas de controle em `/voice/projects` para listar, resolver nome e consultar status. A listagem combina execuções supervisionadas em andamento com sessões atualizadas nos últimos 30 minutos, identificadas como atividade recente. Um snapshot do SQLite contém somente metadados necessários e é filtrado por diretórios imediatos da raiz configurada, com resolução de caminhos reais. A fala é mascarada e limitada a três projetos por página. Nomes normalizados ambíguos são recusados.

## Consequências

O dono pode distinguir trabalho supervisionado de atividade recente sem obter prompts ou caminhos. O modelo legado identifica projetos por nome de pasta: colisões normalizadas não são resolvidas automaticamente. A atividade de sessão é indicativa e não confirma que o processo ainda esteja aberto.
