# HeyCode publicável e esteira obrigatória de agentes: plano de programa

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o HeyCode em um produto que qualquer pessoa instala (MCP/componente local + skill Alexa) sem depender do dono, sobre uma esteira em que todo código é produzido por agentes e só entra se passar por gates obrigatórios.

**Architecture:** Primeiro a esteira (P0), porque tudo o mais será feito por agentes e ela é o que os impede de enfraquecer o próprio processo. Depois a fundação publicável (P1), os contratos e o modelo de segurança multiusuário (P2), o relay em `heycode.dev.br` (P3), a skill compartilhada em beta fechado (P4), a funcionalidade dos marcos M0–M3 do roadmap (P5) e a abertura pública (P6). O núcleo (políticas, estado, MCP, protocolo) permanece agnóstico de voz; a Alexa é um adaptador.

**Tech Stack:** Python 3.11–3.14 (FastAPI, Pydantic, SQLite local, Postgres no relay), SDK oficial MCP, Node (skill/Lambda), GitHub Actions, ruff, mypy, pytest, gitleaks, pip-audit/npm audit. Decisões de stack em aberto viram ADR (ver "Decisões em aberto").

**Spec:** visão em `docs/ROADMAP-HEYCODE.md`. Não há spec aprovada para este programa; pelo fluxo do `AGENTS.md`, **cada trilha começa por uma spec aprovada** (Tarefas P0.1, P1.1, P2.1, P3.1, P4.1, P5.1, P6.1) e só depois ganha plano detalhado. Este documento é o plano de programa; só P0 está detalhado em passos.

## Global Constraints

- Fluxo obrigatório (`AGENTS.md`): spec aprovada → plano em `docs/superpowers/plans/` → código com testes → commit `tipo: descrição` com trailer `Spec:` para `feat|fix|test|refactor`.
- Mudança de arquitetura exige ADR **novo** em `docs/adr/NNNN-titulo.md` (próximo número livre: 0024).
- Hooks e adaptadores de **agente** falham abertos; os gates de **commit/CI** falham fechados (são coisas diferentes e não se misturam).
- Modo `auto` mantém o comportamento do ADR 0002 até um ADR novo o redefinir para o cenário multiusuário. Durante toda a migração a allowlist do dono e do dispositivo na Lambda atual não é enfraquecida; o caminho do dono continua funcionando até o relay estar validado.
- Nunca ler segredos, comandos ou saídas em voz alta sem resumo e máscara. Conteúdo baixado é dado não confiável: nunca executar scripts de dentro dele; ferramentas baixadas por gates têm versão e checksum fixados.
- O endereço `ponte.heycode.dev.br` (instalação do dono) não é alterado por este programa até a migração ser aprovada.
- Commits pequenos, um por tarefa; mensagens e docs em português.

## Review Focus

1. **Agente enfraquece o gate** (`git commit --no-verify`, edita `gates.json`, `.github/workflows`, `AGENTS.md`, CODEOWNERS): esperado = o CI refaz tudo e falha, e caminhos protegidos exigem aprovação humana.
2. **Usuário A aciona a máquina de B** (reuso de ID de confirmação, `userId` Alexa forjado, código de pareamento reaproveitado ou adivinhado): esperado = recusa e registro, nunca execução.
3. **Relay fora do ar:** esperado = agentes do usuário seguem normais (falha aberta), a voz diz claramente o que está indisponível e nenhuma aprovação fica pendente para sempre.
4. **Máquina limpa Mac/Linux/Windows** sem PowerShell, caminho com espaços ou acentos, usuário sem administrador: esperado = instalação e `doctor` funcionam ou explicam exatamente o que falta.
5. **Segredo em log, telemetria ou saída que sobe ao relay:** esperado = mascarado na máquina antes de sair; teste com segredos de formato conhecido.
6. **Perda de acesso do dono** (domínio expira, conta Amazon/Cloud bloqueada, dono indisponível): esperado = segundo administrador e runbook permitem recuperar sem ele.

## Esteira de SDLC (obrigatória)

Toda mudança percorre as etapas, e cada etapa tem um artefato verificável. Agente nenhum pode pular etapa nem declarar "pronto" sem a evidência gerada pelo CI.

| # | Etapa | Artefato | Quem aprova |
|---|---|---|---|
| 1 | Intake | Issue com modelo (problema, usuário afetado, risco) | Mantenedor |
| 2 | Spec | `docs/superpowers/specs/*.md` com `Status: Aprovada` | **Humano** |
| 3 | ADR (se arquitetura) | `docs/adr/NNNN-*.md` novo | **Humano** nos caminhos sensíveis |
| 4 | Plano | `docs/superpowers/plans/*.md` com tarefas e interfaces | Revisão de agente independente |
| 5 | Implementação TDD | Teste falhando → código mínimo → teste verde | Gates locais |
| 6 | Revisão independente | Agente de contexto novo revisa o diff contra spec e plano | Check de CI `agent-review` |
| 7 | CI | Todos os gates abaixo, refeitos do zero, em matriz de SOs | Automático |
| 8 | Aprovação humana | Obrigatória em caminhos de `human_review_paths` e em qualquer mudança de gate | **Humano** (CODEOWNERS) |
| 9 | Merge | Squash, histórico linear, sem force push | Branch protection |
| 10 | Release | Semver por Conventional Commits, changelog, artefatos assinados e SBOM | Pipeline + humano na primeira vez |
| 11 | Operação | SLOs, alertas, runbook, resposta a incidente | Mantenedor de plantão |
| 12 | Retrospectiva | Falhas viram teste, gate ou ADR | Mantenedor |

**Definição de pronto:** spec e plano rastreáveis pelo trailer, testes novos para o comportamento, todos os gates verdes no CI (a saída do CI é a evidência, não o relato do agente), docs e changelog atualizados e, nos caminhos sensíveis, aprovação humana.

## Catálogo de gates

Local = hooks em `.githooks/` (rápidos). CI = autoridade final (hooks locais podem ser burlados, então o CI repete todos). "Falha fechada" vale para todos.

| ID | Gate | Onde | O que bloqueia |
|---|---|---|---|
| G1 | Formato e trailer de commit | commit-msg + CI (todo commit do PR) | Já existe; CI passa a validar o intervalo inteiro do PR |
| G2 | Spec aprovada | commit-msg + CI | `Spec:` aponta para spec sem `Status: Aprovada` |
| G3 | ADR novo para arquitetura | pre-commit + CI | Já existe; amplia `architecture_paths` (relay, protocolo, identidade, auth) |
| G4 | Teste junto do código | pre-commit + CI | `feat`/`fix` que muda código sem mudar teste |
| G5 | Segredos | pre-commit + CI | Segredo no diff ou no histórico do PR (gitleaks) |
| G6 | Lint, formato e tipos | pre-commit + CI | ruff, mypy; checagem de JS no `skill/lambda` |
| G7 | Testes e cobertura | pre-push + CI | Testes falhando; cobertura de linha do diff abaixo do piso; `bridge/policy` com cobertura de ramo de 100% |
| G8 | Cadeia de suprimentos | CI | Dependência sem trava de versão, vulnerabilidade conhecida, licença incompatível, ação de CI sem versão fixada por hash |
| G9 | Contrato de protocolo | CI | Mudança no esquema sem subir a versão e sem teste de compatibilidade |
| G10 | Modelo de ameaça | CI | Mudança em auth, identidade, relay ou política sem atualizar `docs/security/threat-model.md` ou citar ADR que o faça |
| G11 | Proteção dos gates | CI + CODEOWNERS | Qualquer alteração em `scripts/gates/**`, `.githooks/**`, `.github/**`, `AGENTS.md`, `CLAUDE.md`, `.claude/**`, `CODEOWNERS` sem aprovação humana |
| G12 | Tamanho | CI | PR com mais de N linhas ou mais de uma tarefa do plano; N definido na spec P0 |
| G13 | Docs e changelog | CI | Mudança visível ao usuário sem entrada de docs/changelog |
| G14 | Multiplataforma | CI | Falha em Windows, macOS ou Linux, Python 3.11 a 3.14 |
| G15 | Revisão independente | CI | Sem check `agent-review` verde de um agente de contexto novo; aprovação humana em `human_review_paths` |
| G16 | Evidência | PR template + CI | PR sem seção "Evidência" preenchida por saída colada de comando real |

## Domínio, DNS e o que mais a comunidade exige

O domínio e o DNS são a menor parte. Para a comunidade só instalar o MCP e a skill, o HeyCode passa a operar um serviço, e serviço tem custo e responsabilidade.

| Item | Por que | Padrão recomendado (confirmar por ADR) | Trilha |
|---|---|---|---|
| Registros DNS | Endereços estáveis | `api.` (skill, OAuth, WebSocket do relay), `app.` (login e pareamento), `docs.`, `status.`, mais `staging-*`. `ponte.` do dono fica intacto | P3 |
| Hospedagem do relay | Compute com WebSocket | Contêiner em plataforma gerenciada ou VPS; critérios: custo previsível, região com boa latência para a Alexa, deploy reproduzível | P3 |
| Banco | Contas, instalações, dispositivos | Postgres gerenciado com backup e teste de restauração | P3 |
| TLS | HTTPS e account linking exigem | Certificados automáticos | P3 |
| Infraestrutura como código | Outro mantenedor reproduzir o ambiente | OpenTofu/Terraform no repositório, sem segredos | P3 |
| Segredos | Chaves do relay e OAuth | Gerenciador de segredos da plataforma, rotação documentada | P3 |
| E-mail do domínio | Lojas e usuários exigem privacidade e suporte | `privacy@`, `support@`, `security@` com SPF, DKIM e DMARC | P3 |
| Observabilidade | Saber que quebrou antes do usuário | Logs sem segredos, métricas, alertas, página de status | P3 |
| Teto de custo | Você paga a conta | Alerta e limite de orçamento, cotas por usuário, política gratuito/pago decidida em ADR | P3 |
| Conta de desenvolvedor Amazon | Publica a skill | Verificar se aceita administradores adicionais; se não, documentar o risco e o procedimento de migração | P4 |
| Nome de invocação "HeyCode" | A Amazon valida unicidade e regras | Reservar e testar cedo; checar também marca registrada | P4 |
| Documentos legais | Loja e LGPD exigem | Política de privacidade, termos de uso, retenção e exclusão de dados | P4 |
| Organização GitHub | Projeto sem dono único | Org com pelo menos dois owners | P0 |
| Registro de pacotes | Instalar sem clonar | PyPI (e npm se necessário) com publicação confiável por CI | P6 |
| Licença | Sem ela ninguém pode usar | Decisão em aberto, padrão sugerido Apache-2.0 | P0 |
| Canal da comunidade | Suporte sem passar por você | GitHub Discussions e modelos de issue | P6 |
| Continuidade (fator ônibus) | "Não depender de mim" | Segundo administrador do registrador (renovação automática e trava de domínio), da nuvem e do GitHub; runbooks de operação | P3, P6 |

## Decisões em aberto (cada uma vira ADR antes de código)

1. Licença (sugestão: Apache-2.0).
2. Nome e dono da organização GitHub; dois owners.
3. Componente local: daemon próprio, ou só MCP (o MCP é iniciado pelo cliente e não mantém conexão persistente; sugestão: daemon `heycode` + MCP fino).
4. Endpoint da skill: Lambda (atual) ou HTTPS próprio.
5. Hospedagem do relay e política gratuito/pago.
6. Modelo de ameaça do modo `auto` para multiusuário (sugestão: opt-in por instalação, confirmação no computador, nunca ligável só por voz na primeira vez).

## File Structure (alvo ao fim de P1–P3)

- `pyproject.toml`, `src/heycode/` (pacote instalável; substitui `bridge/` como raiz de import e resolve a sombra do pacote `mcp`).
- `src/heycode/{policy,store,supervisor,projects,dictation,mcp_server}/` (movidos de `bridge/`, `mcp` renomeado para `mcp_server`).
- `src/heycode/cli/` (`install-service`, `doctor`, `rotate-secret`, `pair`).
- `protocol/v1/*.schema.json` e `protocol/CHANGELOG.md` (contrato local↔relay).
- `relay/` (serviço em nuvem), `relay/migrations/`, `infra/` (IaC).
- `docs/{SDLC,SECURITY,CONTRIBUTING,OPERATIONS}.md`, `docs/security/threat-model.md`, `docs/runbooks/`.
- `scripts/gates/` (gates; ver P0), `.github/{workflows,CODEOWNERS,pull_request_template.md,ISSUE_TEMPLATE/}`.

---

## P0 Esteira e SDLC (primeiro, antes de qualquer outra trilha)

### Task P0.1: Spec da esteira e `docs/SDLC.md`

**Files:**
- Create: `docs/superpowers/specs/2026-11-13-esteira-obrigatoria-de-agentes.md`, `docs/SDLC.md`, `docs/adr/0024-esteira-obrigatoria-de-agentes.md`

**Interfaces:**
- Produces: valores finais de G1–G16 (pisos de cobertura, N de G12, lista de `protected_paths` e `human_review_paths`) em `Status: Aprovada`.

- [ ] **Step 1:** Promover o catálogo desta página a spec, com pisos e limites numéricos explícitos e critérios de aceite por gate.
- [ ] **Step 2:** Escrever `docs/SDLC.md` (etapas e Definição de pronto acima) e o ADR 0024.
- [ ] **Step 3:** Colocar `Status: Aprovada` nas specs existentes que já valem (migração para o gate G2), sem alterar o conteúdo.
- [ ] **Step 4:** Revisão humana e aprovação da spec. Sem ela, as tarefas P0.2 em diante não começam.
- [ ] **Step 5: Commit** `docs: define esteira obrigatoria de agentes` (isento de trailer).

### Task P0.2: Gate G2 (spec aprovada) e configuração v2

**Files:**
- Create: `scripts/gates/spec_status.py`, `tests/gates/test_spec_status.py`
- Modify: `scripts/gates/commit_msg.py`, `scripts/gates/gates.json`

**Interfaces:**
- Produces: `check_spec_approved(spec_path: Path) -> list[str]` (lista de erros, vazia se ok); novas chaves em `gates.json`: `protected_paths: list[str]`, `human_review_paths: list[str]`, `max_diff_lines: int`, `coverage_floor: int`.
- Consumes: `check_commit_message(message, repo_root, config)` existente.

- [ ] **Step 1:** Testes em `tests/gates/test_spec_status.py`: `test_spec_aprovada_passa`, `test_spec_rascunho_falha`, `test_spec_sem_status_falha`, `test_commit_feat_com_spec_rascunho_falha_no_commit_msg`.
- [ ] **Step 2:** Rodar `python -m pytest tests/gates -v`; esperado FAIL (módulo inexistente).
- [ ] **Step 3:** Implementar `check_spec_approved` lendo a linha `Status:` do cabeçalho da spec e integrar em `check_commit_message` após a checagem de existência.
- [ ] **Step 4:** Ampliar `architecture_paths` com `relay/*`, `protocol/*`, `src/heycode/policy/*`, `src/heycode/store/*`, `src/heycode/supervisor/*`, `src/heycode/mcp_server/*` (mantendo os atuais até a mudança de pacote em P1).
- [ ] **Step 5:** Rodar `python -m pytest tests/gates -v`; esperado PASS.
- [ ] **Step 6: Commit** `feat: exige spec aprovada no gate de commit` com `Spec: docs/superpowers/specs/2026-11-13-esteira-obrigatoria-de-agentes.md`.

### Task P0.3: Gate G4 (teste junto do código) e G12 (tamanho)

**Files:**
- Create: `tests/gates/test_tests_with_code.py`
- Modify: `scripts/gates/pre_commit.py`, `scripts/gates/gates.json`

**Interfaces:**
- Consumes: `_read_staged() -> list[tuple[str, str]]` e `check_staged(staged, config)`.
- Produces: `check_tests_with_code(staged, commit_type, config) -> list[str]`; `check_diff_size(added_lines: int, config) -> list[str]`.

- [ ] **Step 1:** Testes: `test_feat_com_codigo_sem_teste_falha`, `test_fix_com_teste_e_codigo_passa`, `test_docs_isento`, `test_diff_acima_do_limite_falha`, `test_apenas_teste_ou_doc_passa`.
- [ ] **Step 2:** Rodar `python -m pytest tests/gates -v`; esperado FAIL.
- [ ] **Step 3:** Implementar as duas funções. O tipo do commit vem do arquivo de mensagem (no pre-commit ainda não existe; por isso G4 também roda no CI sobre cada commit do intervalo, e no hook local só avisa sobre o que for decidível pelo staging).
- [ ] **Step 4:** Rodar `python -m pytest tests/gates -v`; esperado PASS.
- [ ] **Step 5: Commit** `feat: adiciona gates de teste junto do codigo e de tamanho` com trailer `Spec:`.

### Task P0.4: Gates G5 (segredos) e G6 (lint e tipos) com bootstrap seguro

**Files:**
- Create: `scripts/gates/bootstrap.py`, `.gitleaks.toml`, `ruff.toml`, `tests/gates/test_bootstrap.py`
- Modify: `.githooks/pre-commit`, `requirements-dev.txt`

**Interfaces:**
- Produces: `ensure_tool(name: str, version: str, sha256: dict[str, str]) -> Path` (baixa binário fixado, confere checksum e **nunca executa nada de dentro do download além do binário verificado**); `run_secret_scan(staged_only: bool) -> list[str]`.

- [ ] **Step 1:** Testes: `test_checksum_invalido_recusa_binario`, `test_segredo_conhecido_no_diff_falha` (usar um token falso no formato do provedor), `test_ferramenta_ausente_falha_fechada`.
- [ ] **Step 2:** Rodar `python -m pytest tests/gates/test_bootstrap.py -v`; esperado FAIL.
- [ ] **Step 3:** Implementar o bootstrap e a chamada do gitleaks e do ruff no pre-commit; ferramenta ausente é erro, não aviso.
- [ ] **Step 4:** Rodar `python -m pytest tests/gates -v`; esperado PASS. Rodar o hook sobre um arquivo com token falso e confirmar bloqueio.
- [ ] **Step 5: Commit** `feat: gates de segredos e lint no pre-commit` com trailer `Spec:`.

### Task P0.5: Gates de CI (autoridade) para G1–G16

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/agent-review.yml`, `scripts/gates/ci_range.py`, `tests/gates/test_ci_range.py`
- Modify: `scripts/gates/gates.json`

**Interfaces:**
- Produces: `check_range(base: str, head: str, config: dict) -> list[str]` que aplica G1, G2, G3, G4 a **cada commit** entre `base` e `head`; `check_protected(changed: list[str], config) -> list[str]` (G11).

- [ ] **Step 1:** Testes: `test_commit_sem_trailer_no_meio_do_pr_falha`, `test_no_verify_nao_escapa_do_ci`, `test_alteracao_em_gates_json_exige_aprovacao_humana`, `test_alteracao_em_workflows_exige_aprovacao_humana`.
- [ ] **Step 2:** Rodar `python -m pytest tests/gates/test_ci_range.py -v`; esperado FAIL.
- [ ] **Step 3:** Implementar `check_range` e `check_protected`; o workflow roda a matriz Windows, macOS e Linux, Python 3.11 a 3.14 (G14), pytest com cobertura (G7), `pip-audit`, `npm audit`, verificação de ações fixadas por hash (G8) e o job `agent-review` (G15).
- [ ] **Step 4:** Rodar `python -m pytest tests/gates -v`; esperado PASS. Abrir PR de teste que viola cada gate e confirmar o bloqueio (o resultado vira a evidência de G16).
- [ ] **Step 5: Commit** `feat: adiciona esteira de CI como autoridade dos gates` com trailer `Spec:`.

### Task P0.6: Repositório remoto, proteção de branch e governança (ações do dono)

**Files:**
- Create: `.github/CODEOWNERS`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/*.md`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- Modify: `AGENTS.md` (remover "o remoto GitHub ainda não está configurado" e apontar para `docs/SDLC.md`)

**Interfaces:**
- Consumes: `protected_paths` e `human_review_paths` de `gates.json` (CODEOWNERS espelha as mesmas listas; um teste garante que não divergem).

- [ ] **Step 1:** **Ação do dono (publicação é externa e difícil de reverter):** criar o repositório na conta pessoal do dono, adicionar uma colaboradora administradora de confiança, criar a identidade separada dos agentes (conta-robô ou GitHub App, token de escopo mínimo) e escolher a licença (decisão 1). Ver "Revisão de 2026-11-13" na spec.
- [ ] **Step 2:** Configurar ruleset em `main`: PR obrigatório, checks de G1–G16 obrigatórios, histórico linear, sem force push, revisão obrigatória dos CODEOWNERS, commits assinados, aprovações antigas descartadas a cada novo push.
- [ ] **Step 3:** Teste `test_codeowners_espelha_gates_json` em `tests/gates/`; rodar e esperar PASS.
- [ ] **Step 4:** Antes do primeiro push público, rodar o gitleaks sobre **todo o histórico** e confirmar que não há segredo nos 46 commits atuais nem em `bridge/bridge.db`/`.env` versionados.
- [ ] **Step 5: Commit** `docs: adiciona governanca, licenca e protecao de branch` (isento de trailer, mas passa por G11 por tocar `AGENTS.md` e `.github/`).

---

## P1 Fundação publicável (marco: instala em máquina limpa)

### Task P1.1: Spec e ADRs de empacotamento
- [ ] Spec de pacote instalável, CLI e diretório de dados do usuário. ADRs: pacote `heycode` com `src/`; renomear `bridge/mcp` para `mcp_server`; componente local (decisão 3); faixa de Python suportada.

### Task P1.2: Pacote instalável
- [ ] `pyproject.toml`, mover `bridge/*` para `src/heycode/*`, ajustar imports e testes, remover o truque de carga de módulo do ADR 0006. **Pronto quando:** `pipx install .` num ambiente limpo e `heycode --version` funcionam, e a suíte de testes existente segue verde.

### Task P1.3: Estado e segredos fora do código
- [ ] Banco e `.env` no diretório de dados do usuário (permissões restritas); migração do `bridge.db` existente sem perda; nada de estado dentro do pacote.

### Task P1.4: CLI multiplataforma
- [ ] `heycode install-service` (Tarefa Agendada, launchd ou systemd), `uninstall-service`, `rotate-secret`, `doctor` (distingue Alexa, DNS, túnel/relay, autenticação, ponte e agente; cobre o M0). Os `.ps1` atuais viram invólucros finos ou são removidos. **Pronto quando:** testes em Windows, macOS e Linux no CI e `doctor` explica cada falha provocada.

### Task P1.5: Documentação de entrada
- [ ] README em duas trilhas (usar, contribuir), `docs/OPERATIONS.md`, guia "do zero ao primeiro status em N minutos" (meta de tempo medida no CI de máquina limpa).

---

## P2 Contratos e segurança multiusuário (antes de M1/M2)

### Task P2.1: Specs e ADRs
- [ ] Specs: protocolo local↔relay; identidade e pareamento; modelo de ameaça do relay e do `auto`; contrato de adaptador de agente. ADRs correspondentes, mais "Lambda ou HTTPS próprio" (decisão 4).

### Task P2.2: Protocolo `protocol/v1`
- [ ] Esquemas JSON versionados (mensagens de status, decisão, instrução, resultado), regras de compatibilidade e teste de contrato que roda cliente e servidor de versões vizinhas (G9).

### Task P2.3: Identidade por instalação
- [ ] Substituir o segredo compartilhado, no caminho do relay, por chave por instalação com assinatura, rotação e revogação; o caminho atual do dono continua intacto. Testes: chave revogada recusada, replay recusado, relógio dessincronizado tolerado dentro de limite.

### Task P2.4: Modelo de ameaça e `auto`
- [ ] `docs/security/threat-model.md` (relay vê comandos e saídas; mascaramento na máquina antes de enviar; retenção; abuso). ADR que redefine `auto` para multiusuário (decisão 6). Testes: `auto` não pode ser ligado por outra conta nem por dispositivo não associado.

### Task P2.5: Contrato de adaptador
- [ ] Interface e catálogo de capacidades declaradas (iniciar, instruir sessão aberta, cancelar, retomar, ler resultado) e teste de conformidade que cada adaptador (Claude Code, Codex, Aider) executa no CI.

---

## P3 Relay MVP em `heycode.dev.br` (staging primeiro)

### Task P3.1: Spec de relay, operação e custos
- [ ] Spec: contas, pareamento por código curto (uso único, validade curta, confirmado nos dois lados), roteamento, múltiplas máquinas, limites de latência para a Alexa (resposta rápida com continuação assíncrona), cotas e política de custo. ADRs de hospedagem e banco.

### Task P3.2: Infraestrutura mínima
- [ ] DNS `staging-api.` e `staging-app.`, hospedagem, Postgres com backup e restauração testada, TLS, e-mail do domínio, IaC no repositório, segredos fora do código, alertas de custo. **Pronto quando:** outra pessoa reconstrói o ambiente de staging só com o repositório e os runbooks.

### Task P3.3: Serviço do relay
- [ ] Cadastro/login, servidor OAuth2 para account linking, pareamento, WebSocket de saída da máquina, roteamento por conta e instalação, limite de taxa, logs sem segredos. Testes de isolamento: usuário A nunca recebe, aciona ou lê dados de B (incluindo corridas e IDs reaproveitados). Teste de falha: relay cai e o componente local reconecta sozinho.

### Task P3.4: Componente local conectado
- [ ] `heycode pair` e conexão de saída persistente com reconexão e backoff, falha aberta para os agentes. **Pronto quando:** uma tarefa de teste vai de uma chamada ao relay até o agente local e volta, sem túnel individual.

---

## P4 Skill compartilhada em beta fechado

### Task P4.1: Spec e documentos legais
- [ ] Spec: nome de invocação, account linking, associação de dispositivo por pessoa e instalação, consentimento. Política de privacidade, termos, retenção e exclusão (LGPD); `privacy@` e `support@` ativos.

### Task P4.2: Skill multiusuário
- [ ] Endpoint conforme o ADR (decisão 4), identificação da conta vinculada, escolha de máquina quando houver mais de uma, revogação de dispositivo. O caminho do dono (Lambda atual com allowlist) continua até o beta validar.

### Task P4.3: Beta fechado
- [ ] Publicar a skill em modo de teste para um grupo pequeno de convidados (verificar o limite atual de testadores da Amazon), roteiro de teste, coleta de falhas reais, ajuste do modelo de interação em português (sotaques, nomes de projeto, termos de programação). **Pronto quando:** pelo menos duas pessoas externas completam instalação, pareamento e um fluxo de voz usando só a documentação.

---

## P5 Funcionalidade dos marcos do roadmap (em paralelo à P3/P4, sobre os contratos de P2)

### Task P5.1: Especificar e executar M0–M3
- [ ] Uma spec e um plano por marco do `docs/ROADMAP-HEYCODE.md`, nesta ordem: M0 (confiabilidade e confirmação atômica por ID e destino), M1 (listar e entender execuções, visão de evidências no computador antes de M2), M2 (conduzir trabalho por voz), M3 (conversa natural; a camada de LLM opcional em trilha própria). Cada marco herda os gates da P0 e o contrato da P2.

---

## P6 Abertura pública

### Task P6.1: Spec e lançamento
- [ ] Certificação da skill na loja; produção em `api.`/`app.`/`docs.`/`status.`; publicação no PyPI com publicação confiável por CI, assinatura e SBOM; site de docs; Discussions e modelos de issue; `docs/OPERATIONS.md` e runbooks revisados por quem não é o dono; segundo administrador em registrador, nuvem e GitHub; ensaio de incidente (relay fora do ar, chave vazada, domínio quase expirando).
- [ ] **Pronto quando:** uma pessoa externa instala em máquina limpa, conecta pelo menos dois agentes, executa um fluxo de voz e diagnostica uma falha só com a documentação, e o dono fica ausente por duas semanas sem que nada pare.

## Self-Review

- **Cobertura:** gates e SDLC (P0), domínio/DNS e itens além (seção própria), instalação sem depender do dono (P1, P6), contratos e segurança (P2), relay e skill (P3, P4), roadmap M0–M3 (P5), fator ônibus (P3, P6).
- **Proporção:** só P0 tem passos e assinaturas, pois é a única trilha executável hoje; as demais dependem de spec aprovada (regra do `AGENTS.md`) e receberão plano detalhado depois dela.
- **Riscos assumidos:** pisos numéricos de G7 e G12 ainda não definidos (a spec P0.1 os fixa); o limite de testadores da Amazon e a possibilidade de administradores adicionais na conta de desenvolvedor precisam ser verificados na documentação atual antes de P4.
