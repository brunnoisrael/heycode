# 0049. Rota de leitura do rastro na ponte local

## Status

Aceito. Data: 2026-11-13.

## Contexto

O ADR 0047 manda buscar o detalhe do rastro no próprio computador. A ponte local guarda aprovações e execuções no SQLite (`approvals`, `runs`), mas nenhuma rota as lista. Spec: `docs/superpowers/specs/2026-11-13-heycode-painel-web-rastro-e-comandos.md` §4.

## Decisão

- Nova rota `GET /voice/audit?limit=` com o segredo de controle, **somente leitura**, limite padrão 20 e máximo 50. Devolve aprovações (`id, agent, project, tool, command, decision, t`) e execuções (`id, agent, project, status, summary, t_start, t_end`), mais recentes primeiro, com `mask_secrets` e corte de 200 caracteres. Decisão ainda aberta aparece como `pending`.
- O store ganha `recent_approvals` e `recent_runs`, que **nunca** selecionam a coluna `answer`; para perguntas abertas (`pedir_resposta`) a rota também omite o texto do comando.
- A rota entra na lista fechada do executor local (ADR 0045) com a única chave de consulta `limit`.
- Rejeitado: expor o banco inteiro ou rotas de escrita (poder amplo) e devolver a resposta livre (pode conter segredo).

## Consequências

O painel mostra o que a voz aprovou sem o relay guardar conteúdo. Custo: toda rota a mais usada por voz ou painel exige atualizar a lista do executor e seus testes.
