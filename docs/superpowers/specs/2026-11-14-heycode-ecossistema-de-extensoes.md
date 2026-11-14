# Ecossistema de extensões do HeyCode: lojinha, mentor e MCPs com harness

Data: 2026-11-14. Status: rascunho aguardando aprovação do dono.

ADRs: 0062 (borda por Cloudflare Tunnel na VM), 0063 (extensões, risco calculado e modelo de confiança). Plano: `docs/superpowers/plans/2026-11-14-heycode-ecossistema-de-extensoes.md`.

## 1. Intenção

O HeyCode é um produto de comunidade. O dono hospeda o relay no próprio domínio (`heycode.dev.br`) para que a ferramenta esteja sempre usável. Dentro dele, a comunidade aprende a criar extensões para a própria Alexa, publica numa lojinha com avaliações, e o dono publica as suas como "oficial". A Alexa continua governando: ela dispara, confirma e aprova; nunca instala, nunca dá permissão nova.

## 2. Objetivos, não objetivos e antiobjetivos

Objetivos:
- Fechar duas falhas atuais antes de qualquer extensão de terceiros (§3).
- Borda sem porta aberta: Cloudflare Tunnel na VM, imagem pronta e fixada por digest, backup externo com restauração testada (§4).
- Quatro tipos de extensão com risco crescente e um manifesto único (§5).
- Mentor como MCP fino que a pessoa pluga no próprio agente (§6).
- Lojinha: catálogo assinado, esteira agêntica de verificação, avaliações com prova de instalação, revogação (§7).
- Três MCPs oficiais de lançamento (§8) e as frases de voz da lojinha (§9).

Não objetivos: cobrança; certificação da skill na loja da Amazon; OpenCode hospedado; intents novas criadas por addon; esteira de terceiros rodando na VM.

Antiobjetivos: addon que ganha risco menor do que suas capacidades; instalação ou ativação aprovada por um agente; artefato "oficial" assinável por quem invadir a VM, o túnel ou o GitHub; a Alexa deixando de responder porque o catálogo ou a lojinha caíram.

## 3. Fase 0: falhas que vêm antes de tudo

1. **Risco calculado com piso.** O CLI calcula o risco pelas capacidades: script ≥ `confirmar`; webhook com método de escrita ≥ `confirmar`; uso de segredo (`env:`) ≥ `pin`. O risco declarado só sobe acima do piso. Hoje um agente com shell pode registrar um script destrutivo como `leitura`.
2. **Comando novo ou alterado nasce desligado**, com o sha256 da definição. Ligar exige confirmação fora do agente atada a esse hash: TTY interativo do CLI, painel, ou Alexa com PIN quando o risco é `pin`.
3. **Instalar e ativar nunca aceitam resposta de `pedir_decisao` ou `pedir_resposta`.** Hoje `pedir_decisao` responde "sim" sozinho quando a política permite, e no modo `auto` ela permite tudo (`src/heycode/mcp_server/server.py`).

Aceite: testes mostram que (a) `--risk leitura` num script vira `confirmar`; (b) comando novo não executa por voz até ser ligado fora do agente; (c) mudar a definição desliga e pede nova confirmação; (d) com a política em `auto`, nenhuma tool MCP consegue ativar ou instalar.

## 4. Fase 1: borda e operação da VM

- `cloudflared` como serviço do compose; o token do túnel fica em `relay.env` (modo 600). Nomes: `staging-api.`, `staging-app.` hoje; `loja.` e `pkg.` quando a lojinha existir.
- As portas 80 e 443 deixam de ser publicadas; a lista de segurança da Oracle fica só com o SSH (ou SSH também pelo túnel, com Cloudflare Access).
- A imagem do relay é montada na CI, publicada no `ghcr.io` com atestado de proveniência, e a VM faz `pull` por digest. Nada é compilado na VM.
- Backup diário com cópia externa (`rclone`) e restauração testada, registrada no runbook.
- A regra de taxa, os WebSockets e o modo antibot continuam no painel da Cloudflare (ADR 0058).

Aceite: acesso direto ao IP da VM em 80/443 não conecta; `/health` responde pelo nome; restauração de um backup externo num banco vazio passa no teste; o deploy registra o digest implantado.

## 5. Tipos de extensão e manifesto

| Tipo | Onde roda | Risco mínimo |
|---|---|---|
| Atalho (frase → ação existente) | Relay | "Confirma?" por voz (já existe) |
| Comando (script ou webhook fixo) | PC | Calculado (§3) |
| Addon (pacote de comandos, apelidos e configuração) | PC | O maior risco entre os seus comandos |
| MCP com harness (tools, skills, prompts para agentes) | PC | Declarado por tool; ações sensíveis passam pela aprovação do HeyCode |

Manifesto `heycode-addon.json`: `id`, `versao`, `autor`, `licenca`, `repositorio`, `commit` (40 hex), `tipo`, `capacidades` (processos, rede com destinos fixos, pastas, segredos por nome), `frases` (apelidos usados por `RunCommandIntent`), `mcp` (comando e argumentos, quando houver). O addon **não** cria intent: entra pelo `RunCommandIntent` existente.

CLI: `heycode addon new | validate | simulate "frase" | pack | install | enable | disable | remove`. `validate` e `simulate` são determinísticos e são os mesmos que a esteira do catálogo roda. `install` e `enable` exigem confirmação fora do agente (§3).

## 6. Mentor como MCP no agente da pessoa

A pessoa pluga o MCP `heycode-mentor` no próprio agente (Claude Code, Codex, OpenCode, Cursor). Ele é uma casca fina sobre o CLI. Os guias vivem também numa skill e num trecho para AGENTS.md; só tools são universais entre clientes.

| Tool | Faz | Nunca faz |
|---|---|---|
| `guia(topico)` | Guia primário de cada tipo de extensão | Ler conteúdo de terceiros |
| `criar_rascunho(tipo, nome)` | Esqueleto numa pasta de rascunho | Registrar ou ligar |
| `validar(caminho)` | Erros e risco calculado | Aceitar risco proposto pelo modelo |
| `simular_frase(frase, caminho?)` | Intent, comando casado, risco e fluxo de voz, offline | Executar, falar com a ponte |
| `empacotar(caminho)` | Pacote, varredura de segredos, link de PR pré-preenchido | Push, abrir PR, usar credencial |
| `diagnostico()` | Versões, cliente e capacidades | Ler `config.env` |

Processo separado do MCP do HeyCode, sem o segredo de controle da ponte. Texto de terceiros volta só como campos estruturados, truncados e marcados `untrusted`.

## 7. Lojinha

- **Catálogo:** repositório público `heycode-catalogo` com `index.json`; envio por PR com manifesto e commit fixado. `main` protegida e 2FA com chave física para quem faz merge.
- **Esteira de verificação:** roda em runner hospedado pelo GitHub, só depois do merge, a partir do commit fixado, nunca com `pull_request_target` sobre código de fork. Passos: `validate`, varredura de segredos, execução isolada e revisão adversarial por agente. Gera atestado de proveniência e o selo "verificado".
- **Hospedagem:** índice, pacotes e lista de revogação servidos pela VM em `loja.` e `pkg.heycode.dev.br`, com cache na borda; cópia no GitHub Releases imutável como plano B.
- **Confiança (ADR 0063):** chave raiz offline 2 de 3; chave oficial em token de hardware do dono; selo verificado por Sigstore keyless amarrado ao workflow do catálogo; chave de revogação separada. Índice com versão monotônica, validade curta e hash do anterior; hash publicado no Rekor.
- **Ponte antes de instalar (falha fechada):** cadeia de assinaturas a partir da raiz embutida, validade, sem volta de versão, sha256, bundle Sigstore, lista de revogação, permissões aprovadas. Extensões já instaladas seguem, exceto as revogadas; os hooks dos agentes continuam falhando abertos.
- **Avaliações:** só com prova de instalação assinada pela chave Ed25519 da instalação (ADR 0030), uma por instalação e versão. A ponte informa, se a pessoa permitir, se o comando funcionou ou falhou; a taxa de sucesso aparece ao lado do polegar.
- **Revogação:** o relay empurra pelas conexões das pontes uma revogação já assinada; a lista estática cobre o relay fora do ar. O relay não consegue criar revogação.
- **Painel e site:** página da lojinha com busca, selos, avaliações, perfil de criador e "remixar" com crédito.

## 8. Três MCPs oficiais de lançamento

Todos usam as tools do MCP do HeyCode (`registrar_status`, `pedir_decisao`, `reportar_fim`, `pedir_resposta`, `buscar_instrucao`).

1. **`heycode-economia`:** compressão de saída de comandos (usa o RTK se instalado), resumos curtos, orçamento de contexto por tarefa e sugestão de modelo mais barato com a chave da própria pessoa. Avisa por `pedir_decisao` quando a tarefa passa do orçamento. Risco: leitura. Não compartilha nem agrega chaves de terceiros.
2. **`heycode-revisor`:** antes de `reportar_fim`, roda os testes e o lint declarados no projeto e uma revisão de contexto novo comparando o diff com a spec; pergunta por voz se deve mandar corrigir. Risco: confirmar.
3. **`heycode-memoria`:** decisões e contexto por projeto, passagem de bastão entre sessões e agentes, base do resumo matinal e do aviso "o agente terminou". Fica no PC, nunca no relay. Risco: leitura.

## 9. Voz

- "Alexa, o que tem de novo na lojinha?": três destaques.
- "Alexa, instala o addon X": cria pedido pendente; a confirmação é no PC, com as permissões à vista.
- "Alexa, gostei desse" ou "não gostei": voto da última extensão usada.
- "Alexa, quanto os agentes gastaram hoje?", "o que o revisor achou?", "onde parei no projeto X?": pelos MCPs oficiais.
- Aviso quando o agente termina e resumo matinal (já previstos no plano do site).

Tudo pelas intents existentes ou por intents aditivas com ADR; nenhuma frase instala, liga ou eleva risco sem a confirmação fora do agente.

## 10. Ações que só o dono faz

Aprovar esta spec; comprar dois tokens de hardware; gerar a raiz e a chave oficial; criar o túnel na conta Cloudflare; configurar o `rclone`; criar o repositório do catálogo e sua proteção; escolher o nome final do `heycode-economia`.

## 11. Riscos

- Concentração na Cloudflare (DNS, túnel, proxy): suspensão derruba tudo. Mitigação: backup externo e cópia dos pacotes no GitHub Releases.
- VM única e fraca, e reclamação por ociosidade da Oracle: o componente local reconecta; a migração é o compose em outra VM.
- Moderação da lojinha: a esteira reduz, não elimina. Denúncia e revogação rápidas são parte do desenho.
- Política da Amazon sobre execução por voz: a lojinha não muda o que a skill faz; só alimenta comandos já governados.
