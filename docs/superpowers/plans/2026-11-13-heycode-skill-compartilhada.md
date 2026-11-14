# HeyCode skill compartilhada (P4): plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline).

**Goal:** Account linking OAuth2, requisições da Alexa verificadas, dispositivos autorizados por pessoa e escolha de máquina, no relay, sem tocar o caminho do dono.

**Architecture:** `src/heycode/relay/oauth.py` (servidor OAuth2), `alexa_verify.py` (assinatura e certificado), `devices.py` (associação e instalação padrão) e rotas novas em `relay/app.py`. Repositório SQLite ganha tabelas `oauth_codes`, `oauth_tokens`, `devices`, `device_requests`, e coluna `default_installation` em `accounts`.

**Spec:** `docs/superpowers/specs/2026-11-13-heycode-skill-compartilhada.md` (aprovada). ADRs 0041 a 0043.

## Global Constraints

- Commits `feat|fix|test|refactor` com `Spec:`; um por tarefa, em português. Caminho do dono intacto, suíte existente verde.
- Segredo, tokens e senha nunca em log; tokens só como hash; comparações em tempo constante.
- Falha fechada em tudo que autentica; nenhuma execução sem requisição verificada, conta vinculada e dispositivo autorizado.
- Config da Amazon só por variável de ambiente (`ALEXA_SKILL_ID`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OAUTH_REDIRECT_URIS`).

## Review Focus

1. Redirecionamento aberto ou código OAuth reaproveitado/trocado por outro cliente.
2. Reuso de refresh token (família inteira revogada).
3. Requisição da Alexa forjada (certificado de outro host, assinatura sobre outro corpo, replay antigo).
4. Dispositivo novo executando algo antes da aprovação; conta B aprovando dispositivo de A.
5. Exclusão da conta deixando token, conexão ou dado.

## Tasks

- **P4.2 OAuth2** (`oauth.py`, rotas `/oauth/*`, `tests/relay/test_oauth.py`): autorizar, trocar, renovar com rotação, PKCE, recusas; `current_account` aceita access token OAuth.
- **P4.3 Verificação Alexa** (`alexa_verify.py`, `tests/relay/test_alexa_verify.py`): URL do certificado, SAN, validade, cadeia, assinatura, timestamp, applicationId; certificado de teste gerado nos testes.
- **P4.4 Dispositivos, instalação padrão, `/v1/alexa`, exclusão de conta** (`devices.py`, rotas, `tests/relay/test_devices.py`, `tests/relay/test_alexa_endpoint.py`).
- **P4.5 Documentos** (`docs/legal/*`, `docs/runbooks/beta-fechado.md`, `docs/security/threat-model.md`): rascunhos para revisão do dono; roteiro do beta.

Cada tarefa: testes primeiro (ver FALHAR), implementação mínima, suíte verde, commit.
