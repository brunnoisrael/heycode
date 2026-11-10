# Alexa Agent Hub: desenho

Data: 2026-11-09. Status: rascunho aguardando aprovação.

## 1. Intenção e porquê

Hoje o projeto é uma ponte de leitura: hooks do Claude Code alimentam um servidor FastAPI, e uma skill Alexa
consulta status/resumo e aprova comandos Bash com PIN. Só serve ao Claude Code, só em um sentido, e o estado
vive em memória.

O dono quer uma Alexa que **opere** os agentes dele de forma "pika" (extraindo o máximo da Alexa, não só
aprovar/negar). A Alexa passa a ser um **plano de controle por voz com políticas** sobre todos os agentes de
código do PC (hoje: Claude Code, Codex, Aider), e também **inicia projetos novos**. Os agentes já navegam no PC
e na web por conta própria; a ponte não precisa dar essas capacidades, só conduzi-los.

## 2. Metas

- G1. Um motor de políticas com 4 modos, configurável por voz:
  - **manual**: pergunta cada validação que o agente pede.
  - **auto**: aprova tudo (ver §7, sem piso de segurança, por decisão do dono).
  - **decisões**: aprova o rotineiro, pergunta só escolhas reais.
  - **fim de ciclo**: ao terminar, oferece ler a saída e recebe a próxima instrução para repassar.
- G2. Regras globais com exceção por projeto ou agente ("no projeto X, manual"), persistidas em disco.
- G3. Suporte a qualquer agente via (a) servidor MCP central e (b) adaptadores por agente (Claude hooks,
  Codex, Aider).
- G4. Modo supervisor: a ponte inicia e controla agentes headless a pedido ("peça ao Codex para...").
- G5. Iniciar projeto por voz: criar pasta, `git init`, scaffold de gates e disparar o agente na primeira
  tarefa (que é escrever a spec).
- G6. Ditado de instruções com releitura e confirmação antes de enviar ao agente.
- G7. Processo obrigatório no repositório: gates de spec, commits locais, ADRs, `AGENTS.md`, skills Anthropic.

## 3. Não-metas

- Dar aos agentes capacidades novas (navegar, web, etc.): eles já têm.
- Voz espontânea nativa da Alexa (a plataforma não permite para skills custom).
- Publicar a skill na loja da Alexa (fica em modo desenvolvimento, só a conta do dono).
- Multiusuário ou multi-máquina.
- Conectar ao GitHub agora (o dono conecta depois).

## 4. Anti-metas (falha mesmo funcionando)

- A ponte travar ou quebrar um agente. Hooks e adaptadores falham aberto (o agente segue com o prompt normal).
- Perda de política ou fila ao reiniciar.
- Alexa executando instrução mal ouvida sem confirmação.
- Vazar segredos lendo comandos ou saídas em voz alta sem resumo.
- Ficar tão complexa que os gates sejam contornados.

## 5. Restrições

- Windows 11. Python 3.14, Node 24, git, uv instalados. Agentes presentes: claude, codex, aider.
- Alexa: ~8 s de limite por resposta, sessões curtas, ditado livre só via slot `AMAZON.SearchQuery` com frase
  portadora, pt-BR, invocação "meu agente".
- Alexa precisa alcançar o PC por HTTPS: falta túnel (`cloudflared` ou Tailscale), a instalar.
- Reaproveitar o que existe: FastAPI em `bridge/server.py`, hooks em `bridge/hook.py`, skill em `skill/`.

## 6. Abordagens consideradas

- **A. Hub MCP + hooks (cooperativo).** Serve agentes já abertos. Não consegue mandar tarefa a sessão
  interativa existente.
- **B. Supervisor (a ponte inicia os agentes).** Controle total e "peça ao X para Y" funciona. Não cobre
  agentes abertos na mão.
- **C. Híbrido (escolhida pelo dono).** Motor de políticas central, com hub MCP e hooks para agentes abertos
  e supervisor para tarefas pedidas pela Alexa. Maior obra, mas é a única que cobre os dois cenários.
  Entrega em fases (§9).

## 7. Decisões do dono

- Abordagem C.
- Modo auto aprova tudo, **sem piso**. Isso remove a lista `NEVER_BY_VOICE` no modo auto. Risco aceito: `rm -rf`,
  `git push --force` etc. passam sem pergunta. Nos demais modos a lista continua valendo.
- Ativar o modo auto **não exige PIN e não expira**: basta pedir por voz ("modo auto"). Vale também para
  agentes iniciados pelo supervisor (aplicação aos dois é chamada minha, ver §10).
- O dono já tem conta no Alexa Developer Console, então a skill pode ser testada de ponta a ponta.
- Iniciar projeto por voz faz parte do escopo.
- Processo: gates obrigatórios de spec, commits locais, ADRs, `AGENTS.md`, skills Anthropic.

## 8. Arquitetura (as chamadas são minhas, ver §10)

```
Alexa skill (Lambda) --HTTPS--> Ponte (FastAPI) --+-- Motor de políticas --- SQLite
                                      |            +-- Servidor MCP (mesma app)
 Agentes abertos --hooks/MCP ---------+            +-- Supervisor --> claude -p / codex exec / aider
```

- **Estado em SQLite**: políticas, sessões, fila de aprovações, fila de relatórios, instruções pendentes,
  histórico. Substitui os dicts em memória.
- **Servidor MCP** (streamable HTTP, SDK Python oficial, montado na mesma app) com ferramentas como
  `pedir_decisao`, `reportar_fim`, `buscar_instrucao`, `registrar_status`. Qualquer agente com suporte a MCP usa.
- **Adaptadores**: Claude Code via hooks (já existem, a estender); Codex via configuração MCP e política de
  aprovação; Aider via MCP ou, onde não houver, só pelo supervisor.
- **Supervisor**: inicia agentes headless como processos filhos, captura saída, aplica a política a cada pedido
  de aprovação, guarda a saída para o "fim de ciclo".
- **Motor de políticas**: função única `decidir(agente, projeto, pedido) -> allow | deny | ask_voz | ask_teclado`,
  usada por hooks, MCP e supervisor. É o único lugar onde os modos existem.
- **Skill Alexa**: novos intents para trocar modo, ditar instrução ("peça ao {agente} {instrução}"), confirmar,
  ouvir saída, criar projeto. Respostas sempre curtas e resumidas.

## 9. Fases

1. Fundação de processo: git local, gates, ADRs, `AGENTS.md`, skills Anthropic (ver §11).
2. Motor de políticas + SQLite + os 4 modos, com testes, sobre o adaptador Claude já existente.
   Inclui o túnel (`cloudflared`) e a skill publicada em modo desenvolvimento, para testar de ponta a ponta.
3. Servidor MCP e adaptadores Codex e Aider (começa com um teste rápido de viabilidade, ver §10).
4. Supervisor e ditado com confirmação.
5. Iniciar projeto por voz.
6. Aviso proativo (ntfy, opcional Home Assistant) e endurecimento.

## 10. Chamadas minhas (revisáveis)

- Python/FastAPI e SQLite (continuidade do que existe, sem servidor extra).
- MCP pelo SDK Python oficial, no mesmo processo da ponte.
- Modo auto sem PIN e sem expiração (decisão do dono, §7). O PIN continua existindo só para os modos que o
  usarem; não é exigido para entrar no auto. Vale para hooks, MCP e supervisor.
- Como não há piso nem PIN no auto, a Lambda **só aceita o ID do usuário e do dispositivo do dono**
  (allowlist), além do `x-secret`, para ninguém mais controlar os agentes.
- Túnel: `cloudflared` nomeado em uso contínuo, quick tunnel só em desenvolvimento. Entra na fase 2.
- Instrução para agente já aberto: só no Claude (hook de Stop + ferramenta MCP `buscar_instrucao`). Codex e
  Aider recebem instruções só quando iniciados pelo supervisor, mas enviam aprovações e relatórios.
- Modo decisões: lista de regras por ferramenta. Leitura, edição e Bash não destrutivo são rotina; pergunta
  livre via `pedir_decisao` é sempre escolha real. Sem LLM no caminho.
- Sem resposta: hooks voltam ao prompt normal após 55 s; o supervisor nega e avisa (tempo configurável).
- Fase 3 começa com um teste de viabilidade. Se o Aider não aceitar MCP, ele fica só no supervisor.
- Uma spec geral (este documento) mais um plano por fase. Commits da fase 1 dispensam o trailer `Spec:`.
- Reinício: aprovações pendentes expiram; execuções do supervisor ficam "interrompidas", sem reanexar.
- Ditado: confirmação em toda instrução, limite de 300 caracteres, segredos mascarados por padrão.
- Compatibilidade: `/status`, `/pending`, `/result`, `/decide`, `/approval`, `/event` seguem funcionando
  durante a migração.
- Aviso de "fim de ciclo": push (ntfy) e fila lida quando a skill é aberta. Voz espontânea só com Home Assistant,
  opcional.
- Criar projeto: pasta dentro de uma raiz configurável (padrão `C:\Users\Sergio\Documents\Projetos`), nome
  ditado e confirmado, primeira tarefa do agente é a spec.

## 11. Processo obrigatório do repositório

- **Gate de spec**: toda funcionalidade tem arquivo em `docs/superpowers/specs/` aprovado antes de código.
- **Commits locais**: git local desde a fase 1. Hook `commit-msg` exige trailer `Spec: <arquivo>` apontando
  para spec existente (exceto `docs:`/`chore:`). Remoto GitHub fica para depois.
- **ADRs**: `docs/adr/NNNN-titulo.md`. Hook `pre-commit` exige novo ADR quando mudam arquivos de
  arquitetura (lista configurável).
- **`AGENTS.md`** na raiz, referenciado por `CLAUDE.md`, valendo para todos os agentes, descrevendo gates,
  comandos e regras.
- **Skills Anthropic** instaladas no projeto (ex.: `mcp-builder`, `skill-creator`) em `.claude/skills/`.

## 12. Deixado ao construtor

Esquema SQLite, nomes exatos das ferramentas MCP, formato dos ADRs, intents e frases portadoras do pt-BR,
detalhes de configuração do Codex e do Aider, estratégia de testes e do lançamento de processos no Windows.
