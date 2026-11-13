# HeyCode: comandos locais (scripts e webhooks) por voz

Data: 2026-11-13. Status: Aprovada pelo dono em 2026-11-13 ("pode seguir com B e C", sobre as fases B e C desenhadas no §6 da spec do painel; registrado pelo agente a pedido expresso).

Base: `2026-11-13-heycode-painel-web-rastro-e-comandos.md` (§6), ADRs 0031, 0044, 0045, 0048, 0049; `docs/security/threat-model.md`.

## 1. Intenção e porquê

Atalhos para agentes (fase A) cobrem "peça ao codex". Falta o que mais se quer de uma voz no computador: **"deploy", "git pull", "reiniciar o serviço", "acender a luz do escritório"**. Isso é execução real, então a regra de ouro é: **quem define o que roda é o computador, nunca o relay, a Alexa ou o painel**. Meta: o dono cadastra um comando uma vez, no terminal, e depois o dispara por voz com o nível de confirmação que ele escolheu.

## 2. Escopo

Dentro: registro local de comandos (`commands.json`) com validação estrita; execução de **scripts** (sem shell) e de **webhooks** (destino fixo); três níveis de risco; confirmação atada ao comando; CLI `heycode command ...`; rotas locais da ponte; integração com a intent `RunCommandIntent`; listagem e **desligamento remoto** no painel; rastro.

Fora: variáveis ou argumentos vindos da fala (injeção), agendamento, encadeamento de comandos, execução como administrador, edição remota de definições.

## 3. Registro local

- Arquivo `commands.json` no diretório do HeyCode, só escrito pelo CLI local (escrita atômica). Cada comando: `name`, `aliases` (até 5), `type` (`script` ou `webhook`), `risk` (`leitura`, `confirmar`, `pin`), `enabled`, `description`.
- **Script:** `argv` (lista de 1 a 32 argumentos; o primeiro é o programa), `cwd` opcional (diretório absoluto existente), `timeout` (1 a 300 s, padrão 60). **Nunca** passa por shell. Ambiente mínimo (PATH, HOME/USERPROFILE, SYSTEMROOT no Windows, LANG) mais os nomes listados em `env_pass`. Saída capturada até 4 KB, com segredos mascarados.
- **Webhook:** `url` fixa em `https` (`http` só para `localhost`/`127.0.0.1`), `method` `GET` ou `POST`, `body` JSON opcional e fixo, `headers` cujos valores podem ser `env:NOME` (lidos do `config.env` local; o valor nunca aparece em resposta, log ou rastro), `timeout` de 1 a 30 s, sem seguir redirecionamentos. `POST` com `risk` `leitura` é **recusado** na validação.
- **Nada do que foi falado entra no comando:** a fala só escolhe qual comando; argv, URL e corpo são exatamente os cadastrados.
- Cadastrar, alterar, remover e **ligar** só pelo CLI local, mostrando a definição exata e pedindo confirmação.

## 4. Níveis de risco e fluxo por voz

| Nível | Comportamento |
|---|---|
| `leitura` | roda assim que a frase é reconhecida e fala o resultado (para o que só consulta) |
| `confirmar` | fala o que vai rodar e pergunta "Confirma?"; só roda depois do "sim" |
| `pin` | exige "aprovar" com o PIN (o mesmo PIN e o mesmo bloqueio por tentativas da aprovação) |

- A pendência é **uma por vez**, vale **120 s**, está atada ao comando e a um hash da definição (editar o registro no meio invalida) e some ao trocar de projeto ou iniciar outra tarefa.
- Um comando por vez (trava global) e intervalo mínimo de 3 s por comando.
- `RunCommandIntent`: o relay tenta primeiro os atalhos de agente da conta (fase A); se nenhum casar, pede à máquina que procure nos comandos locais. O casamento local usa a mesma normalização, recusa empate e baixa semelhança.

## 5. Rotas locais e relay

- Ponte local (segredo de controle): `GET /voice/commands` (só nome, apelidos, tipo, risco, ligado e descrição: **nunca** argv, URL, cabeçalhos ou corpo), `POST /voice/commands/run`, `POST /voice/commands/confirm`, `POST /voice/commands/cancel`, `POST /voice/commands/disable` (**só desligar**; ligar é do CLI). Todas na lista fechada do executor (ADR 0045).
- Relay: `GET /v1/computers/{id}/commands` e `POST /v1/computers/{id}/commands/disable` repassam à máquina pelo canal assinado.
- Painel: seção "Comandos do computador" (somente leitura, com botão **Desligar**) e instrução de como cadastrar pelo terminal.
- Rastro: o resultado e o nome do comando; detalhe local inclui execuções recentes de comandos (nome, risco, resultado, código de saída), nunca a saída.

## 6. Critérios de aceite

1. Validação recusa: shell embutido via `argv` vazio, `cwd` relativo ou inexistente, `timeout` fora da faixa, URL `http` externa, webhook `POST` com risco `leitura`, `env:` apontando para variável ausente, nome ou apelido duplicado, mais de 50 comandos.
2. Script roda sem shell, com ambiente mínimo, respeita timeout (mata a árvore), limita e mascara a saída; webhook não segue redirecionamento e esconde cabeçalhos.
3. Fluxo por risco ponta a ponta com servidor real: `leitura` roda direto, `confirmar` só roda após "Confirma?", `pin` só com PIN correto (3 erros bloqueiam), pendência expira em 120 s, troca de projeto cancela.
4. A fala nunca chega ao comando (teste com texto malicioso na fala).
5. Remoto só consegue **desligar** comandos; `GET /voice/commands` não vaza argv, URL, cabeçalho nem corpo.
6. Painel mostra e desliga; teste em navegador.
7. Suíte anterior verde; Lambda do dono e atalhos de agente intactos.

## 7. Decisões minhas (o dono delegou)

1. Definição só no computador e ligar só pelo CLI; o remoto só desliga (interruptor de segurança).
2. Sem shell e sem parâmetros vindos da voz.
3. Webhook só com destino fixo; segredos de cabeçalho por referência `env:`.
4. Webhook que muda estado nunca é `leitura`.

## 8. Riscos

- Script mal escrito pelo dono continua sendo responsabilidade do dono; o CLI mostra a definição antes de salvar.
- Reconhecimento de fala pode escolher o comando errado: a confirmação (`confirmar` e `pin`) e a recusa de empate são a barreira; por isso `leitura` é por conta e risco de quem a escolhe.
- Windows: `argv[0]` precisa ser um executável (não um `.bat` sem caminho completo); o CLI avisa.
