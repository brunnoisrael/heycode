# Fluxo centralizado sem PR

Data: 2026-11-14. Status: aprovada pelo dono em 2026-11-14.

## Objetivo

Usar o diretório principal do repositório como ponto de entrada para os agentes e integrar na `main` sem abrir PR. Evitar testes executados contra uma instalação editável de outro worktree. Preservar alterações e dados existentes ao retirar cópias antigas.

## Comportamento desejado

- Antes de trabalhar, verificar branch, alterações locais e origem do pacote Python. Não trocar de branch ou descartar alterações de outra tarefa.
- Instalar as dependências e o pacote editável no ambiente Python escolhido para o diretório de trabalho atual; confirmar `heycode.__file__` e executar os testes a partir dele.
- Worktrees temporários só quando necessários para isolamento; após a tarefa, retirar os que estiverem limpos e sem dados a preservar, mantendo as branches até a integração ser verificada.
- Uma entrega tem spec aprovada, plano, testes, ADR novo quando necessário e commit com os trailers exigidos. Não abrir PR.
- A integração direta na `main` deve ter uma verificação de CI e revisão independente equivalentes às exigências existentes, sem depender de evento, corpo ou revisão de PR. Não declarar uma entrega integrada antes de verificar esses resultados e as proteções reais do remoto.
- Registrar evidências e instruções de recuperação em um local acessível aos agentes, sem expor segredos.

## Aceite

1. O comando documentado de testes usa o código do diretório escolhido, mesmo após outro worktree ter sido instalado.
2. O fluxo de integração e seus checks funcionam sem PR e não reduzem os gates existentes.
3. As instruções de contribuição e operação concordam com o CI efetivamente configurado.
4. A remoção de worktree não perde alterações, arquivos não rastreados ou dados ignorados que precisem ser preservados.
