# 0014. Separação de segredos: agente e controle

## Status

Aceito. Data: 2026-11-10.

## Contexto

A revisão final (`docs/superpowers/specs/2026-11-10-revisao-final.md`, achados A1, A3, A4, M1, M3, M6, M7 e B2) mostrou que um único `BRIDGE_SECRET` valia em todas as rotas. O hook e o cliente MCP precisam dele no ambiente do agente, então um agente (ou um conteúdo web que ele leu, por prompt injection) podia chamar `POST /mode` e ligar o modo auto sozinho. Um segredo vazio também abria a ponte sem credencial (`compare_digest("", "")` é verdadeiro). A allowlist da Lambda não protege esse caminho, porque a ponte nunca vê o usuário da Alexa. Spec: `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md`. O modo auto continua aprovando tudo (ADR 0002, decisão do dono).

## Decisão

- Dois segredos, ambos no cabeçalho `x-secret`; cada rota compara só com o seu.
  - `BRIDGE_SECRET` (agente): `/event`, `/approval`, `/instruction/next` e `/mcp` (também aceito como `Authorization: Bearer`). `/health` segue sem segredo.
  - `BRIDGE_CONTROL_SECRET` (controle, só na Lambda): todas as outras rotas (`/mode`, `/decide`, `/status`, `/pending`, `/result`, `/instruction`, `/runs*`, `/projects`, `/confirm`, `/cancel`, `/dictation*`).
- A ponte aborta no import (`SystemExit`) se qualquer segredo faltar, tiver menos de 32 caracteres ou se os dois forem iguais.
- Toda `speech` passa por um único helper, `say()`, que aplica `mask_secrets`. `describe_tool` pula tokens `VAR=valor` iniciais.
- `/pending` devolve `approval_id`; `/decide` aceita `approval_id` opcional e recusa ("Esse pedido mudou. Pergunte de novo." ou "Esse pedido já expirou.") quando não é o pendente mais antigo. Um id divergente não conta como falha de PIN.
- `/mode` (GET e POST) devolve `{mode, report_on_end, speech}` com a fala em pt-BR.
- Caminhos: `/dictation` e `/runs` resolvem `realpath` e exigem `commonpath` sob `PROJECTS_ROOT`. Projeto inexistente ou fora da raiz responde `ok:false` ("Não achei o projeto X.") e nunca cai na raiz. `/runs` sem `cwd` ou fora da raiz responde 400, e a política vem sempre do `cwd` final (o campo `project` é ignorado).
- `pedir_decisao` sem `BRIDGE_PIN` responde `sem_resposta` na hora, sem criar aprovação (no modo auto continua respondendo "sim").
- Alternativas rejeitadas: PIN no `/mode` (não cobre as demais rotas de controle) e ACL por rota num segredo único (o agente continuaria com a credencial mestre).

## Consequências

Um agente comprometido só alcança as rotas de agente: não muda de modo, não aprova, não inicia runs. O custo é operacional: dois segredos para gerar, rotacionar e guardar (`scripts/rotate-secret.ps1 -Which`), e a Lambda passa a usar `BRIDGE_CONTROL_SECRET`. Uma ponte já instalada não sobe até o `.env` ganhar o segredo de controle e ambos terem 32 caracteres ou mais. Risco aceito: o segredo de agente ainda permite forjar `/approval` e `/event` (status falso); a política e a lista branca (ADR 0012) limitam esse dano.
