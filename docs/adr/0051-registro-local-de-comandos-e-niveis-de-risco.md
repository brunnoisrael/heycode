# 0051. Registro local de comandos e níveis de risco

## Status

Aceito. Data: 2026-11-13.

## Contexto

Comandos que executam coisas no computador são o ponto mais perigoso do produto. Um relay comprometido, um painel invadido ou uma frase mal reconhecida não podem criar execução (ADR 0048). Spec: `docs/superpowers/specs/2026-11-13-heycode-comandos-locais-scripts-e-webhooks.md` §3 e §4.

## Decisão

- As definições vivem em `commands.json` no computador, escrito só pelo CLI local (`heycode command ...`), que mostra a definição exata e pede confirmação. O relay e o painel só leem um resumo (nome, apelidos, tipo, risco, ligado, descrição) e só podem **desligar**.
- Scripts rodam **sem shell**, com `argv` fixo, ambiente mínimo, `cwd` absoluto existente, tempo máximo e saída limitada e mascarada. Nada falado entra no comando: a fala só escolhe qual.
- Três níveis: `leitura` (roda ao reconhecer), `confirmar` (pergunta "Confirma?") e `pin` (aprovação com o PIN e o bloqueio por tentativas já existentes). Pendência única, de 120 s, atada ao comando e ao hash da definição.
- Uma execução por vez e intervalo mínimo de 3 s por comando.
- Rejeitado: o relay definir ou editar scripts (um relay comprometido ganharia execução), argumentos extraídos da fala (injeção) e shell (metacaracteres).

## Consequências

O pior que um relay comprometido faz é pedir um comando que o dono já cadastrou, no nível de confirmação que o dono escolheu, ou desligar comandos. Custo: cadastrar exige o terminal; a pessoa que escolher `leitura` aceita executar sem confirmação.
