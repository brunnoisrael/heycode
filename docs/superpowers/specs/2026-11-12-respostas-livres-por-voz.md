# Respostas livres por voz para o agente

Data: 2026-11-12. Status: aprovada pelo dono em 2026-11-12 ("pode executar os planos e evoluir").

## Problema

Hoje `pedir_decisao` recebe apenas sim ou não. Uma pergunta como “Qual biblioteca você prefere?” não tem resposta útil por voz. Aprovações de comandos compartilham a fila de pendências, portanto uma resposta livre precisa ficar vinculada à pergunta apresentada e não pode aprovar comandos.

## Experiência proposta

1. O agente chama uma nova ferramenta MCP `pedir_resposta(question, agent, project)`.
2. Ao consultar pendências, o dono ouve a pergunta e pode dizer “responder”. A Alexa pede a resposta em um segundo turno.
3. A Alexa relê a transcrição mascarada e pede confirmação. “Confirma” entrega o texto; “cancela” o descarta e mantém a pergunta pendente até expirar.
4. A ferramenta devolve `answer` com o texto confirmado, ou `null` se o prazo terminar ou a ponte reiniciar.

O texto é uma instrução do dono para o agente, não uma aprovação de ferramenta. O agente continua responsável por aplicar a política a qualquer ação decorrente. A ferramenta existente `pedir_decisao` conserva seu contrato e o comportamento do modo auto.

## Requisitos

- Usar o ID da pergunta ouvido na sessão em todas as etapas; recusar confirmação se ela expirou, foi resolvida ou deixou de ser a pendência apresentada. Nunca redirecionar a resposta para outra pergunta.
- A pergunta livre tem tipo próprio na fila; `/pending` identifica o tipo e anuncia a pergunta como pergunta, sem dizer que é um comando. A resposta livre nunca resolve uma aprovação Bash ou `pedir_decisao`.
- Limitar resposta a 300 caracteres, rejeitar texto vazio e aplicar a máscara de segredos em toda fala e log. Entregar ao agente o texto original confirmado; não registrar seu conteúdo em logs.
- Confirmar explicitamente a transcrição antes da entrega. Usar credencial de controle e a allowlist existente da Lambda. Uma confirmação de outro fluxo não pode entregar essa resposta.
- Consumir resposta e resolver pendência atomicamente; confirmação repetida, concorrente ou após expiração não entrega duas vezes. Ao reiniciar, pendências em andamento expiram como hoje.
- Sem resposta, a ferramenta retorna no prazo configurado e não bloqueia indefinidamente. No modo auto, perguntas abertas ainda aguardam o dono: não há resposta livre que possa ser inferida automaticamente.
- Preservar aprovações existentes, seus requisitos de PIN e a regra `NEVER_BY_VOICE` fora do modo auto. Não enfraquecer a allowlist da Lambda.
- O modelo Alexa usa diálogo em dois turnos para a frase livre e segue as restrições existentes de `AMAZON.SearchQuery`. O fluxo deve informar quando a sessão ou pergunta já não estiver disponível.

## Fora do escopo

Respostas livres para aprovações de comandos, interpretação por modelo de linguagem, múltiplos usuários e alteração das regras do modo auto para comandos.

## Verificação

- Testes da ponte e MCP para resposta confirmada, prazo, reinício, ID obsoleto, concorrência e incompatibilidade com aprovações.
- Testes da Lambda e do modelo para os dois turnos, releitura, confirmação, cancelamento, sessão ausente e máscara.
- Build do modelo no console Alexa e ensaio com a skill e ponte reais, quando disponíveis; testes locais não comprovam o reconhecimento de voz.
