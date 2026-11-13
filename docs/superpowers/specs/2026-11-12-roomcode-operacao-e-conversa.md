# RoomCode: conexão estável e conversa para desenvolvimento

Data: 2026-11-12. Status: aprovada pelo dono em 2026-11-12 ("agora pode evoluir o que der de paralelo").

## Objetivo

Permitir que o dono inicie e acompanhe trabalho de desenvolvimento por voz, com endereço estável, recuperação após reinício e um diálogo que acompanhe projeto, agente e execução. A primeira entrega atende um dono, um computador e o Echo já autorizado. Não pressupõe que a Alexa ou um agente permaneçam conectados continuamente.

## Situação atual

- O túnel rápido recebe outra URL quando reinicia; a Lambda precisa ser atualizada manualmente. A tarefa da ponte inicia no logon, mas o túnel rápido não tem ciclo de vida equivalente.
- Já existem criação de projeto, supervisor, fila para Claude aberto, políticas, perguntas abertas e histórico em SQLite. `/runs/latest` e o cancelamento mais recente não apresentam a lista completa; a fila para agente aberto depende de cooperação do adaptador.
- O modelo de voz tem frases e fluxos fixos. `AMAZON.SearchQuery` tem restrições de combinação com outros slots; diálogos em vários turnos são necessários em alguns casos. A resposta aberta atualmente depende do prazo de aprovação existente, curto para uma conversa.
- No Echo, a abertura explícita “abra a skill meu agente” e a pergunta em seguida funcionaram. O simulador tem outro ID de dispositivo e é recusado pela allowlist existente.

## Experiência desejada

1. Ao iniciar o computador e entrar na conta Windows, ponte e conector recuperam a operação sem atualizar a Lambda. Diagnóstico distingue serviço local, DNS/túnel, Alexa, credenciais e agente. A URL fixa é configurada uma vez.
2. “Quais projetos estão ativos?” apresenta uma lista curta de projetos com execuções ou sessões recentes, seus agentes e estados. “Mais” continua a lista; “abra o painel” escolhe um projeto, sem alterar arquivos.
3. “No painel, peça ao Codex para corrigir o login” seleciona destino, coleta os campos faltantes e relê o pedido. Depois de confirmação explícita, inicia uma execução e informa identificação curta. Se o reconhecimento não permitir todos os campos na mesma frase, a skill pede apenas os ausentes.
4. “Como está?” usa o projeto selecionado; se houver mais de uma execução possível, pede a escolha. “O que ele fez?” informa resultado disponível e quando foi atualizado; não inventa progresso.
5. “Avise o agente: considere o fluxo mobile” prepara uma instrução para uma sessão compatível e explica quando será entregue. Se não houver sessão elegível, oferece iniciar uma nova execução após confirmação. Não promete interromper o turno atual.
6. “Crie um projeto” coleta nome, descrição e agente, confirma e usa o scaffold existente. “Inicie outro agente neste projeto” cria uma execução supervisionada; em fase posterior, perfis nomeados permitem escolher agente e instruções iniciais. Não cria contas, instala software ou altera configuração do agente implicitamente.
7. “O que precisa de mim?” apresenta pendências com projeto e agente. Perguntas abertas permitem resposta ditada, releitura e confirmação, vinculadas ao pedido original. Aprovações conservam o PIN e as regras de política existentes.
8. “Pare o agente do painel” identifica e confirma a execução quando houver ambiguidade. Cancelamento nunca escolhe silenciosamente entre várias execuções.

## Requisitos de operação

- Usar Cloudflare Tunnel nomeado com hostname próprio estável, DNS na conta do dono e `cloudflared` como serviço/tarefa persistente; hospedar a ponte apenas em loopback. O domínio e o método de login dependem da conta disponível. Nenhum túnel rápido é promovido a solução estável.
- Instalação idempotente e revisável: detectar configuração existente, apresentar mudanças antes da aplicação, não substituir um serviço ou DNS não relacionado e não exibir tokens. Reinstalação e rollback documentados; separar configuração e segredos de logs.
- Verificar reconexão após interrupção de rede, reinício do processo e logon. Diferenciar pronto localmente, túnel conectado e teste externo autenticado; `/health` público não deve vazar estado privado. Nunca reiniciar execução ou aprovar pedido por causa de recuperação automática.
- Manter credenciais separadas de agente e controle e a allowlist existente de usuário e dispositivo, sem afrouxá-la. O simulador é tratado separadamente, sem autorizar todos os dispositivos. Modo auto continua como definido no ADR 0002.
- Oferecer diagnóstico seguro com estado e horário, sem imprimir PIN, tokens, URLs com credenciais, prompts ou saídas brutas. Logs operacionais devem correlacionar requisição, intenção e resultado sem conteúdo sensível; retenção limitada configurável.

## Contratos do diálogo e dos dados

- Identificar cada projeto por chave estável e caminho resolvido sob `PROJECTS_ROOT`. Listagem não expõe caminhos completos, segredos ou conteúdo arbitrário. Ordenar por atividade mais recente e paginar; limitar o tamanho da fala.
- Sessões ativas de hooks/MCP e execuções do supervisor têm fontes e estados distintos. Informar origem e frescor; se a sessão estiver velha ou o estado não puder ser provado, dizer “última atividade” em vez de “rodando”. Várias execuções no mesmo projeto são identificadas por ID e agente.
- O contexto de voz contém projeto, agente, execução e operação pendente; é vinculado à sessão Alexa, com validade definida e tratamento de reinício e perda de contexto. Valores não confirmados nunca executam ações. Pedidos de criar projeto, iniciar execução, enviar instrução e responder pergunta usam confirmação vinculada à operação e ao destino originais, com consumo atômico e proteção contra duplicatas.
- Consultas de status/listagem são somente leitura. Resultados e contexto ditado são resumidos e mascarados antes de fala; o texto completo confirmado só é entregue ao destino escolhido. Em caso de falha de reconhecimento ou ambiguidade, pedir esclarecimento.
- O diálogo aceita interrupção e retomada quando o canal e o adaptador realmente suportarem. Claude aberto recebe pelo mecanismo já existente; suporte real a Codex/Aider depende de capacidades verificadas, com mensagem honesta quando indisponível.
- A primeira fase usa intents e diálogo explícitos, sem criar dependência de modelo externo. Uma camada opcional de linguagem poderá propor intenção e entidades em fase posterior, com esquema validado, limite de tempo e fallback determinístico. Ela não executa ações, decide políticas nem interpreta conteúdo do repositório como instrução; custo, provedor e envio de dados exigem decisão separada antes de ativação.
- Limitar prompts e capturas conforme capacidades reais da Alexa, oferecendo divisão em turnos sem prometer ditado ilimitado. A viabilidade de fala livre, duração das sessões e suporte a slots deve ser confirmada no console e em Echo real antes de declarar a função concluída.

## Entregas e critérios de aceite

1. **Conectividade:** URL estável, conector e ponte recuperam após reinício/logon; chamada autenticada externa funciona; operação de voz funciona após reboot sem deploy novo da Lambda. Se faltar domínio ou credencial, deixar provisionamento preparado e relatar a dependência sem interromper a ponte existente.
2. **Visibilidade:** listar projetos ativos e execuções, navegar páginas e escolher contexto; estados desatualizados e indisponíveis são informados corretamente. Testes cobrem concorrência, paginação, projeto inexistente e restrição de caminho.
3. **Trabalho:** criar projeto, iniciar agente, ditar prompt, acompanhar, enviar contexto e cancelar a execução certa; confirmação, expiração, repetições e casos ambíguos cobertos por testes e ensaio de voz.
4. **Conversa:** respostas curtas e naturais, perguntas somente para campos ausentes, retomada explícita, perguntas abertas com prazo apropriado e confirmação. Validar modelo no Alexa Developer Console e no Echo; simulador não substitui Echo.
5. **Operação:** documentação, verificação de saúde, recuperação e logs seguros; medir tempo de resposta e registrar os limites reais das integrações. Nenhuma garantia de disponibilidade percentual sem observação e infraestrutura adequadas.

## Fora do escopo inicial

Multiusuário, múltiplas máquinas, publicação na loja, agentes arbitrários instalados automaticamente, compartilhamento de credenciais e interpretação por modelo externo ativada por padrão.

## Referências

- Cloudflare: https://developers.cloudflare.com/tunnel/get-started/ e https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/dns/
- Alexa: https://developer.amazon.com/en-US/docs/alexa/custom-skills/dialog-interface-reference.html e https://www.developer.amazon.com/en-US/docs/alexa/custom-skills/slot-type-reference.html
