# 0046. Painel web servido pelo relay, com sessão em cookie e proteção CSRF

## Status

Aceito. Data: 2026-11-13.

## Contexto

O gerenciamento (pareamento, dispositivos, rastro, atalhos) precisa de interface. A API atual autentica por `Authorization: Bearer`, que numa página web obrigaria guardar o token em `localStorage`, exposto a XSS. Spec: `docs/superpowers/specs/2026-11-13-heycode-painel-web-rastro-e-comandos.md` §3.

## Decisão

- O relay serve o painel em `/app` com HTML, CSS e JavaScript sem build e sem dependências externas.
- Login do painel cria sessão em cookie `HttpOnly; Secure; SameSite=Strict`. Métodos que alteram estado exigem o cabeçalho `X-CSRF-Token` igual ao token de duplo envio da sessão. O `Authorization: Bearer` segue aceito para o `heycode` e a Alexa (sem cookie, sem CSRF).
- Política de segurança de conteúdo rígida (`default-src 'self'`, sem inline, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. Dados entram na página por `textContent`.
- Rejeitado: React/Vite separado (outro deploy, CORS, mais superfície) e token em `localStorage` (roubável por XSS).

## Consequências

Uma peça para publicar e menos superfície. Custo: telas mais simples e a obrigação de manter a política de conteúdo (todo script em arquivo próprio).
