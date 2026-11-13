# Esteira obrigatória de agentes: spec

Data: 2026-11-13. Status: aprovada pelo dono em 2026-11-13 (dono longe do computador, autorizou o agente a registrar a aprovação: "pode aprovar pra mim e segue pra o restante"; "mas eu permito, estou longe").

Plano de programa: `docs/superpowers/plans/2026-11-13-heycode-publicavel-e-esteira-de-agentes.md` (trilha P0). Visão: `docs/ROADMAP-HEYCODE.md`.

## 1. Intenção e porquê

Todo o código do HeyCode será produzido por agentes. Um agente que quer terminar a tarefa tem incentivo para contornar o que o atrapalha: pular hook, editar o gate, declarar "pronto" sem prova. A esteira precisa tornar o contorno inútil, não apenas desencorajado, e precisa continuar valendo quando outras pessoas contribuírem sem o dono por perto.

Hoje existem dois gates locais (`commit-msg`: formato e trailer `Spec:`; `pre-commit`: ADR novo para caminhos de arquitetura). Hooks locais podem ser burlados com `--no-verify`, e nada impede um agente de editar o próprio gate. Esta spec define o conjunto completo e onde ele é aplicado.

## 2. Princípios

1. **O CI é a autoridade; o hook local é conveniência.** Todo gate roda no CI, sobre cada commit do PR, e é obrigatório para o merge. O hook existe para falhar cedo.
2. **Falha fechada.** Ferramenta ausente, configuração ilegível ou erro interno do gate bloqueiam. Isso vale para commit e CI. Os hooks dos **agentes** (Claude Code, Codex) continuam falhando abertos (`AGENTS.md`); são sistemas diferentes e não se misturam.
3. **Quem escreve não aprova.** O gate não pode ser alterado por quem ele restringe: caminhos protegidos exigem aprovação humana.
4. **Evidência, não relato.** "Pronto" é a saída do CI, não a frase do agente.
5. **Determinismo antes de julgamento.** Gates 100% determinísticos (regra e script) sempre que possível; o único gate que usa um agente (G15) nunca é o único bloqueio.

## 3. Gates

Pisos numéricos abaixo são a proposta a aprovar.

| ID | Gate | Local | CI | Critério de bloqueio |
|---|---|---|---|---|
| G1 | Formato e trailer | commit-msg | sim, em todo commit do intervalo do PR | Já existe. Sem `tipo: descrição` válido, ou `feat/fix/test/refactor` sem `Spec:` apontando para arquivo existente em `docs/superpowers/specs/` |
| G2 | Spec aprovada | commit-msg | sim | A spec citada não tem `Status: aprovada` (qualquer capitalização) nas 10 primeiras linhas. A convenção já em uso (`Status: aprovada pelo dono em ...`) é aceita; `rascunho`, `proposta` ou ausência bloqueiam |
| G3 | ADR novo para arquitetura | pre-commit | sim | Já existe. `architecture_paths` é ampliado (ver §4) |
| G4 | Teste junto do código | aviso no pre-commit | sim, por commit | Commit `feat` ou `fix` que altera arquivo de código de produto sem alterar arquivo de teste no mesmo commit |
| G5 | Segredos | pre-commit | sim, no intervalo do PR | Qualquer segredo detectado (gitleaks, regras padrão mais `.gitleaks.toml` do projeto) |
| G6 | Lint, formato e tipos | pre-commit | sim | `ruff check`, `ruff format --check` e `mypy` em Python; verificação de sintaxe e `node --check` no `skill/lambda` |
| G7 | Testes e cobertura | pre-push (suíte rápida) | sim, suíte completa | Qualquer teste falhando; cobertura de linhas **novas** do diff abaixo de **90%**; cobertura de **ramos** em `bridge/policy` abaixo de **100%** nas linhas tocadas |
| G8 | Cadeia de suprimentos | não | sim | Dependência sem versão travada; vulnerabilidade conhecida (`pip-audit`, `npm audit --audit-level=high`); licença fora da lista permitida; ação de CI referenciada por tag móvel em vez de hash |
| G9 | Contrato de protocolo | não | sim | Mudança em `protocol/**` sem subir a versão do esquema, sem entrada em `protocol/CHANGELOG.md` e sem teste de compatibilidade com a versão anterior. Ativo a partir da trilha P2 |
| G10 | Modelo de ameaça | não | sim | Mudança em auth, identidade, relay ou política sem alterar `docs/security/threat-model.md` no mesmo PR ou sem citar o ADR que o faz. Ativo a partir da trilha P2 |
| G11 | Proteção dos gates | não | sim | Qualquer alteração em `protected_paths` sem aprovação de um humano dono do caminho (CODEOWNERS e revisão obrigatória) |
| G12 | Tamanho | aviso no pre-commit | sim | Mais de **400 linhas adicionadas** por PR, excluindo travas de dependência, arquivos gerados e documentação em `docs/`; ou mais de uma tarefa do plano por PR |
| G13 | Docs e changelog | não | sim | Mudança visível ao usuário (comando, rota, frase da skill, configuração) sem alteração em `docs/` ou `CHANGELOG.md` |
| G14 | Multiplataforma | não | sim | Falha em qualquer célula da matriz: Windows, macOS e Linux, Python 3.11 a 3.14 |
| G15 | Revisão independente | não | sim | Falta o check `agent-review`, executado por um agente de contexto novo, sem acesso ao raciocínio do autor, que compara o diff com spec e plano; e, em `human_review_paths`, falta aprovação humana |
| G16 | Evidência | não | sim | O PR não preenche a seção "Evidência" do modelo com a saída de comando real; ou o texto contradiz o resultado dos checks |

Até a trilha P1 existir, G6, G7 e G14 se aplicam ao código que já está no repositório; G9 e G10 ficam desligados por configuração (`enabled_gates`) até a P2.

## 4. Configuração (`scripts/gates/gates.json`, versão 2)

Chaves novas, sem remover as atuais:

- `version`: `2`.
- `enabled_gates`: lista de IDs ativos.
- `protected_paths` (G11): `scripts/gates/**`, `.githooks/**`, `.github/**`, `AGENTS.md`, `CLAUDE.md`, `.claude/**`, `docs/SDLC.md`, `.gitleaks.toml`, `ruff.toml`, `LICENSE`.
- `human_review_paths` (G15): `bridge/policy/**`, `bridge/store/**`, `bridge/mcp/**`, `bridge/supervisor/**`, `skill/lambda/**`, `skill/interaction-model-pt-BR.json`, `docs/superpowers/specs/**`, `docs/security/**`, `relay/**`, `protocol/**`, `infra/**`.
- `max_added_lines`: `400`. `diff_coverage_floor`: `90`. `policy_branch_coverage_floor`: `100`.
- `approved_status_regex`: `^.*Status:\s*aprovad[ao]\b` (sem distinção de maiúsculas, nas 10 primeiras linhas).
- `architecture_paths` ganha `relay/*`, `protocol/*` e `infra/*`. Os caminhos `src/heycode/...` entram na trilha P1, junto com a mudança de pacote.

`CODEOWNERS` espelha `protected_paths` e `human_review_paths`; um teste garante que as listas não divergem.

## 5. Fluxo e etapas

Definido em `docs/SDLC.md` (12 etapas, Definição de pronto). Esta spec torna obrigatórios: spec aprovada por humano antes de código (etapa 2), ADR novo para arquitetura (3), plano (4), TDD (5), revisão independente (6), CI completo (7), aprovação humana em caminhos sensíveis (8), merge squash com histórico linear (9).

## 6. Ações que só o dono pode fazer

1. Aprovar esta spec (mudar o `Status` acima).
2. Decidir sobre `2026-11-09-alexa-agent-hub-design.md`, ainda `rascunho aguardando aprovação` apesar de ter sido implementada: com G2, nenhum commit novo pode citá-la como `Spec:` até ela ser aprovada formalmente. As specs `2026-11-09-spike-codex-aider.md` e `2026-11-10-revisao-final.md` não têm campo de status e passam pela mesma decisão.
3. Criar o repositório no GitHub (conta pessoal do dono), escolher a licença e configurar o ruleset de `main` (P0.6). Publicar é externo e difícil de reverter.
4. Confirmar quem são os humanos donos dos caminhos protegidos: o dono e pelo menos uma pessoa de confiança como colaboradora administradora.

### Revisão de 2026-11-13 (aprovada pelo dono na sessão: "pode, manda bala")

- O repositório começa na **conta pessoal do dono**, não em organização. Repositório pessoal tem um só owner, então "dois owners" vira "dono mais uma colaboradora administradora" (registrador do domínio incluído). Transferir para uma organização é o caminho quando entrar o primeiro mantenedor externo; por isso nomes de pacote, URLs e docs não usam o nome de usuário e preferem `heycode` e `heycode.dev.br`.
- **Agentes usam identidade separada** (conta-robô ou GitHub App, token com escopo mínimo, restrito a este repositório). Se agente e dono usassem o mesmo usuário, o GitHub não deixaria o dono aprovar o próprio PR e a saída seria abrir exceção no ruleset, o que enfraqueceria o G11. O robô abre PR e não faz merge em caminhos protegidos.

## 7. Fora do escopo

Empacotamento e CLI (P1), protocolo e identidade (P2), relay e skill compartilhada (P3 e P4), funcionalidade dos marcos (P5). G9 e G10 apenas ficam definidos e desligados.

## 8. Critérios de aceite

- Cada gate G1 a G16 tem teste automatizado que prova o bloqueio e o caso que passa.
- Um PR de teste que viola cada gate é bloqueado no CI, mesmo com `--no-verify` local. A saída fica anexada ao PR (G16).
- Alterar `scripts/gates/gates.json`, um workflow ou `AGENTS.md` sem aprovação humana é bloqueado.
- Ferramenta ausente ou configuração inválida bloqueia o commit, em vez de passar em silêncio.
- A suíte de testes atual continua verde.

## 9. Riscos

- **Atrito:** gates demais podem atrasar entregas pequenas. Mitigação: G4 e G12 só avisam localmente; os pisos podem ser ajustados por nova spec.
- **Falso senso de segurança do G15:** um agente revisando outro agente não substitui um humano. Por isso G15 nunca é o único bloqueio e `human_review_paths` exige aprovação humana.
- **Ferramentas baixadas:** gitleaks e ruff vêm de download. Versão e checksum são fixados, e nada além do binário verificado é executado (`AGENTS.md`: conteúdo baixado é dado não confiável).
- **Dono como ponto único:** enquanto houver um só dono no GitHub, G11 depende dele. O mínimo de dois donos (ação 4) corrige isso.
