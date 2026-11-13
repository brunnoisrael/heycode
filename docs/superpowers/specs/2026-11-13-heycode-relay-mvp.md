# HeyCode relay MVP: contas, pareamento, roteamento e operação

Data: 2026-11-13. Status: Rascunho (aguarda aprovação do dono; sem aprovação, nenhuma tarefa de código da P3 começa).

Visão: `docs/ROADMAP-HEYCODE.md`. Programa: `docs/superpowers/plans/2026-11-13-heycode-publicavel-e-esteira-de-agentes.md` (trilha P3). Contratos: `docs/superpowers/specs/2026-11-13-heycode-contratos-e-seguranca-multiusuario.md` e ADRs 0029 a 0034. Modelo de ameaça: `docs/security/threat-model.md`.

## 1. Intenção e porquê

Qualquer pessoa precisa usar o HeyCode sem túnel próprio, domínio nem Lambda. O relay é o serviço em nuvem que une a skill Alexa e a máquina de cada usuário: a máquina abre uma conexão de saída, a skill fala com o relay, e o relay entrega o pedido **só** à instalação da conta certa. Meta: **uma tarefa de teste vai da skill ao agente local e volta, sem túnel individual, e a conta A jamais alcança a máquina de B.**

## 2. Escopo

Dentro: serviço `relay/` (FastAPI) com cadastro e login, pareamento, WebSocket de saída da máquina, roteamento por conta e instalação, endpoint HTTPS da skill, limite de taxa, cotas, logs sem segredo; `heycode pair` e conexão persistente com reconexão no componente local; infraestrutura mínima de staging como código; documentos de operação.

Fora: OAuth2 completo de account linking e certificação da skill (P4); funcionalidades M0–M3 (P5); produção pública (P6). O caminho do dono (Lambda, `ponte.heycode.dev.br`) não é alterado.

## 3. Arquitetura

- **Relay:** processo Python (FastAPI, mesmo stack da ponte), um único contêiner sem estado local. Estado em Postgres; testes e desenvolvimento usam SQLite atrás da mesma interface de repositório.
- **Entidades:** `account`, `installation` (id, conta, chave pública, nome, `last_seen`), `device_association`, `pairing_code`, `revocation`, `request_log` (sem conteúdo sensível).
- **Conexão da máquina:** WebSocket de saída, autenticado por envelope assinado (ADR 0030). O relay valida assinatura, anti-replay e revogação em toda mensagem. Reconexão com backoff exponencial (1 s a 60 s com jitter) no componente local; falha aberta para os agentes.
- **Pedido da skill:** HTTPS em `api.` (ADR 0033). A skill se identifica pela conta vinculada; o relay resolve a instalação (a única, ou a escolhida quando houver mais de uma), entrega o envelope e aguarda resposta curta. Se a máquina não responder no limite, a skill diz que a máquina está offline ou que o pedido continua em segundo plano; nenhuma confirmação fica pendente para sempre (ADR 0031, expiração de 5 min).
- **Latência:** a Alexa dá poucos segundos. Resposta síncrona até 4 s; acima disso, resposta parcial ("estou verificando") e continuação assíncrona pela fila de resultados.
- **Isolamento:** toda consulta filtra por conta no repositório (teste de isolamento por construção); nenhum endpoint aceita `account_id` ou `installation_id` do corpo como autoridade.

## 4. Contas e pareamento

- Cadastro por e-mail com link de verificação e login com senha (hash Argon2id) ou provedor externo (decisão aberta §8). Sessão por token de curta duração.
- Pareamento conforme spec P2 §4: o relay emite o código (8 caracteres, uso único, 5 min), a máquina o resgata com `heycode pair`, e a conta confirma no app web. O código de verificação de 6 dígitos aparece nos dois lados.
- Revogação pelo app web; a máquina descobre na próxima conexão e para.

## 5. Cotas e custo

- **Gratuito:** 1 conta, até 2 instalações, 200 pedidos por dia por conta, retenção do `request_log` de 30 dias.
- **Teto de custo:** alerta e limite de orçamento mensal na plataforma; limite de taxa global e por conta; WebSocket por instalação com máximo de 1 conexão ativa.
- A política paga é decidida por ADR antes de existir cobrança; o MVP não cobra.

## 6. Operação

- Domínios: `staging-api.heycode.dev.br` e `staging-app.heycode.dev.br` primeiro; `ponte.` do dono intacto. E-mail `privacy@`, `support@`, `security@` com SPF, DKIM e DMARC.
- Hospedagem, Postgres gerenciado com backup e restauração testada, TLS automático, segredos no gerenciador da plataforma, tudo como código em `infra/` sem segredos; um segundo administrador em registrador, nuvem e GitHub (P6).
- Observabilidade: logs estruturados sem segredo, métricas (conexões, latência, erros, pedidos por conta), alertas de queda e de custo, página de status.
- `docs/OPERATIONS.md` e runbooks em `docs/runbooks/` (relay fora do ar, chave vazada, domínio quase expirando, restauração do banco).

## 7. Critérios de aceite

1. Cadastro, login e pareamento ponta a ponta em staging, com os casos de falha da P2 (código expirado, reusado, adivinhado).
2. Uma tarefa de teste vai de uma chamada HTTPS ao relay até o agente local e volta, sem túnel individual.
3. Testes de isolamento: usuário A nunca recebe, aciona ou lê dados de B, inclusive com corridas e IDs reaproveitados.
4. Relay cai: o componente local reconecta sozinho e os agentes seguem normais.
5. Segredo nunca aparece no relay nem nos logs (teste com segredos de formato conhecido).
6. Outra pessoa reconstrói o staging só com o repositório e os runbooks.
7. O caminho do dono segue passando em toda a suíte existente.

## 8. Decisões propostas (o dono confirma)

1. **Hospedagem:** contêiner em plataforma gerenciada com WebSocket e Postgres gerenciado (sugestão: Fly.io; alternativa: Railway ou VPS). Critérios: custo previsível, região próxima ao Brasil/EUA-Leste para a Alexa, deploy reproduzível. Escolha e conta são do dono (envolve cobrança).
2. **Login:** e-mail e senha com Argon2id no MVP; provedor externo (Google/Amazon) depois. Sugestão: começar só com e-mail e senha para não depender de terceiros.
3. **Cotas gratuitas** do §5.
4. **Latência:** limite síncrono de 4 s do §3.

## 9. Ordem de execução e o que o agente não faz sozinho

Primeiro o que é só código e teste, em `relay/` e `heycode.cli`: repositório e modelos, contas, pareamento, roteamento, WebSocket, cliente com reconexão, isolamento. Só depois a infraestrutura. **Ações que dependem do dono** (cobrança e identidade): criar a conta na plataforma, registrar os DNS, ativar e-mail do domínio, liberar orçamento. O agente deixa o IaC e os runbooks prontos, mas não contrata, não publica e não toca DNS sem pedido explícito.

## 10. Riscos

- Dependências novas (FastAPI já existe; `argon2-cffi`, driver Postgres) passam por G8.
- Mudança de arquitetura: ADRs de hospedagem, banco, login e cotas, e atualização do `threat-model.md` (G10).
- A skill compartilhada só existe na P4; até lá o endpoint da skill é testado por cliente simulado.
