# 0052. Webhooks de destino fixo com segredos por referência

## Status

Aceito. Data: 2026-11-13.

## Contexto

Webhooks (casa, CI, automações) tiram uma chamada de dentro da máquina. A URL e o corpo não podem vir da voz nem do relay, e tokens de cabeçalho não podem aparecer em lugar nenhum. Spec: `docs/superpowers/specs/2026-11-13-heycode-comandos-locais-scripts-e-webhooks.md` §3.

## Decisão

- URL, método e corpo são fixos no `commands.json`. URL só `https` (ou `http` para `localhost`/`127.0.0.1`); sem seguir redirecionamentos; tempo máximo de 1 a 30 s.
- Cabeçalhos com segredo usam referência `env:NOME`, resolvida do `config.env` local no momento da chamada. O valor nunca entra em resposta, log, rastro nem saída falada. Referência a variável ausente é erro de validação.
- Webhook `POST` nunca tem risco `leitura`; só `GET` pode. A resposta falada traz o código HTTP e no máximo 200 caracteres do corpo, mascarados.
- Rejeitado: URL com variáveis preenchidas pela fala (SSRF e vazamento) e seguir redirecionamentos (desvio de destino).

## Consequências

Automação útil sem abrir um proxy genérico. Custo: um webhook por destino e ação, cadastrado no terminal.
