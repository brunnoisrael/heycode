# HeyCode: roadmap do controle de agentes por voz

Estado deste documento: visão e prioridades de produto, não um plano de implementação aprovado. Atualizado em 2026-11-13.

## Visão

HeyCode é uma Alexa com uma skill que governa o trabalho de agentes de código. A pessoa desenvolvedora fala naturalmente, acompanha projetos e sessões, dá contexto, responde decisões e recebe resultados sem precisar decorar comandos. Quando voltar ao computador, encontra as execuções, decisões e evidências organizadas.

O produto deve ser agnóstico a agentes: Claude Code, Codex, Aider e outros entram por adaptadores e declaram suas capacidades reais. A experiência de voz permanece consistente; o sistema deixa claro quando um agente não suporta uma operação.

Exemplo de um dia de trabalho:

> “Alexa, abra o HeyCode. Quais projetos estão ativos?”
>
> “No painel, peça ao Codex para corrigir o login. Considere o erro que vimos ontem.”
>
> “Como está? Precisa de mim?”
>
> “O que mudou? Mostre os testes e o que ficou pendente.”

As frases são metas de experiência. O nome de invocação e o reconhecimento dependem da configuração e validação real da Alexa.

## Ponto de partida

- Ponte local FastAPI, políticas e estado SQLite; MCP, hooks Claude e supervisor para Claude Code, Codex e Aider.
- Skill de desenvolvimento com status, aprovações, ditado confirmado, projeto novo, pergunta aberta e listagem/seleção de projetos recentes ou em execução.
- Túnel nomeado em `ponte.heycode.dev.br`; ponte e túnel iniciam no logon. A confirmação por Echo após a troca de endereço e o teste completo após reinício continuam pendentes.
- Playwright MCP instalado para o Codex deste usuário como ferramenta de desenvolvimento e validação do HeyCode.
- Limites atuais: contexto de projeto vive na sessão de voz; algumas confirmações ainda usam pendência global; a lista distingue execução supervisionada de atividade recente e pode mudar entre páginas; adaptadores oferecem capacidades diferentes.

## Princípios de produto

1. **Voz útil, não roteiro:** reconhecer variações, lembrar o contexto da conversa e perguntar apenas o que falta. Ler respostas curtas primeiro e oferecer detalhes depois.
2. **Nada de destino implícito quando houver dúvida:** identificar projeto, agente e execução. Uma confirmação vale para a operação e o destino apresentados.
3. **Agentes intercambiáveis com capacidades explícitas:** o usuário escolhe o agente ou aceita uma sugestão explicável; o HeyCode informa limitações antes de prometer uma ação.
4. **O computador continua sendo a fonte de trabalho:** código, histórico, testes e evidências permanecem acessíveis no projeto. A voz é uma interface para operá-los.
5. **Observabilidade honesta:** diferenciar em andamento, aguardando, concluído, falhou, cancelado, interrompido e último sinal recebido. Nunca inventar progresso nem dizer que um processo está vivo só porque deixou uma sessão recente.
6. **Política e privacidade preservadas:** manter a allowlist do dono e do dispositivo, separação de credenciais e resumo com máscara antes de falar. O modo `auto` continua com o comportamento integral definido no ADR 0002; nos demais modos aplicam-se as políticas existentes.
7. **Operar sem atrapalhar o fluxo:** instalação reproduzível, recuperação após falhas e hooks/adaptadores que falham abertos quando a ponte não estiver disponível.

## M0 — Fazer o caminho atual ser confiável

**Meta:** o dono consegue usar a skill todos os dias sem manutenção manual de endereço.

- Validar no Echo real status e projetos pelo endereço fixo, inclusive depois de reiniciar o computador e fazer logon.
- Exercitar queda de rede, reinício da ponte e do conector, e recuperação com diagnóstico que distingue Alexa, DNS, túnel, autenticação, ponte e agente.
- Associar confirmação ao ID da operação e ao destino no backend; expirar, cancelar e consumir atomicamente. Eliminar conflitos entre sessões e solicitações antigas.
- Padronizar logs sem segredos, alertas de indisponibilidade e instruções de recuperação. Definir testes de aceitação no aparelho, sem declarar disponibilidade percentual sem medições.

**Pronto quando:** o ciclo de reinício e uma tarefa de teste passam do Echo ao agente e de volta, sem edição da Lambda e sem entregar uma confirmação a outro pedido.

## M1 — Entender o que está acontecendo

**Meta:** responder “o que está rodando e onde?” de forma útil.

- Listar projetos, agentes e execuções; distinguir execuções em andamento de sessões com atividade recente. Paginar com consistência e permitir filtrar por projeto, estado e agente.
- Selecionar projeto e execução; oferecer resumo, última atividade, decisões aguardando, resultado e próxima ação. Tratar nomes parecidos e várias execuções por projeto.
- Guardar contexto com prazo claro e permitir retomá-lo quando a sessão Alexa terminar, sem adivinhar o destino. Dizer quando uma informação estiver desatualizada.
- Criar visão complementar no computador para detalhes, histórico e evidências quando uma resposta não couber na voz.

**Pronto quando:** alguém consegue localizar uma execução entre vários projetos, entender seu estado e abrir os detalhes sem precisar lembrar IDs.

## M2 — Conduzir o trabalho por voz

**Meta:** criar, direcionar e acompanhar trabalho com poucos turnos.

- Criar projeto, escolher agente, ditar tarefa, revisar o entendimento e iniciar. Retomar um projeto existente e acrescentar contexto durante a execução quando o adaptador suportar.
- Iniciar outra execução no mesmo projeto, responder perguntas abertas, solicitar resumo, cancelar ou retomar a execução correta e pedir continuação após o resultado.
- Permitir instruções longas em partes e correções antes de confirmar; respeitar as restrições reais de tempo e reconhecimento da Alexa.
- Explicitar a diferença entre iniciar uma execução e enviar uma instrução a uma sessão já aberta. Não anunciar interrupção imediata se o adaptador só entrega no próximo ponto de cooperação.

**Pronto quando:** a jornada “projeto novo → tarefa → pergunta → contexto → resultado” funciona no Echo, com falhas e ambiguidades tratadas.

## M3 — Conversa natural e contexto de desenvolvimento

**Meta:** deixar de depender de frases rígidas sem perder controle sobre o que será executado.

- Ampliar expressões usuais, perguntas de esclarecimento, referências como “esse projeto” e “aquele agente”, e respostas que comecem pela informação mais útil.
- Criar resumos com fontes rastreáveis: tarefa atual, arquivos alterados, testes, bloqueios e decisões. Apontar ausência ou idade dos dados; não ler segredos ou saídas extensas.
- Avaliar uma camada opcional de linguagem para interpretar pedidos e resumir contexto, com contrato estruturado, prazo, custo visível, privacidade e fallback sem modelo. A camada propõe ações; as políticas e confirmações continuam no controle do HeyCode.
- Medir compreensão com frases reais em português, sotaques, nomes de projetos e termos de programação. Manter um conjunto de cenários e testes de regressão, além de ensaios no Echo.

**Pronto quando:** usuários conseguem cumprir jornadas representativas com linguagem variada e recuperação clara quando a Alexa entende errado.

## M4 — Agentes, comunidade e operação de produto

**Meta:** outras pessoas conseguirem instalar, adaptar e contribuir com confiança.

- Publicar contrato de adaptadores, catálogo de capacidades e perfis de agentes; validar instalação, atualização e diagnóstico em ambiente limpo.
- Oferecer guia de início, exemplos de frases, demonstração, roteiro de teste, documentação de segurança e contribuição. Esclarecer custos de domínio, infraestrutura e provedores de agentes.
- Criar uma interface de acompanhamento para projetos, histórico, políticas, resultados de testes e resolução de problemas, sem tornar a voz dependente dela para tarefas básicas.
- Estudar distribuição da skill e onboarding para a comunidade; antes de publicar, resolver consentimento, isolamento de contas/dispositivos, credenciais e requisitos da plataforma. Multiusuário e múltiplas máquinas exigem especificação própria.
- Avaliar integrações com repositórios, issues, revisões e entrega de software somente com ações identificadas e autorização adequada.

**Pronto quando:** uma pessoa externa instala em máquina limpa, conecta pelo menos dois agentes, executa um fluxo de voz e consegue diagnosticar uma falha usando a documentação.

## Como trabalhar neste roadmap

Os agentes que desenvolvem o HeyCode podem usar Playwright para validar o console da Alexa, fluxos web e outras interfaces quando adequado. Essa é uma ferramenta do processo de desenvolvimento; ela não constitui um recurso obrigatório ou eixo do produto.

Cada marco será dividido em especificações aprovadas, planos, código com testes e commits com o trailer exigido pelo repositório. Mudanças de arquitetura recebem ADR novo. O roadmap indica direção e ordem de aprendizado; não substitui essas aprovações nem garante suporte a uma capacidade que ainda não foi verificada.
