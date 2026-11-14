# Plano: ecossistema de extensões do HeyCode

Spec: `docs/superpowers/specs/2026-11-14-heycode-ecossistema-de-extensoes.md` (rascunho aguardando confirmação humana). ADRs [0065](../../adr/0065-borda-por-cloudflare-tunnel-na-vm.md) e [0066](../../adr/0066-extensoes-risco-calculado-e-modelo-de-confianca.md): propostos. Este plano estabelece ordem e validações; não altera os ADRs.

## Visão e resultado desejado

O HeyCode deve tornar a Alexa uma assistente útil no dia a dia do desenvolvimento: acompanhar agentes e projetos, lembrar onde a pessoa parou, ajudar com decisões e apresentar resultados. Memória, revisão e economia ampliam essa experiência; mentor e lojinha permitem que a comunidade a adapte e compartilhe. O computador continua sendo o lugar do trabalho e dos dados locais; o relay conecta os componentes.

Entregar o conjunto por etapas, aprendendo com o uso real. A primeira meta não é encher uma loja, mas provar que uma extensão melhora uma jornada de voz, pode ser compreendida e controlada pela pessoa e não atrapalha os agentes quando a ponte cai. O catálogo comunitário vem depois dessa prova.

Cada fase de implementação depende de spec aprovada, plano executável, testes e ADR novo quando exigido pelas regras do repositório. As decisões abertas abaixo devem voltar à spec para aprovação antes do código correspondente. As entregas seguem o fluxo sem PR do ADR 0064; o CI registra os testes e as evidências relevantes.

## F0. Fundamentos de comandos e consentimento

- [ ] Reproduzir e testar os riscos atuais: script declarado como `leitura`, alteração de definição e tentativa de ativação por agente em `auto`.
- [ ] Definir e implementar o risco efetivo pelas capacidades, com o declarado apenas elevando o piso; aplicar também ao carregar comandos existentes e avisar a pessoa sobre migração e mudanças de risco.
- [ ] Comando novo ou alterado nasce desligado; vincular a ativação à definição exata e invalidá-la quando ela mudar.
- [ ] Especificar e testar confirmação independente do agente, vinculada à operação, identidade, hash e permissões apresentadas. Avaliar TTY, painel e voz com PIN conforme o risco, inclusive tentativas de automação pelo agente e corridas entre alteração e confirmação. Explicitar os limites quando um agente já controla a máquina.
- [ ] Instalação e ativação não aceitam resposta de `pedir_decisao` ou `pedir_resposta`, inclusive em `auto`. Delimitar essa regra para não alterar silenciosamente o comportamento geral do modo, definido no ADR 0002.
- [ ] Testar migração, expiração, repetição e concorrência das confirmações, além de preservar a falha aberta dos hooks e adaptadores.

**Pronto quando:** os casos da spec §3 passam, comandos existentes têm migração compreensível e a pessoa consegue ver exatamente o que está autorizando.

## F1. Extensão mínima e primeira jornada útil

- [ ] Definir o manifesto mínimo, versão, identidade, capacidades, frases, empacotamento e diagnóstico; validar colisões e entradas inválidas. Manter compatibilidade com `RunCommandIntent`.
- [ ] Entregar `addon new | validate | simulate | pack | install | enable | disable | remove` em etapas testáveis. Simulação não executa ações; instalação e ativação seguem F0.
- [ ] Explicar na interface capacidades declaradas, controles realmente aplicados e riscos que dependem de confiança no código. Não prometer que um processo MCP passa obrigatoriamente pelo HeyCode sem um mecanismo que o imponha.
- [ ] Fazer uma primeira extensão oficial **candidata: memória local por projeto**, sujeita à decisão na spec. Definir fontes, consentimento, retenção, visualização, correção e exclusão; não enviar memória ao relay.
- [ ] Validar a jornada: o agente registra contexto permitido, a pessoa pergunta à Alexa onde parou, recebe resumo curto com indicação de origem/idade e encontra detalhes no computador. Testar ausência de contexto, dados desatualizados, ambiguidades, privacidade e queda do relay ou catálogo.
- [ ] Testar instalação e uso em máquina limpa por uma pessoa externa; registrar dificuldades e corrigir bloqueios antes da próxima fase.

**Pronto quando:** uma pessoa consegue instalar, entender, ativar, usar, desativar e remover a extensão; a jornada de voz é útil e verificável sem inventar estado. Se memória não for viável como primeiro exemplo, escolher outra extensão oficial e justificar a troca na spec.

## F2. Mentor para criar e testar extensões

- [ ] Entregar o MCP separado `heycode-mentor` com as seis tools da spec §6 sobre as operações locais validadas em F1; ele não recebe o segredo de controle da ponte.
- [ ] Criar guias em skill e trecho para AGENTS.md, com instruções de registro nos clientes e declaração de limitações reais de cada um.
- [ ] Testar que rascunho, validação, simulação e empacotamento não executam, registram, ativam ou publicam extensões, nem leem `config.env`; tratar dados de terceiros como não confiáveis.
- [ ] Pedir a uma pessoa externa que crie e simule uma extensão simples, registrando onde precisou de ajuda.

**Pronto quando:** uma pessoa consegue passar da ideia a um pacote inspecionável sem que o mentor tome decisões de instalação por ela.

## F3. Confiança, atualização e revogação

Antes de abrir distribuição comunitária, detalhar na spec e nos ADRs o modelo de ameaça e a operação, inclusive recuperação e os limites de cada selo.

- [ ] Definir assinatura e verificação, identidade do autor e do pacote, versão, hashes, permissões, expiração, proteção contra volta de versão e rotação ou perda de chaves. A implementação deve respeitar o modelo aprovado, incluindo o ADR 0066 se aprovado.
- [ ] Definir atualização: quais mudanças exigem nova confirmação, como comparar permissões e como preservar a versão anterior. Testar adulteração, corrida e alteração de permissões.
- [ ] Definir o comportamento de extensões revogadas, inclusive máquinas offline, atraso ou indisponibilidade da lista, recuperação e comunicação à pessoa. Testar lista estática e revogação assinada enviada pelo relay.
- [ ] Definir o que acontece quando catálogo, serviço de assinatura ou relay caem: novas instalações falham fechadas; preservar o uso local e a falha aberta dos agentes conforme a política de revogação aprovada.
- [ ] Documentar e testar geração, guarda, rotação, recuperação e revogação de chaves; as ações de posse de chaves continuam com o dono.

**Pronto quando:** uma instalação, atualização e revogação reais são reproduzíveis, com testes de falha e recuperação, e a pessoa entende o que está confiando.

## F4. Catálogo e lojinha comunitária

- [ ] Criar catálogo e esteira conforme a spec aprovada: commit e pacote fixados, validação, varredura, execução isolada, revisão e atestados; não executar código de terceiros na VM de produção.
- [ ] Definir critérios públicos de publicação, denúncia, moderação, resposta a incidentes e remoção. O selo **oficial** identifica autoria/responsabilidade do projeto; **verificado** descreve os testes efetuados, sem garantir segurança.
- [ ] Publicar busca, detalhes, permissões, versão, origem, selos e fluxo de instalação pendente no painel/site. Disponibilizar pacotes e índice com as verificações de F3.
- [ ] Avaliações e taxa de sucesso ficam para depois do catálogo básico: definir consentimento, dados coletados, retenção, abuso e moderação. Uma chave por instalação não prova uso real nem impede múltiplas instalações.
- [ ] Testar indisponibilidade do catálogo, pacotes adulterados, extensões denunciadas e isolamento entre contas.

**Pronto quando:** um criador externo publica e outra pessoa descobre, inspeciona e instala uma extensão com clareza sobre autoria, permissões e limites da verificação.

## F5. Ampliar as capacidades da assistente

- [ ] Evoluir memória a partir do retorno de F1; manter a pessoa no controle dos dados locais.
- [ ] Construir `heycode-revisor`: apresentar testes, lint e revisão com fontes e limitações; confirmar ações que modifiquem o projeto.
- [ ] Construir `heycode-economia`: mostrar o que foi medido e o que é estimativa, orçamento e custos quando disponíveis, sem agregar chaves de terceiros.
- [ ] Acrescentar frases de novidades, pedido de instalação e avaliações somente quando seus fluxos existirem; nenhuma frase instala, ativa ou amplia permissões sem a confirmação prevista.
- [ ] Avaliar aviso de término e resumo matinal com os mecanismos e limitações reais da Alexa; testar as jornadas no Echo, além dos testes automatizados.

**Pronto quando:** cada capacidade responde a uma necessidade real do desenvolvedor, explica a origem das informações e tem testes de voz, falha e privacidade adequados.

## Trilha operacional independente: borda e recuperação da VM

Esta trilha pode avançar em paralelo após aprovação da spec e do ADR 0065, sem bloquear a prova local de F1. Preparar CI com imagem e atestado por digest, `cloudflared` no Compose, fechamento das portas públicas, runbook de implantação e reversão, backup externo e restauração testada. Registrar o digest implantado e verificar saúde pelo domínio e inacessibilidade direta das portas. Criação de túnel, configuração do destino de backup e demais ações de conta ficam com o dono conforme a spec.

## Dependências e decisões antes da implementação

F0 precede instalação/ativação em F1; F1 precede validação do mentor e distribuição comunitária; F3 precede F4; F5 pode ser desenvolvido incrementalmente após F1, com publicação comunitária dependente de F4. A trilha operacional é independente da prova local.

Antes de aprovar a implementação, atualizar a spec para refletir essa ordem e resolver: extensão inicial; fronteira de confiança e mecanismos reais de isolamento; confirmação independente; migração de comandos; atualização e revogação; privacidade da memória e das avaliações; definição dos selos; e critérios de aceitação no Echo e em máquina limpa. Se alguma decisão mudar arquitetura, registrar novo ADR conforme os gates.
