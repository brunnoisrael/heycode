# Revisão adversarial do HeyCode (2026-11-13)

> Registro histórico da revisão de 2026-11-13. O projeto e seu fluxo mudaram depois desta análise; confirme achados e instruções contra a `main` e o SDLC atuais antes de agir.
> A cópia preservada não inclui os links ou referências individuais das fontes consultadas. Atribuições a fontes externas e afirmações marcadas `[NC]` não devem ser tratadas como verificadas sem nova pesquisa e citação direta.

Quatro revisores independentes (GTM, tech hype, DevEx, Alexa Skills) examinaram o `main` e os worktrees `p0`–`p4`. Este documento consolida os achados e os transforma em tarefas para agentes executarem depois.

**Status:** relatório de revisão, não é spec aprovada. Nenhuma tarefa abaixo autoriza código sem spec aprovada (fluxo do `AGENTS.md`). Itens marcados **[NC]** não foram confirmados em fonte oficial pelos revisores; verificar antes de agir. Fontes web foram em boa parte secundárias.

## Como usar este documento (agentes)

1. Leia "Veredito" e "Decisões do dono" primeiro. As tarefas das trilhas dependem delas.
2. Cada tarefa tem ID, dependência, critério de pronto verificável e se exige spec/ADR/humano.
3. Não execute tarefas marcadas `HUMANO` sem aprovação explícita do dono. Não altere `gates.json`, workflows, CODEOWNERS ou o ruleset.
4. Ao concluir, registre a evidência (saída de teste, link do CI), não apenas o relato.

## Veredito consolidado

Consenso dos quatro revisores: **o código é sólido e a segurança do relay (P2/P3) está bem pensada, mas a tese de mercado não está validada e há três riscos que bloqueiam publicação.** Recomendação: **reduzir escopo antes de abrir ao público**. Congelar relay público, OAuth multiusuário e loja (P3-público/P4/P6) até passarem os experimentos E1, E2 e E4; polir o caminho do dono; consertar os bloqueantes de segurança e certificação.

### Bloqueantes (impedem publicação)

| ID | Achado | Origem |
|---|---|---|
| B1 | **Modo `auto` sem piso, sem PIN, sem expiração, ativável por uma frase de voz** (ADR 0002; `skill/lambda/index.js:182-194`). Visita, TV ou criança pode liberar `rm -rf`. Abaixo do padrão que o próprio mercado considera insuficiente (auto mode com classificador). Supervisor ainda usa `codex -s danger-full-access` e `claude --dangerously-skip-permissions` (ADR 0007). | Hype, Alexa, GTM |
| B2 | **A Lambda atual recusa qualquer usuário que não seja o dono** (`index.js:399-436`) e o endpoint `/v1/alexa` de P4 só atende abertura/ajuda/parar. Skill publicada assim reprova na certificação por não funcionar. O revisor da Amazon também não tem como testar sem PC+agente+túnel. | Alexa |
| B3 | **Relay central é, por desenho, um canal de comando para máquinas de terceiros**; supply chain do pacote, prompt injection via conteúdo lido pelo agente e injeção reversa por `reportar_fim`/saída falada estão fora do threat model. Mantenedor solo, sem receita. | Hype, GTM |
| B4 | **Sem demanda externa comprovada.** Único usuário real é o dono. Substitutos de primeira parte (ChatGPT Voice+Codex, Claude Remote Control/Channels, `/voice`) atacam o mesmo caso sem skill nem relay. | GTM, Hype |
| B5 | **Instalação por terceiro não funciona hoje:** pacote não publicado; `main` só tem scripts `.ps1` e `bridge/`; `main` não tem CI, LICENSE, CONTRIBUTING. ~12 passos manuais em 3 consoles para chegar à Alexa. | DevEx |

### Altos

- Absorção pela plataforma: Alexa+ for Builders expõe **MCP add-ons** (Alexa como cliente MCP, Streamable HTTP; Private Preview, pt-BR **[NC]**). Skills custom não estão deprecadas, mas o investimento da Amazon migrou. Anthropic e OpenAI estão fechando o buraco de voz (issue claudeissues #76005 aberta).
- PIN falado é estático, fica na transcrição do app Alexa e a trava de 3 erros/5 min é global (permite negação de serviço ao dono) (`bridge/server.py:541-546`).
- Skill fala comandos/resultados sem PIN (`index.js:99,133`); política da Amazon cita voice code antes de recitar informação sensível.
- `StopIntent` e finais sem `shouldEndSession:true` (`index.js:445-448`).
- Intents com falhas de diálogo: `ApproveIntent` sem slot samples para `{pin}`; `SendInstructionIntent` sem elicit; respostas "esquece/cancela" capturadas como texto de instrução.
- `AskAgentIntent`: SearchQuery não pode dividir frase com outro slot, então "peça ao claude para refatorar o login" cai no Fallback.
- MCP com segredo estático, sem OAuth nem escopos por tool, fora da direção da spec MCP atual. Login próprio e-mail/senha no relay (ADR 0036) reinventa IdP, enquanto o account linking da Amazon exige authorization server.
- Nome de invocação: "heycode" (uma palavra) exige prova de marca; ASR pt-BR provavelmente instável; "meu agente" é genérico e arrisca rejeição. Não muda depois de publicado.
- Contribuição desproporcional para externos: spec aprovada por 1 humano + ADR + plano + 14 gates para qualquer fix; sem via rápida.
- `heycode doctor`: mojibake no Windows, erros do argparse em inglês, não mostra qual home/ponte consultou, sempre "aviso" na camada Alexa.

### Pontos fortes (preservar)

- Threat model do relay (Ed25519, anti-replay, ±2 min, revogação, mascaramento local, `auto` exige confirmação no computador).
- Falha aberta nos hooks; separação de segredos agente/controle.
- Suítes verdes: main 552 pytest + 80 node; p4 999 pytest (executado pelo revisor DevEx com `PYTHONPATH=src`).
- Decisão da Alexa+ chegando ao Brasil (jun/2026) cria janela de atenção.

## Decisões do dono (bloqueiam as trilhas)

| ID | Decisão | Opções | Recomendação dos revisores |
|---|---|---|---|
| D1 | Escopo de publicação | (a) seguir P3/P4/P6 como planejado; (b) congelar relay público e reposicionar como open source com túnel próprio; (c) pivotar o núcleo (MCP de status/aprovação) para celular | (b) até E1/E2/E4 passarem |
| D2 | Política do `auto` fora da instalação do dono | manter só como flag local do dono; ou exigir piso (deny-list) + PIN/desafio + expiração em modo compartilhado | piso + desafio + expiração; `auto` sem piso só local, fora do relay e do pacote comunitário. Exige ADR novo (não edita o 0002) |
| D3 | Nome de invocação | "heycode", "hey code" (duas palavras), outro | testar fonética no Echo antes de decidir |
| D4 | Identidade/login | e-mail+senha próprio (ADR 0036) vs IdP gerenciado/OAuth | IdP gerenciado |
| D5 | Nome do produto | HeyCode vs RoomCode | unificar em HeyCode |

## Experimentos de validação (antes de construir mais)

| ID | Experimento | Sucesso | Descarte |
|---|---|---|---|
| E1 | Demo de 60–90 s + repo em comunidades dev pt-BR | ≥15 "quero instalar" e ≥5 instalações concluídas | <5 interessados |
| E2 | Dono mede uso por 2 semanas (voz vs teclado/celular) | >5 usos úteis por dia útil | uso cai a ~0 após a semana 1 |
| E3 | Mesmo fluxo com ChatGPT Voice+Codex e Claude Remote Control | existe cenário onde só HeyCode funciona | nenhum cenário |
| E4 | Submeter versão mínima em beta à certificação | aprovada no escopo atual | reprovada por execução arbitrária/auto |
| E5 | 50 frases reais com jargão e nomes de projeto no Echo | ≥85% sem repetir | <70% |
| E6 | 3 devs instalam só com QUICKSTART | 2/3 chegam a uma tarefa de teste em 30 min | <2/3 |
| E7 | Verificar disponibilidade pt-BR de Alexa+ MCP add-ons e se custom skills seguem suportadas | resposta documentada | n/a |

## Tarefas por trilha

Legenda: **Spec** = exige spec aprovada antes de código; **ADR** = exige ADR novo; **H** = exige humano.

### T-SEC: segurança (prioridade máxima)

- **T-SEC-1 (Spec, ADR, H)**: novo modo de aprovação do `auto` para uso compartilhado: piso deny-list mantido, expiração configurável (sugestão 30 min), confirmação em voz do que está sendo liberado, log, e ativação só após desafio. Não editar ADR 0002; criar ADR novo que o delimite ao uso local do dono. Pronto: testes mostram que "modo auto" dito sem desafio não ativa em conta não-dono; teste de expiração.
- **T-SEC-2 (Spec)**: substituir PIN estático por desafio de uso único mostrado no computador (ou PIN por usuário criado no linking) com lock por usuário e re-link após 3 erros; lembrete de 60 dias; reset. Pronto: replay de áudio gravado não aprova; ataque de 3 erros não bloqueia o dono em outros fluxos.
- **T-SEC-3**: falar apenas resumo por padrão ("há um comando Bash pendente") e detalhe só após desafio; mascarar segredos também no cliente da skill. Pronto: teste com segredos de formato conhecido na saída falada.
- **T-SEC-4 (Spec, H)**: estender `docs/security/threat-model.md` (p3) com supply chain do pacote (assinatura, versões e checksum fixados), prompt injection que usa MCP/ask para exfiltrar, e injeção reversa via `reportar_fim`/saídas. Pronto: cada ameaça com controle e teste.
- **T-SEC-5**: no supervisor público, remover `danger-full-access`/`--dangerously-skip-permissions` como padrão; só sob o modo `auto` local. Pronto: teste do comando montado por modo.
- **T-SEC-6**: tornar `ALLOWED_SKILL_ID` obrigatório na Lambda atual e validar assinatura/cert/timestamp/applicationId no endpoint próprio (spec P4 §4 já descreve). Pronto: invocação sem applicationId e com timestamp antigo é rejeitada (teste e `ask smapi invoke-skill-end-point`).

### T-ALX: skill Alexa

- **T-ALX-1**: `withShouldEndSession(true)` em Stop/Cancel e finais; tratar `NavigateHomeIntent` (ou remover); separar erro de ponte de erro interno (`Errors.canHandle: () => true` hoje trata tudo como ponte); progressive response em chamadas lentas. Arquivo: `skill/lambda/index.js`. Pronto: testes em `skill/lambda/test/`.
- **T-ALX-2**: `ApproveIntent`: slot samples `{pin}` e `o pin é {pin}` + dialog com ElicitSlot; testar "um dois três quatro", "doze trinta e quatro", "zero um dois três". Pronto: simulador/NLU eval.
- **T-ALX-3**: `SendInstructionIntent` com slot samples, dialog e ElicitSlot; palavras de cancelamento ("esquece", "cancela isso", "volta", "não") tratadas antes de virar texto de instrução.
- **T-ALX-4 (Spec)**: aceitar instrução em um turno: uma intent por agente com frase portadora ("peça ao claude {instrucao}") ou duas intents por carrier phrase. Substitui a limitação de SearchQuery com outro slot na mesma frase.
- **T-ALX-5**: desambiguar utterances conflitantes: "cancela o agente"/"para o agente" vs `AMAZON.CancelIntent`/`StopIntent`/`CancelDictation`; "o que está rolando" (Status) vs "o que está rodando" (ListProjects); "avisar no fim do ciclo" vs "avise o agente aberto"; "manda ver" vs "manda o {agente}"; "mais" e "resumo" isolados. Adicionar 10+ samples por intent e sinônimos de "aider". Pronto: annotation set NLU com 80+ frases, relatório intent esperado × obtido.
- **T-ALX-6 (Spec)**: entidades dinâmicas de projeto (`Dialog.UpdateDynamicEntities`) em vez dos 3 valores fixos de `NOME_PROJETO`; confirmar nome novo antes de criar. Pronto: **[NC]** suporte pt-BR verificado antes.
- **T-ALX-7**: Launch com card `LinkAccount` para conta não vinculada; Help com exemplos de frase; Fallback com escalonamento (segunda tentativa orienta).
- **T-ALX-8**: aprovar em sessão nova hoje é recusado; oferecer fluxo "tenho uma pendência, quer ouvir?" no Launch.
- **T-ALX-9 (H)**: preparar certificação: política de privacidade e termos em URLs válidas e em pt-BR declarando envio de fala ao relay/agente; contas de teste por locale; **modo demo/sandbox** para o revisor; descrição declarando requisito de PC/relay; registro de userId/deviceId na política. Pronto: checklist de certificação do console sem pendências.
- **T-ALX-10 (H)**: teste de nome de invocação no Echo real ("hey code", "heycode", alternativas) com TV ligada; reunir prova de marca/domínio se for uma palavra. Congelar só depois (D3).
- **T-ALX-11 (opcional)**: APL para dispositivos com tela: comando pendente mascarado/truncado, projetos selecionáveis por toque; PIN nunca na tela.
- **T-ALX-12**: avaliar migração para Alexa+ MCP add-on (E7): o servidor MCP já existe; verificar transporte Streamable HTTP (SSE legado é rejeitado **[NC]**) e conformidade com a spec MCP vigente. Registrar resultado como ADR se a direção mudar.

### T-DX: experiência do desenvolvedor

- **T-DX-1**: limpar o `main`: ignorar `.playwright-cli/`, `.playwright-mcp/`, `.vscode/` no `.gitignore`; decidir sobre a mudança pendente de `skill/interaction-model-pt-BR.json` e o plano `2026-11-13-heycode-publicavel...md`; integrar `p0`→`p4` via PRs em ordem (PR #1 primeiro). Não fazer push nem merge sem pedido do dono (ver memória do projeto).
- **T-DX-2**: README (main, p1, p4): nome único HeyCode, público e idioma (pt-BR, Alexa), estado real ("o que funciona hoje"), quickstart de 3 comandos. Renomear resquícios `RoomCode` (tarefas `RoomCodeBridge`/`RoomCodeTunnel`, MCP `roomcode`, AGENTS.md) com migração que evite duas tarefas agendadas na porta 8765 (D5).
- **T-DX-3**: mover o diário de bordo do dono (`docs/DEPLOY-ALEXA.md` linhas 6–13) para `docs/runbooks/`; acentuar os trechos sem acento.
- **T-DX-4**: `heycode doctor`: forçar UTF-8 no stdout no Windows; mostrar o home carregado e a origem/PID da ponte consultada; traduzir erros do argparse; rebaixar "hook antigo" a aviso quando a ponte local está ok; checar se o executável da tarefa agendada ainda existe; `doctor --alexa` com consulta fim a fim.
- **T-DX-5 (Spec)**: `heycode setup-agents` multiplataforma e idempotente (substitui `setup-agents.ps1`); `heycode skill` que gera o `env.json` e imprime os passos do console com os IDs. Reduz os ~12 passos manuais.
- **T-DX-6**: documentar `pair`/`connect` no QUICKSTART e README como caminho principal para terceiros (hoje só em `docs/OPERATIONS.md:46`), com túnel como alternativa avançada.
- **T-DX-7 (H)**: CONTRIBUTING com **via rápida** para correção trivial (bug + teste que falha, isenção de spec/ADR fora de `human_review_paths`), "como rodar os gates localmente" em um comando, rótulos `good first issue`. Mudar gates/CODEOWNERS é decisão do dono.
- **T-DX-8**: `CHANGELOG.md`, tag `v0.1.0` com a roda do job `instalacao-limpa`; publicar no PyPI quando D1 permitir.
- **T-DX-9**: corrigir DeprecationWarnings (mcp `streamable_http_client`, websockets `ws_handler`); revisar o pin `cryptography>=46,<47` frente a conflitos no `pipx`.
- **T-DX-10**: `pytest-xdist`/marcador rápido (suíte leva 70–145 s); `heycode dev setup` para `core.hooksPath`.
- **T-DX-11**: validar `pip install .` em venv limpo e em Mac/Linux (o revisor não conseguiu executar; só leu o job de CI).
- **T-DX-12**: status das specs: somente 1 de 9 specs tem `Status: aprovada` pelo regex do gate **(conferido em 3 por amostragem)**; regularizar ou documentar a exceção para o legado.

### T-GTM: produto e distribuição

- **T-GTM-1**: executar E1–E7 e registrar resultados em `docs/validacao/` com critério de sucesso/descarte. Pronto: decisão D1 documentada com os números.
- **T-GTM-2**: reposicionar a narrativa de "plano de controle por voz" para "aprovar e acompanhar seus agentes de longe, em pt-BR, com política e auditoria"; cortar a promessa de "plataforma multiagente" até haver paridade (Aider não tem MCP/hook/sandbox).
- **T-GTM-3**: definir quem paga o relay e o limite de suporte (estimativa dos revisores: dezenas de dólares/mês de infra para centenas de conexões; o custo real é segurança e suporte). Registrar como ADR se o relay seguir.
- **T-GTM-4**: canal de distribuição realista: vídeo curto e repositório (GitHub/X/Reddit/HN pt-BR), não a loja. README com GIF de 30 s.
- **T-GTM-5 (opcional, depende de D1c)**: extrair o núcleo (MCP de status/aprovação/decisão por política) como produto independente de voz, com aprovação no celular.

## Ordem sugerida

1. D1, D2 e D5 (dono), E2 e E7 em paralelo (baratos).
2. T-SEC-1/2/3/5/6, T-ALX-1/2/3/5/7 (consertam falhas independentes de D1).
3. T-DX-1/2/3/4/6 (limpeza e primeira impressão).
4. E1, E3, E5, E6 com o caminho polido.
5. Só então, conforme D1: T-ALX-9/10, T-SEC-4, relay público, certificação (E4), T-DX-7/8.

## Limitações desta revisão

- Pesquisa web de poucas passadas, fontes majoritariamente secundárias; vários itens marcados **[NC]** (data do auto mode padrão, disponibilidade pt-BR do Alexa+ MCP, transporte SSE vs Streamable HTTP do servidor, flags exatos do ASK CLI).
- O GTM não leu P1/P2 por completo; o revisor Alexa não leu os ADRs 0005/0010/0013/0016/0018/0020/0023 em detalhe.
- Não há dado de base instalada de Echo no Brasil; a estimativa "centenas de usuários potenciais" é palpite do revisor.
- O revisor DevEx não executou `pip install .` limpo (bloqueado pelo sandbox); números de testes foram executados por ele, não por mim.
- Mudanças em `skill/` e ADRs seguem o fluxo do `AGENTS.md`; este documento não cria spec nem ADR.
