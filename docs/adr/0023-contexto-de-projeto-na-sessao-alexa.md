# 0023. Contexto de projeto na sessão Alexa

## Status

Aceito. Data: 2026-11-12.

## Contexto

A spec `docs/superpowers/specs/2026-11-12-roomcode-operacao-e-conversa.md` pede que o dono encontre projetos ativos e continue trabalhando em um deles sem repetir o nome em cada turno. A Alexa pode perder o contexto ao encerrar a sessão.

## Decisão

A skill consulta a ponte para listar atividades e resolver o nome de projeto. A escolha validada fica nos atributos da sessão Alexa; status e novos ditados usam esse projeto, salvo quando o dono fornece outro explicitamente. A paginação usa o offset devolvido pela ponte. Fora da sessão, não existe projeto implícito persistente. A seleção desconhecida limpa o contexto e não encaminha tarefas à raiz.

## Consequências

O contexto reduz a repetição no diálogo e permanece isolado por sessão. Após seu encerramento, o dono escolhe novamente. A habilidade de identificar um projeto falado continua sujeita ao reconhecimento dos slots da Alexa e deve ser verificada no console e no Echo. Selecionar um projeto não inicia nem modifica arquivos.
