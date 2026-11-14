# Plano: ecossistema de extensões do HeyCode

Spec: `docs/superpowers/specs/2026-11-14-heycode-ecossistema-de-extensoes.md` (rascunho; nada é implementado antes de `Status: aprovada`). ADRs: 0062, 0063.

Um PR por fase, sem limite de tamanho (ADR 0060). Cada fase termina com `python -m pytest` verde e a evidência colada no PR (G16).

## F0. Falhas atuais (antes de tudo)

- [ ] Teste falhando: script cadastrado com `--risk leitura` precisa virar `confirmar`; com `env:` precisa virar `pin`.
- [ ] `src/heycode/commands.py` e `commands_cli.py` (registro local): função `risco_efetivo(capacidades, declarado)`; aplicar em `command add` e na carga do `commands.json`.
- [ ] Hash sha256 da definição; comando novo ou alterado nasce desligado; `command enable` exige TTY interativo (ou painel, ou PIN por voz para risco `pin`).
- [ ] `mcp_server/server.py`: nenhuma tool instala ou ativa; teste com política em `auto` provando que ativação por MCP é recusada.
- [ ] `heycode doctor` avisa comandos que subiram de nível.

## F1. Borda e operação da VM (ADR 0062)

- [ ] Workflow de CI que constrói a imagem do relay, publica no `ghcr.io` e gera atestado.
- [ ] `infra/vps/docker-compose.yml`: imagem por digest, serviço `cloudflared`, sem `ports` 80/443; Caddy removido ou fixado por digest.
- [ ] Runbook: criar o túnel na conta Cloudflare (dono), `ingress` dos nomes, fechar 80/443 na lista de segurança da Oracle, voltar atrás.
- [ ] Backup externo com `rclone` (dono configura o destino) e teste de restauração registrado em `docs/runbooks/restauracao-do-banco.md`.

## F2. Manifesto e CLI de addon

- [ ] Esquema `heycode-addon.json` com testes de validação (válido, sem commit, capacidade desconhecida, frase que colide).
- [ ] `heycode addon new | validate | simulate | pack` determinísticos; `simulate` usa o motor de política em processo com executor falso.
- [ ] `heycode addon install | enable | disable | remove`, com confirmação fora do agente.

## F3. Mentor como MCP

- [ ] Servidor `heycode-mentor` com as 6 tools da spec §6, chamando o CLI; processo separado, sem segredo da ponte.
- [ ] Skill e trecho de AGENTS.md com os guias; testes de que nenhuma tool registra, liga, publica ou lê `config.env`.
- [ ] Guia de instalação do mentor em Claude Code, Codex, OpenCode e Cursor.

## F4. Modelo de confiança (ADR 0063)

- [ ] Dono: dois tokens de hardware, raiz 2 de 3, chave oficial, chave de revogação; runbook de geração e rotação.
- [ ] Verificador na ponte (python-tuf ou equivalente e sigstore-python): testes de adulteração, volta de versão, índice vencido, revogação e permissão divergente.
- [ ] Revogação dupla: lista estática e envio assinado pelo relay às pontes conectadas.

## F5. Catálogo e lojinha

- [ ] Repositório `heycode-catalogo` (dono cria), `main` protegida, esteira pós-merge em runner do GitHub, atestado, Releases imutáveis.
- [ ] `loja.` e `pkg.heycode.dev.br` servidos pela VM com cache na borda; cópia no GitHub Releases.
- [ ] Relay: avaliações com prova de instalação, taxa de sucesso opcional, denúncia.
- [ ] Painel e site: página da lojinha, selos, perfil de criador, remixar.

## F6. Três MCPs oficiais

- [ ] `heycode-economia`, `heycode-revisor`, `heycode-memoria`, cada um com manifesto, testes e publicação "oficial" pelo catálogo.

## F7. Voz

- [ ] Frases da lojinha (novidades, instalar como pendente, votar) pelas intents existentes ou intents aditivas com ADR.
- [ ] Aviso de "agente terminou" e resumo matinal usando `heycode-memoria`.
- [ ] Reenviar o modelo de interação ao console quando mudar.

## Dependências

F0 bloqueia F2 em diante. F1 é independente. F4 bloqueia F5. F6 pode começar após F2 e só é publicado após F5.
