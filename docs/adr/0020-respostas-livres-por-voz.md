# 0020. Respostas livres por voz

## Status

Aceito. Data: 2026-11-12.

## Contexto

A spec `docs/superpowers/specs/2026-11-12-respostas-livres-por-voz.md` prevê respostas abertas a perguntas de agentes, sem confundi-las com aprovações de comandos.

## Decisão

Usar a fila de aprovações com tipo distinto para ordenar as perguntas junto das demais pendências. A ponte guarda a transcrição em memória e entrega um token à sessão Alexa; a confirmação consome esse token e usa uma operação condicional no SQLite, vinculada ao ID e ao prazo da pergunta. A ferramenta MCP retorna o texto ou ausência de resposta. Perguntas abertas aguardam mesmo no modo auto.

## Consequências

O fluxo reutiliza a ordem e a expiração da fila existente, mas exige distinguir rigorosamente os tipos e garantir atualização atômica. A resposta no banco contém o texto original; as falas usam a máscara de segredos. Reinícios expiram perguntas pendentes e descartam transcrições não confirmadas.
