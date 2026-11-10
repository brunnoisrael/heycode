# 🎙️ RoomCode

**Converse com seus agentes de código pela Alexa.** Pergunte o que eles estão fazendo, aprove ou negue o que pedem, mande tarefas por voz e comece projetos novos, tudo com Claude Code, Codex e Aider, sem levantar da cadeira.

```
Alexa ──skill──▶ túnel HTTPS ──▶ Ponte RoomCode (FastAPI + SQLite)
                                   ├── Motor de políticas (manual · auto · decisões)
                                   ├── Servidor MCP  ◀── Claude Code · Codex
                                   ├── Hooks do Claude Code (status, aprovação, próxima instrução)
                                   └── Supervisor ──▶ claude · codex · aider (processos filhos)
```

## O que dá para fazer

| Você diz | Acontece |
|---|---|
| "Alexa, pergunte ao meu agente qual o status" | Lê o que o agente está fazendo agora |
| "Modo auto" / "modo manual" / "modo decisões" | Troca a política de aprovação |
| "Peça ao Codex para rodar os testes" | Ela relê o que entendeu; você diz "confirma" e a ponte inicia o agente |
| "Crie o projeto painel com o Claude para acompanhar vendas" | Cria pasta, git, gates de spec e `AGENTS.md`, e o agente começa escrevendo a spec |
| "Cancela o agente" / "para o agente" | Interrompe a execução mais recente em andamento |
| "Avise o agente aberto: rode os testes" | Entra na fila do Claude Code aberto, com a mesma releitura e confirmação |
| "Peça ao Codex no projeto painel para rodar os testes" | Ditado no projeto citado; projeto inexistente é recusado, nunca cai na raiz |
| "Aviso no fim do ciclo" | Quando o agente termina, ela oferece ler a saída e receber a próxima instrução |

## Modos de política

- **manual:** a Alexa pergunta cada validação que o agente pede (aprovar exige PIN).
- **auto:** aprova tudo. **Sem piso de segurança, sem PIN e sem expiração** (ADR 0002). Comandos como `rm -rf` e `git push --force` passam sem pergunta.
- **decisões:** aprova o rotineiro e só pergunta o que é escolha de verdade.
- **fim de ciclo:** opção à parte, combinável com qualquer modo.

As regras valem globalmente, com exceção por agente ou projeto ("no projeto X, manual"), e ficam salvas em disco.

## Segurança (leia antes de usar)

- **Dois segredos** (`x-secret`, mínimo de 32 caracteres, diferentes entre si). `BRIDGE_SECRET` é o de **agente**: vai nos hooks e no MCP e vale só em `/event`, `/approval`, `/instruction/next` e `/mcp` (que também aceita `Authorization: Bearer`). `BRIDGE_CONTROL_SECRET` é o de **controle**: fica só na Lambda e vale nas demais rotas. A Lambda **não** deve receber o segredo de agente. Nunca exponha o servidor sem eles.
- O que a separação protege: um agente (ou conteúdo web que ele leu, por prompt injection) tem o segredo de agente no ambiente, mas com ele não consegue chamar `/mode` e ligar o modo auto sozinho, nem aprovar pedidos, nem iniciar execuções. Ela não protege contra quem já controla a sua máquina ou contra o modo auto em si (ADR 0002).
- A skill só aceita o **seu** usuário e o **seu** dispositivo Alexa (`ALLOWED_USER_ID`, `ALLOWED_DEVICE_ID`), e opcionalmente o ID da skill (`ALLOWED_SKILL_ID`).
- Ditado: toda instrução é relida e só vai depois do "confirma"; limite de 300 caracteres; segredos saem mascarados em voz, push e log.
- Aprovação por voz exige PIN (3 erros bloqueiam por 5 min). No modo manual e no decisões, comandos destrutivos nunca passam por voz.
- **O modo auto e o supervisor executam código na sua máquina por comando de voz.** Um PIN falado pode ser ouvido por quem está na sala. Use por sua conta e risco.
- O Codex desta máquina já roda com `approval_policy="never"`; o RoomCode não altera isso.

## Como funciona por dentro

- **Estado em SQLite** (políticas, sessões, aprovações, instruções, execuções, aviso de fim de ciclo não lido, resumo da sessão e trava de PIN): sobrevive a reinício (ADR 0015). Aprovações pendentes expiram e execuções em andamento viram "interrompidas", sem aviso de fim de ciclo.
- **Um único motor de políticas** (`bridge/policy`) decide `allow | deny | ask_voz | ask_teclado` para hooks, MCP e supervisor.
- **Servidor MCP** (`roomcode`) com `registrar_status`, `pedir_decisao`, `reportar_fim` e `buscar_instrucao`.
- **Supervisor** monta o comando de cada agente conforme a política (sandbox restrito fora do auto).
- Aider não tem MCP nem hook de aprovação: só roda pelo supervisor.

## Instalação rápida

```powershell
pip install -r bridge/requirements.txt
powershell -ExecutionPolicy Bypass -File scripts/install-service.ps1   # ponte como tarefa agendada (porta 8765)
powershell -ExecutionPolicy Bypass -File scripts/setup-agents.ps1      # registra o MCP no Claude Code e no Codex
powershell -ExecutionPolicy Bypass -File scripts/start-tunnel.ps1      # túnel HTTPS (rápido; veja o guia para o nomeado)
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1             # confere tudo numa porta livre
```

Depois de atualizar, **reimporte o modelo de interação** (`skill/interaction-model-pt-BR.json`) no console da Alexa e faça Deploy da Lambda (que usa `BRIDGE_CONTROL_SECRET`). Guia completo da skill Alexa, túnel nomeado, Home Assistant e rotação de segredo: [docs/DEPLOY-ALEXA.md](docs/DEPLOY-ALEXA.md).

## Como este projeto é desenvolvido

Gates obrigatórios, aplicados por hooks do git (`git config core.hooksPath .githooks`):

1. **Spec aprovada** antes de código (`docs/superpowers/specs/`); commits `feat|fix|test|refactor` exigem o trailer `Spec:`.
2. **ADR novo** (`docs/adr/`) para qualquer mudança de arquitetura.
3. **Commits locais** pequenos, com testes (`python -m pytest`, `cd skill/lambda && npm test`).

Regras para agentes em [AGENTS.md](AGENTS.md). Decisões em [docs/adr/](docs/adr/).

## Ideias de evolução

- Ditado de respostas livres para `pedir_decisao` (hoje é sim/não).
- Multi-máquina e multiusuário.
- Publicar a skill na loja da Alexa (hoje só modo desenvolvimento, na sua conta).
