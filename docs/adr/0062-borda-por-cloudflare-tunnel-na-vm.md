# 0062. Borda por Cloudflare Tunnel na VM

## Status

Proposto. Data: 2026-11-14. Complementa o ADR 0058 (Cloudflare na frente) e o 0054 (VM com Compose); não os edita.

## Contexto

O relay roda numa VM Oracle Always Free. O proxy da Cloudflare já está ligado em `staging-api` e `staging-app`, e a origem já não responde por fora (conferido em 2026-11-14). Ainda assim a VM publica 80 e 443, depende de uma lista de faixas da Cloudflare duplicada em `cloudflare-ips.txt` e no `Caddyfile`, compila a imagem na própria máquina e usa `caddy:2` sem versão fixa. O dono já opera um túnel nomeado no próprio domínio para a ponte pessoal (ADR 0021). Spec: `docs/superpowers/specs/2026-11-14-heycode-ecossistema-de-extensoes.md` §4.

## Decisão

- O `cloudflared` roda como serviço do compose, com o token em `relay.env`, e expõe os nomes do relay por `ingress`. A VM não publica 80 nem 443.
- O certificado público é o da borda da Cloudflare. O Caddy sai ou fica só como proxy interno, fixado por digest.
- A imagem do relay é construída na CI, publicada no `ghcr.io` com atestado e implantada por digest; o deploy registra o digest.
- Backup com cópia externa e restauração testada passam a ser condição de operação.
- Rejeitado: manter portas abertas com filtro de faixas (lista duplicada e manutenção manual); runner de CI na VM (executaria código de terceiros na máquina das contas).

## Consequências

- Some a superfície de entrada da VM e a lista de faixas. A origem do cliente passa a vir do `cloudflared`; o relay continua confiando só no cabeçalho que a borda envia (ADR 0040).
- Dependência maior da conta Cloudflare (DNS, proxy e túnel). Mitigação: backup externo e cópia dos pacotes fora dela.
- A Alexa continua recebendo HTTPS com certificado confiável, servido pela borda.
