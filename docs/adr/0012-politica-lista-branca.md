# 0012. Política por lista branca, redação ampliada e prompt protegido

## Status

Aceito. Data: 2026-11-10. Ajusta o ADR 0004; o ADR 0002 (modo auto sem piso) não muda.

## Contexto

A revisão final (`docs/superpowers/specs/2026-11-10-revisao-final.md`, achados A2, A3 e B4) mostrou que a lista negra
`NEVER_BY_VOICE`, pensada para Unix, deixava passar como `allow` em `decisoes` comandos destrutivos de Windows
(`Remove-Item -Recurse -Force`, `rmdir /s`, `del /f`) e de outros mundos (`find -delete`, `git checkout -- .`,
`| python`, `npm publish`). A máscara de segredos falhava com `OPENAI_API_KEY=...`, `Bearer ...`, `usuario:senha@` e
`-pSenha`. E o prompt do supervisor podia ser lido como flag pela CLI do agente. Spec:
`docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` §7 e §10.

## Decisão

- Em `decisoes`, rotina passa a ser uma lista **branca** curta: `git status|diff|log|show|branch|add|commit`, `ls`,
  `dir`, `cat`, `type`, `pwd`, `echo`, `pytest`, `python -m pytest`, `npm test`, `npm run test`, `node --test`, mais as
  ferramentas `Read`, `Grep`, `Glob`, `Edit`, `Write` e `MultiEdit`. Todo o resto de `Bash` vira `ask_voz`. Comando com
  `;`, `&`, `|`, `<`, `>`, crase, `$(`, `${` ou quebra de linha também sai da lista branca.
- `NEVER_BY_VOICE` ganha os padrões destrutivos de Windows e correlatos, e qualquer comando que cite `BRIDGE_SECRET`,
  `BRIDGE_CONTROL_SECRET`, `127.0.0.1:8765`, `localhost:8765` ou `/mode`. Destrutivo continua indo ao teclado.
- O modo `auto` não muda: `decidir` aprova tudo, por decisão do dono (ADR 0002).
- `mask_secrets` troca `\b` por um limite que funciona depois de `_` e cobre `sk-`, `ghp_`, `github_pat_`, `AKIA`/`ASIA`,
  `xox[bp]-`, pares `NOME=valor` e `NOME: valor` com nome contendo `key|token|secret|password|senha|pass|pwd`,
  `Bearer <valor>`, `usuario:senha@` em URL e `-p<senha>`.
- `runner.build_command` põe `--` antes do prompt no Codex e no Claude. O `--help` das duas CLIs (clap no Codex,
  commander no Claude) mostra o prompt como argumento posicional; ambas seguem a convenção POSIX do `--`. Não foi
  executado nenhum modelo para provar o comportamento, então vale validar na primeira run real. O Claude agora recebe
  `-p` antes das demais opções, com o prompt no fim. Plano B, se uma CLI rejeitar o `--`: prefixar o prompt com um espaço.
  Aider não mudou.
- Alternativas rejeitadas: ampliar só a lista negra (sempre haverá um comando a mais) e classificar com LLM (ADR 0004).

## Consequências

- Mais pedidos de voz em `decisoes` para comandos comuns fora da lista (`npm install`, `python script.py`): erro para o
  lado seguro, e quem quer fluidez usa `auto`.
- A máscara tem falsos positivos conhecidos (ex.: `key: valor` em texto corrido) e `-p<algo>` colado; aceitos por
  preferir mascarar a vazar.
- A ressalva de `Edit`/`Write` fora do `cwd` (A2) continua aberta e depende da validação de caminhos da Onda 2a.
