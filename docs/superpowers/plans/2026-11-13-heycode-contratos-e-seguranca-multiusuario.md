# HeyCode contratos e segurança multiusuário (P2): plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Entregar os contratos que o relay (P3) e a skill compartilhada (P4) vão obedecer: protocolo `v1`, identidade por instalação, modelo de ameaça com `auto` multiusuário e contrato de adaptador, sem tocar o caminho do dono.

**Architecture:** Código novo em módulos isolados (`src/heycode/protocol`, `src/heycode/identity`, `src/heycode/adapters`) sem alterar `app.py` nem a política atual. Cada contrato tem teste que o prova.

**Tech Stack:** Python 3.11–3.14, Pydantic, `jsonschema`, `cryptography` (Ed25519), pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md` (aprovada). ADRs 0029–0033.

## Global Constraints

- Commits `feat|fix|test|refactor` com trailer `Spec:` apontando para a spec acima; `docs`/`chore` isentos. Um commit por tarefa, em português.
- O caminho atual do dono (Lambda, segredo, allowlist, ADR 0002) **não muda**; a suíte existente deve seguir verde.
- Dependências novas com versão fixada (G8). Arquivos em `src/heycode/policy|store|supervisor|mcp_server` e `protocol/` contam como arquitetura (G3): os ADRs 0029–0033 já cobrem.
- Segredo nunca entra em envelope; mascarar antes (função de máscara existente em `heycode.policy`).
- Falhas de adaptador falham abertas; identidade falha fechada (assinatura inválida = recusa).

## Review Focus

1. Conta A aciona instalação de B (ID reaproveitado, `installation_id` forjado no payload).
2. Replay, relógio dessincronizado, chave revogada ou rotacionada.
3. Código de pareamento reaproveitado, expirado, adivinhado ou confirmado em um lado só.
4. `auto` ligado por outra conta, dispositivo não associado ou só por voz na primeira vez.
5. Segredo no payload que sobe ao relay.

## Task P2.1: Protocolo `protocol/v1`

**Files:** Create `protocol/v1/*.schema.json` (envelope, status, decision-request, decision-response, instruction, run-result, pair-request, pair-confirm, error), `protocol/CHANGELOG.md`, `src/heycode/protocol/__init__.py`, `src/heycode/protocol/envelope.py`, `tests/protocol/test_contract.py`. Modify `requirements*.txt` (jsonschema fixado).

**Interfaces:** Produces `validate(message: dict) -> None` (levanta `ProtocolError("unsupported_version"|"invalid")`), `SUPPORTED_VERSIONS: frozenset[int]`.

- [ ] **Step 1:** Testes: `test_envelope_valido_passa`, `test_versao_maior_recusada_unsupported_version`, `test_campo_desconhecido_ignorado`, `test_campo_obrigatorio_ausente_falha`, `test_vizinhas_compat_cliente_v1_servidor_v1_com_campo_novo_opcional`.
- [ ] **Step 2:** `python -m pytest tests/protocol -v`; esperado FAIL.
- [ ] **Step 3:** Escrever esquemas e `validate`.
- [ ] **Step 4:** `python -m pytest tests/protocol -v`; esperado PASS.
- [ ] **Step 5:** Commit `feat: adiciona protocolo local-relay v1` com `Spec:`.

## Task P2.2: Identidade (chave, assinatura, anti-replay, revogação)

**Files:** Create `src/heycode/identity/{keys,signing,replay,registry}.py`, `tests/identity/test_identity.py`. Modify dependências (`cryptography` fixado).

**Interfaces:** Produces `generate_keypair(data_dir) -> PublicKey` (privada em arquivo `0600`), `sign(envelope, key) -> str`, `verify(envelope, public_key, now) -> None` (levanta `IdentityError`), `ReplayWindow(ttl=600, skew=120).check(id, ts, now)`, `Registry.revoke(installation_id)` / `is_revoked`. Consumes `validate` (P2.1).

- [ ] **Step 1:** Testes: `test_assinatura_valida_passa`, `test_payload_adulterado_recusado`, `test_replay_recusado`, `test_relogio_dentro_de_2min_aceito`, `test_relogio_fora_de_2min_recusado`, `test_chave_revogada_recusada`, `test_rotacao_assinada_pela_chave_antiga`, `test_chave_privada_com_permissao_restrita`.
- [ ] **Step 2:** `python -m pytest tests/identity -v`; esperado FAIL.
- [ ] **Step 3:** Implementar JSON canônico (chaves ordenadas, sem espaços) e as quatro peças.
- [ ] **Step 4:** Rodar; esperado PASS.
- [ ] **Step 5:** Commit `feat: identidade por instalacao com Ed25519` com `Spec:`.

## Task P2.3: Pareamento

**Files:** Create `src/heycode/identity/pairing.py`, `tests/identity/test_pairing.py`.

**Interfaces:** Produces `PairingService(clock).issue(account_id) -> Code` (8 chars, alfabeto sem ambíguos, 5 min), `.redeem(code, installation_pubkey) -> Pending`, `.confirm(pending_id, side)`; vínculo só quando `side` cobrir `"account"` e `"machine"`.

- [ ] **Step 1:** Testes: `test_codigo_uso_unico`, `test_codigo_expira_em_5min`, `test_limite_de_5_tentativas_bloqueia_codigo`, `test_confirmacao_so_de_um_lado_nao_vincula`, `test_codigo_de_outra_conta_nao_vincula`.
- [ ] **Step 2:** Rodar; esperado FAIL.
- [ ] **Step 3:** Implementar com relógio injetável.
- [ ] **Step 4:** Rodar; esperado PASS.
- [ ] **Step 5:** Commit `feat: pareamento por codigo curto` com `Spec:`.

## Task P2.4: Isolamento entre contas e `auto` multiusuário

**Files:** Create `src/heycode/identity/routing.py`, `src/heycode/identity/auto_mode.py`, `tests/identity/test_isolation.py`, `docs/security/threat-model.md`.

**Interfaces:** Produces `Router.route(account_id, installation_id, envelope) -> Installation` (levanta se a instalação não pertence à conta), `Confirmation.bind(operation, destination, installation_id)` de uso único, `AutoMode.enable(installation_id, *, confirmed_on_machine: bool, by_account)`.

- [ ] **Step 1:** Testes: `test_conta_a_nao_aciona_instalacao_de_b`, `test_installation_id_forjado_no_payload_ignorado`, `test_confirmacao_nao_vale_para_outro_destino`, `test_confirmacao_nao_reutilizavel`, `test_auto_so_liga_com_confirmacao_no_computador`, `test_auto_nao_liga_por_outra_conta`, `test_auto_nao_liga_por_dispositivo_nao_associado`, `test_segredo_mascarado_antes_de_sair`, `test_relay_fora_nao_trava_agente`.
- [ ] **Step 2:** Rodar `python -m pytest tests/identity/test_isolation.py -v`; esperado FAIL.
- [ ] **Step 3:** Implementar; escrever `threat-model.md` com cada linha da tabela do §5 da spec apontando para o teste acima.
- [ ] **Step 4:** Rodar; esperado PASS.
- [ ] **Step 5:** Commit `feat: isolamento por conta e auto multiusuario` com `Spec:`.

## Task P2.5: Contrato de adaptador

**Files:** Create `src/heycode/adapters/{__init__,base}.py`, `tests/adapters/conformance.py`, `tests/adapters/test_conformance.py`. Modify os adaptadores existentes do supervisor (Claude Code, Codex, Aider) apenas para expor `capabilities()` sem mudar comportamento.

**Interfaces:** Produces `AgentAdapter` (Protocol), `Capability` (enum), `UnsupportedCapability`.

- [ ] **Step 1:** Testes de conformidade parametrizados pelos três adaptadores: `test_declara_capacidades`, `test_chamar_nao_declarada_levanta_unsupported`, `test_erro_do_adaptador_nao_derruba_o_agente`.
- [ ] **Step 2:** Rodar; esperado FAIL.
- [ ] **Step 3:** Implementar interface e expor capacidades nos adaptadores.
- [ ] **Step 4:** `python -m pytest -q`; esperado suíte inteira PASS (inclui o caminho do dono).
- [ ] **Step 5:** Commit `feat: contrato de adaptador de agente` com `Spec:`.

## Self-Review

- Cobertura: protocolo (P2.1), identidade e anti-replay (P2.2), pareamento (P2.3), isolamento, `auto` e modelo de ameaça (P2.4), adaptadores (P2.5); todos os critérios de aceite 1–7 da spec têm tarefa.
- Risco: G12 pode reprovar PR único; empilhar um PR por tarefa se necessário.
