# HeyCode: intents completas no modo compartilhado

Data: 2026-11-13. Status: Aprovada pelo dono em 2026-11-13 ("Pode seguir com isso", em resposta à proposta de começar o porte das intents do Lambda; registrado pelo agente a pedido expresso).

Visão: `docs/ROADMAP-HEYCODE.md`. Base: spec da skill compartilhada (`2026-11-13-heycode-skill-compartilhada.md`, §2 deixou este porte para esta trilha), relay (`2026-11-13-heycode-relay-mvp.md`), contratos da P2, ADRs 0029 a 0043.

## 1. Intenção e porquê

O endpoint `/v1/alexa` hoje só abre, ajuda e para. O Lambda do dono faz o trabalho de verdade: cada intent vira uma chamada à ponte local, que devolve a fala (`speech`), e o Lambda guarda o contexto nos atributos de sessão da Alexa. Meta: **uma pessoa com a skill compartilhada faz por voz o mesmo que o dono faz hoje (status, pendências, aprovar com PIN, modo, projetos, pedir tarefa, ditado confirmado, resposta livre, criar projeto, cancelar), sem Lambda e sem túnel, e sem que o relay ganhe poder novo sobre a máquina além do que a voz já tinha.**

## 2. Escopo

Dentro: dois tipos novos de mensagem no protocolo (`bridge-call` e `bridge-result`); executor no componente local que chama a ponte local com **lista fechada** de rotas; porte, em Python no relay, dos tratadores de intent do Lambda (mesma fala, mesmos atributos de sessão, mesmas diretivas de diálogo); regra do modo `auto` e do PIN no modo compartilhado; comando `heycode relay-auto`.

Fora: alterar o modelo de interação (`skill/interaction-model-pt-BR.json`) ou o Lambda do dono (continua como está, com a allowlist); resposta assíncrona proativa; interface web.

## 3. Arquitetura

- `bridge-call` (relay → máquina): `{method, path, body?}`. `bridge-result` (máquina → relay): `{status, body, in_reply_to}`, assinado pela instalação. Tipos novos e aditivos no protocolo v1 (ADR 0044).
- **Executor local** (`heycode.relay_client`): só executa o par (método, caminho) da lista fechada abaixo, com consulta restrita às chaves permitidas, contra `127.0.0.1` e com o segredo de controle lido do `config.env` local. Qualquer outra coisa devolve 403 sem chamar a ponte. O relay nunca conhece o segredo da ponte.
- **Lista fechada** (a mesma superfície que o Lambda usa): `GET /status`, `/pending`, `/result`, `/voice/projects` (`offset`), `/voice/projects/status` (`project`), `/voice/projects/resolve` (`name`); `POST /decide`, `/mode`, `/dictation`, `/answer/preview`, `/answer/confirm`, `/projects`, `/confirm`, `/cancel`, `/runs/latest/cancel`.
- **Tratadores no relay** (`heycode.relay.voice`): tradução fiel do `skill/lambda/index.js`: mesmas falas, mesmos reprompts, mesmos atributos de sessão (`selected_project`, `approval_id`, `pending_kind`, `free_answer`, `ask`, `create`, `block_prior_confirmation`, `projects_next_offset`) devolvidos em `sessionAttributes`, e `Dialog.ElicitSlot` para slots que faltam. O relay não guarda estado de sessão: ele vive na sessão da Alexa.
- **Sem destino implícito:** projeto e agente vêm dos slots ou dos atributos de sessão, como hoje.
- **Limites:** cada intent que chama a máquina conta na cota diária (ADR 0037); espera de 4 s e, sem resposta, a fala padrão de falha ("Não consegui falar com o seu computador. Verifique se o heycode connect está rodando.").

## 4. Modo `auto` e PIN

- `/mode` com `mode: auto` só passa se o computador estiver com `auto_allowed` ligado em `relay.json`, o que só o comando local `heycode relay-auto on` faz (ADR 0031: opt-in por instalação, confirmado no computador; nunca ligável só por voz). Sem isso, a máquina responde 403 e a fala explica como ligar. `manual` e `decisoes` passam sempre.
- A decisão de aprovar usa o PIN verificado **na ponte local**, como hoje; o relay só repassa o que a pessoa falou, sem guardar. O PIN não aparece em log do relay.
- Aprovações seguem atadas a `approval_id` lido em voz alta, como no Lambda, e a confirmação de ditado só vale para o destino apresentado.

## 5. Critérios de aceite

1. Cada intent portada tem teste que compara a fala e os atributos de sessão com o comportamento do Lambda (casos extraídos de `skill/lambda/test`).
2. Fluxo ponta a ponta com servidor real: requisição assinada da Alexa → relay → máquina (executor) → ponte local simulada → fala.
3. O executor recusa qualquer rota fora da lista, método trocado, consulta com chave não permitida e `mode: auto` sem `auto_allowed`.
4. O relay não envia nem guarda o segredo da ponte; PIN e texto de pedidos não aparecem em log.
5. Dispositivo não aprovado, conta não vinculada e requisição inválida continuam sem executar nada (testes da P4 intactos).
6. O Lambda do dono e a suíte existente seguem intactos e verdes.

## 6. Decisões (delegadas pelo dono, pela experiência do usuário)

1. Reproduzir as falas e o diálogo do Lambda palavra por palavra: quem já usa a skill do dono não precisa reaprender.
2. `auto` por voz só depois de ligado no computador (mantém o ADR 0031).
3. Tratar o computador offline com uma frase única e acionável, em vez de erros diferentes por intent.

## 7. Riscos

- O relay comprometido já podia pedir ações pela voz; a lista fechada e o gate do `auto` limitam o dano ao que a voz permite. Fica documentado no threat model.
- Divergência futura entre o Lambda do dono (Node) e o porte (Python): mitigada pelos testes de equivalência; a longo prazo o Lambda do dono pode migrar para o relay.
