# HeyCode: rotas protegidas, borda anti-abuso e painel refinado

Data: 2026-11-14. Status: Aprovada pelo dono em 2026-11-14 ("siga com sua recomendação [...] você que manda", depois de o agente apresentar o diagnóstico, a ordem rotas → borda → visual e a opção Cloudflare na frente; registrado pelo agente, que tomou as decisões de desenho abaixo por delegação).

Base: specs do relay MVP, da skill compartilhada e do painel web; ADRs 0035, 0037, 0040, 0046, 0054; `docs/security/threat-model.md`.

## 1. Intenção e porquê

O relay roda numa VM pequena (always free) e fica exposto à internet. O dono quer três coisas: que as rotas que já existem sejam **seguras de ponta a ponta**, que a VM **não caia com abuso** (limites, bloqueio de IP, anti-DDoS) e que o painel `/app` tenha **acabamento de produto**: grade consistente, campos bem organizados, textura e fluidez.

## 2. Objetivos, não objetivos e antiobjetivos

Objetivos:

- Toda rota tem teto de taxa, de tamanho e de memória; nenhuma estrutura em memória cresce sem limite.
- Um IP abusivo é barrado sozinho, por tempo limitado, sem ação do dono.
- Ataque volumétrico é absorvido antes da VM (Cloudflare); a VM só aceita tráfego web vindo da Cloudflare.
- O painel fica bonito e organizado sem perder a CSP rígida nem a regra "dado só entra por `textContent`".

Não objetivos: trocar login por IdP (D4 da revisão adversarial), mudar o protocolo máquina↔relay, mudar a skill, criar rotas de produto novas além de uma visão geral que só lê rotas existentes.

Antiobjetivos: um limite que tranque o dono fora da própria conta por muito tempo; um painel que exija build com Node na VM ou afrouxe a CSP; proteção que quebre a Alexa (os pedidos dela chegam de poucos IPs da Amazon).

## 3. Abordagens

Borda:

- **A. Cloudflare na frente + limites na VM (escolhida).** A Cloudflare absorve volume; o firewall da VM só abre 80/443 para as faixas dela; o Caddy reconhece o IP real e impõe tamanho e tempo; o app limita por IP e por conta. O domínio já usa os servidores de nome da Cloudflare, então basta ligar o proxy nos registros. Custo: manter a lista de faixas.
- B. Só na VM (Caddy com plugin de taxa + fail2ban). Não segura volume e exige compilar o Caddy na VM fraca. Rejeitada.
- C. Só Cloudflare, sem limites no app. Quem descobrir o IP de origem contorna tudo. Rejeitada.

Painel:

- **A. Sem build: HTML, CSS e módulo JS próprios (escolhida).** Mantém a CSP `'self'`, a lista fechada de arquivos e zero dependência; seis telas não justificam um framework.
- B. React/Vite com build. Mais ergonomia, mas põe Node na imagem e no CI e amplia a cadeia de suprimentos de um painel que controla máquinas. Rejeitada.
- C. Biblioteca vendorizada (Preact/htm) sem build. Ganho pequeno para o risco de manter código de terceiros copiado. Rejeitada.

## 4. Fase A: rotas (`src/heycode/relay/`)

1. **`RateLimiter` com memória limitada**: descarta chaves vazias, tem teto de chaves (ao estourar, expulsa as mais antigas) e informa o tempo de espera.
2. **Guarda global por IP** (middleware HTTP, exceto `/health`): 240 pedidos/min por IP. Excedeu: `429` com `Retry-After`. O IP vem de `request.client.host` (ADR 0040).
3. **Banimento temporário**: cada `429` da guarda ou falha de assinatura da Alexa conta um ponto; 20 pontos em 5 min bloqueiam o IP por 15 min (resposta `429` imediata, sem tocar banco nem Argon2). Estado em memória, com teto.
4. **Limites específicos por IP**: cadastro e login (API, painel, OAuth) 10/min, como já era; `pair/machine-confirm`, `pair/{id}` e `oauth/token` 30/min; `/v1/alexa` 600/min (IPs da Amazon são compartilhados); aperto de mão do WebSocket 20/min.
5. **Login por e-mail**: 20 tentativas/15 min por e-mail (hash), além do limite por IP. Risco aceito: um atacante pode atrasar o login do dono por até 15 min; a sessão já aberta não é afetada.
6. **Por conta**: emissão de código de pareamento 10/min.
7. **Tamanho**: `Content-Length` acima de 64 KiB (256 KiB em `/v1/alexa`) recebe `413`; campos Pydantic ganham `max_length` (e-mail 254, senha 256, código 16, chave pública 128, ids 256, texto de instrução 2000).
8. **WebSocket `/v1/connect`**: 10 s para o primeiro envelope; no máximo 64 conexões ainda não autenticadas; 240 mensagens/min por conexão (excedeu: fecha com 4429).
9. **Memória do pareamento**: `done` e `names` com teto; códigos e falhas expirados são varridos.
10. **Cabeçalhos em toda resposta**: `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`, `Permissions-Policy` vazia; CSP `default-src 'none'; frame-ancestors 'none'` nas respostas que não são do painel; o formulário OAuth ganha CSP própria e `no-store`.
11. **Sem documentação automática em produção**: `/docs`, `/redoc` e `/openapi.json` desligados.
12. **Argon2 com teto de paralelismo**: no máximo 2 cálculos de senha ao mesmo tempo (cada um usa ~64 MiB); os demais esperam a vez. Achado durante a implementação.

Critério de pronto: teste para cada item; a suíte do relay segue verde.

## 5. Fase B: borda (`infra/vps/`), com ADR novo

1. **Caddyfile**: `trusted_proxies` com as faixas da Cloudflare, `X-Forwarded-For` com o IP real do cliente, corpo máximo de 256 KiB, tempos de leitura de cabeçalho e ociosidade, cabeçalhos de segurança, HSTS com `includeSubDomains`.
2. **Uvicorn**: `--limit-concurrency`, `--timeout-keep-alive`, `--ws-max-size`.
3. **Compose**: teto de memória, CPU e processos nos dois contêineres; rotação de log.
4. **Firewall**: `infra/vps/cloudflare-firewall.sh` troca "80/443 para todos" por "80/443 só das faixas da Cloudflare" (lista em `cloudflare-ips.txt`, versionada). O SSH continua aberto por chave.
5. **Runbook** no `infra/vps/README.md`: DNS com proxy, TLS "Full (strict)", WebSocket ligado, uma regra de taxa na borda, modo "Under Attack" e como voltar atrás.

O dono executa os passos na Cloudflare e na VM; o agente não tem acesso a nenhum dos dois.

## 6. Fase C: painel (`src/heycode/relay/panel/`)

- **Estrutura**: barra lateral com ícones (SVG criado por DOM), cabeçalho de página com ações, grade de 12 colunas, cartões em grade responsiva, barra inferior no celular.
- **Visão geral** (tela nova, só leitura de rotas existentes): computadores conectados, dispositivos aguardando, comandos ligados e atividade recente.
- **Formulários**: campos alinhados em grade, rótulo, ajuda e erro por campo, contador de caracteres, interruptor no lugar de caixa de seleção.
- **Diálogos próprios** (`<dialog>`) no lugar de `window.prompt` e `window.confirm`.
- **Textura e fluidez**: fundo com malha de gradiente e grão sutil (CSS e `data:` SVG), superfícies com elevação, esqueletos de carregamento, transições curtas que respeitam `prefers-reduced-motion`.
- **Tabelas**: cabeçalho fixo, linhas com realce, selos de resultado.
- Mantidos: CSP atual, lista fechada de arquivos, textos e rótulos que os testes de navegador usam, temas claro/escuro e cor de destaque, alvo de toque ≥ 42 px, foco visível.

Critério de pronto: `tests/relay/test_panel_static.py` e `tests/ui/test_panel_browser.py` verdes, mais testes da visão geral e dos diálogos; conferência visual por captura de tela em 1280 px e 390 px, nos dois temas.

## 7. Restrições

- Cada commit ≤ 400 linhas adicionadas (G12); `feat`/`fix` com teste e trailer `Spec:`.
- Limites em memória e por processo (ADR 0035: instância única). Reiniciar o relay zera contadores e banimentos.
- Nada de fonte, script ou imagem de terceiros no painel.

## 8. Deixado para quem implementa

Nomes internos, valores exatos de espaçamento e cor, divisão dos commits e a forma dos ícones.
