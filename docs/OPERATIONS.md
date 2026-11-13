# Operação do HeyCode

Comece sempre por `heycode doctor`: ele aponta a camada com problema e o que fazer.

## Reiniciar

| Situação | Como |
|---|---|
| Rodando em primeiro plano | Ctrl+C e `heycode serve` de novo |
| Serviço instalado | Windows: `schtasks /End /TN HeyCodeBridge` e `schtasks /Run /TN HeyCodeBridge`; macOS: `launchctl kickstart -k gui/$(id -u)/dev.heycode.bridge`; Linux: `systemctl --user restart heycode.service` |
| Depois de reiniciar o computador | O serviço volta no logon do usuário; confirme com `heycode doctor` |

Ao reiniciar, aprovações pendentes expiram e execuções em andamento viram "interrompidas" (ADR 0015).

## Rotacionar segredos

```bash
heycode rotate-secret                   # dry-run: mostra o que faria
heycode rotate-secret --apply           # segredo de agente (hooks e MCP)
heycode rotate-secret --control --apply # segredo de controle (Lambda)
```

Cria backup do `config.env` (permissão restrita; apague quando não precisar mais), reinicia o serviço se estiver instalado e diz o que atualizar: `BRIDGE_SECRET` nos hooks e no MCP dos agentes (reinicie-os) ou `BRIDGE_CONTROL_SECRET` na Lambda (com Deploy). Rode as duas variantes, uma de cada vez, para trocar ambos.

## Recuperar de falhas

| `doctor` mostra | Causa provável | O que fazer |
|---|---|---|
| ponte: falha | Serviço parado ou fora do ar | `heycode serve` ou `heycode install-service --apply` |
| ponte: "outro serviço" | Outra coisa usa a porta 8765 | `heycode serve --port <outra>` e ajuste `BRIDGE_URL` |
| autenticação: falha | Ponte iniciada com segredos antigos | Reinicie a ponte; confira `config.env` |
| configuração: segredos | `config.env` ausente ou segredos curtos/iguais | `heycode init` (não sobrescreve) ou `rotate-secret` |
| hook do Claude: falha | Hook antigo (`python .../hook.py`) | Troque o comando por `heycode hook` (veja o exemplo em `docs/`) |
| url pública: falha | Túnel ou DNS fora do ar | Confira o túnel; `scripts\diagnose-connection.ps1` no Windows |

## Onde ficam os dados

`config.env` (segredos) e `heycode.db` (estado) ficam no diretório do usuário; `heycode init` mostra o caminho. **Faça backup do diretório inteiro** e trate `config.env` como senha: nunca o envie a ninguém nem o commite. `heycode init --import-legacy` traz o estado de um clone antigo sem apagar a origem.

## Segurança em uma linha

O modo `auto` aprova tudo, sem PIN e sem expiração (ADR 0002). A mitigação é a allowlist de usuário e dispositivo do dono na Lambda; não a enfraqueça.

## Relay (multiusuário, opcional)

Para quem usa o relay em vez de túnel próprio: `heycode pair CÓDIGO --relay https://...` pareia este computador (confira o código de verificação nos dois lados) e `heycode connect` mantém a conexão de saída, reconectando sozinho. Se o relay cair, os agentes seguem normais. Operação do serviço, incidentes e restauração: `infra/README.md` e `docs/runbooks/`. O caminho do dono (Lambda e `ponte.`) não muda.

### Modo automático por voz no modo compartilhado

Por padrão a skill compartilhada **não** consegue ligar o modo `auto`. Para permitir, no próprio computador: `heycode relay-auto on` (pede confirmação; `--yes` pula) e `heycode relay-auto off` para bloquear de novo. A mudança vale na hora, sem reiniciar o `heycode connect`. O modo `auto` aprova tudo sem PIN e sem expiração (ADR 0002).
