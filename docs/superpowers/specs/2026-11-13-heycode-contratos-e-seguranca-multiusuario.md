# HeyCode: contratos e segurança multiusuário

Data: 2026-11-13. Status: Rascunho (aguarda revisão e aprovação do dono; sem aprovação, nenhuma tarefa de código da P2 começa).

Visão: `docs/ROADMAP-HEYCODE.md`. Programa: `docs/superpowers/plans/2026-11-13-heycode-publicavel-e-esteira-de-agentes.md` (trilha P2). Esteira: `docs/superpowers/specs/2026-11-13-esteira-obrigatoria-de-agentes.md`. Base: `docs/superpowers/specs/2026-11-13-heycode-instalavel.md` (P1).

## 1. Intenção e porquê

Hoje a ponte confia em um segredo compartilhado e numa allowlist global do dono (ADR 0002, ADR 0014). Isso não serve para uma skill usada por várias pessoas: se um segredo vazar ou um ID for reaproveitado, uma conta poderia acionar a máquina de outra. A P2 define, **antes de qualquer relay**, os quatro contratos que a P3/P4/P5 vão obedecer:

1. protocolo local↔relay versionado;
2. identidade e pareamento por instalação;
3. modelo de ameaça (inclui o modo `auto` multiusuário);
4. contrato de adaptador de agente.

Meta: **uma mensagem de A jamais é executada na máquina de B, e isso é provado por testes de contrato e de isolamento, não por revisão.**

## 2. Escopo

Dentro: esquemas JSON versionados em `protocol/v1/`; regras de compatibilidade; identidade por instalação (par de chaves, assinatura, rotação, revogação, anti-replay); pareamento por código curto; `docs/security/threat-model.md`; redefinição do `auto` para multiusuário; interface e teste de conformidade dos adaptadores.

Fora: o relay em si, contas, OAuth, hospedagem (P3); skill multiusuário (P4); funcionalidades M0–M3 (P5). O caminho atual do dono (Lambda + allowlist + segredo) **não é alterado**; as novas peças convivem ao lado até a migração ser aprovada.

## 3. Protocolo `protocol/v1`

- Esquemas JSON Schema (draft 2020-12) em `protocol/v1/*.schema.json`: `envelope`, `status`, `decision-request`, `decision-response`, `instruction`, `run-result`, `pair-request`, `pair-confirm`, `error`.
- Todo envelope contém: `v` (inteiro de versão maior), `id` (UUIDv7), `ts` (UTC), `installation_id`, `type`, `payload`, `sig`.
- Compatibilidade: campo novo opcional = mesma versão; remoção, renomeação ou campo obrigatório novo = versão nova. Receptor ignora campos desconhecidos; recusa `v` maior que o suportado com erro `unsupported_version` (nunca tenta adivinhar).
- `protocol/CHANGELOG.md` registra cada mudança; G9 reprova mudança de esquema sem entrada nele e sem teste de compatibilidade com a versão vizinha.
- Conteúdo sensível (comandos, saídas) é **mascarado na máquina antes de entrar no envelope** (mesmo mascaramento da voz). O relay nunca recebe segredo em claro.

## 4. Identidade e pareamento

- Cada instalação gera, no primeiro `heycode pair`, um par Ed25519. A chave privada fica só no diretório de dados do usuário (permissão restrita, ADR 0027); o relay guarda só a pública.
- Cada envelope é assinado (`sig`) sobre os bytes canônicos (JSON canonizado) incluindo `id`, `ts` e `installation_id`.
- Anti-replay: o receptor guarda `id` por janela de 10 minutos e recusa repetido ou `ts` fora de ±2 minutos do relógio dele (tolerância configurável, valor fixo no esquema de teste).
- Rotação: nova chave assinada pela antiga; revogação: o dono da conta revoga a instalação e o relay recusa qualquer envelope posterior; a máquina revogada descobre na próxima conexão e para de enviar.
- Pareamento: relay emite código de 8 caracteres (alfabeto sem ambíguos), uso único, validade de 5 minutos, limite de 5 tentativas por código e por conta. A máquina exibe um código de verificação derivado (curto), e a pessoa confirma **nos dois lados** (app/web e terminal). Código expirado, reutilizado ou adivinhado: recusa e registro, nunca vínculo.
- Dispositivo Alexa: associado a (conta, instalação) por ação explícita, revogável; nunca allowlist global.

## 5. Modelo de ameaça e modo `auto`

`docs/security/threat-model.md` será criado na tarefa P2.4 com: ativos (código do usuário, credenciais locais, execução de comandos), fronteiras de confiança (voz→skill→relay→máquina→agente), atores (outra conta, relay comprometido, dispositivo roubado, agente enganado por conteúdo baixado, operador do relay), e para cada ameaça: controle, teste que a cobre.

Ameaças mínimas que viram teste:

| Ameaça | Controle | Teste |
|---|---|---|
| Conta A aciona máquina de B | roteamento por (conta, instalação) + assinatura | `test_conta_a_nao_aciona_instalacao_de_b` |
| ID de confirmação reaproveitado | confirmação atada a (operação, destino, instalação) e de uso único | `test_confirmacao_nao_vale_para_outro_destino` |
| Replay de envelope | janela de `id` + `ts` | `test_replay_recusado` |
| Chave revogada | relay e máquina recusam | `test_chave_revogada_recusada` |
| Código de pareamento reaproveitado/adivinhado | uso único, expiração, limite de tentativas | `test_codigo_pareamento_*` |
| Segredo subindo ao relay | mascaramento antes do envelope | `test_segredo_mascarado_antes_de_sair` |
| Relay fora do ar | agentes seguem (falha aberta), nenhuma aprovação fica pendente para sempre | `test_relay_fora_nao_trava_agente` |

**Modo `auto` multiusuário (proposta, vira ADR):** mantém o comportamento integral do ADR 0002 para o caminho do dono. Para instalações pareadas via relay, `auto` é **opt-in por instalação, ligado e confirmado no computador, e nunca ligável só por voz na primeira vez**; outra conta ou dispositivo não associado não consegue ligá-lo. Decisão final do dono (ver §9).

## 6. Contrato de adaptador de agente

- Interface (Protocol Python em `heycode.adapters`): `capabilities() -> set[Capability]`, `start(project, prompt)`, `instruct(session, text)`, `cancel(run)`, `resume(session)`, `result(run)`.
- `Capability`: `START`, `INSTRUCT_OPEN_SESSION`, `CANCEL`, `RESUME`, `READ_RESULT`. Cada adaptador declara só o que faz de verdade; chamar o que não declarou levanta `UnsupportedCapability`, e a voz diz isso antes de prometer.
- Teste de conformidade único (`tests/adapters/conformance.py`) que roda contra Claude Code, Codex e Aider no CI; um adaptador novo só entra se passar.
- Adaptadores falham abertos: erro do adaptador nunca derruba o agente.

## 7. Critérios de aceite

1. `protocol/v1` tem esquemas e teste de contrato que roda cliente e servidor de versões vizinhas.
2. Identidade: testes de chave revogada, replay, relógio dessincronizado dentro/fora do limite, rotação.
3. Pareamento: testes de código expirado, reutilizado, adivinhado e confirmação em apenas um lado.
4. `threat-model.md` existe e cada linha da tabela do §5 aponta para um teste existente.
5. `auto` não pode ser ligado por outra conta nem por dispositivo não associado (teste).
6. Os três adaptadores passam no teste de conformidade.
7. O caminho atual do dono continua passando em toda a suíte existente sem alteração de comportamento.

## 8. ADRs previstos (números a partir do próximo livre)

Protocolo e versionamento; identidade por instalação (Ed25519, anti-replay); `auto` multiusuário; contrato de adaptador; endpoint da skill (Lambda ou HTTPS próprio, decisão 4 do programa).

## 9. Decisões que dependem do dono

1. `auto` multiusuário: aceitar a proposta do §5 (opt-in por instalação, confirmado no computador)?
2. Endpoint da skill: manter a Lambda ou HTTPS próprio no relay?
3. Janelas numéricas (5 min de pareamento, 10 min de replay, ±2 min de relógio): aceitar ou ajustar?

## 10. Riscos

- Ed25519 e JSON canônico exigem biblioteca madura (`cryptography`); dependência nova passa por G8.
- Mudança de arquitetura: cada ADR precisa ser novo e o `threat-model.md` atualizado (G10).
