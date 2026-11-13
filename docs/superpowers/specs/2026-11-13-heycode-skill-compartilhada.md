# HeyCode skill compartilhada: account linking, requisições verificadas e dispositivos

Data: 2026-11-13. Status: Aprovada pelo dono em 2026-11-13 ("pode escrever e executar", em resposta à proposta de escrever a spec da P4 e executá-la; registrado pelo agente a pedido expresso). A aprovação cobre código, testes e rascunhos de documentos; publicar a skill, criar a conta de desenvolvedor Amazon, validar o nome de invocação e revisão jurídica final dos documentos são do dono.

Visão: `docs/ROADMAP-HEYCODE.md`. Programa: `docs/superpowers/plans/2026-11-13-heycode-publicavel-e-esteira-de-agentes.md` (trilha P4). Base: spec do relay (`2026-11-13-heycode-relay-mvp.md`), contratos da P2, ADR 0033 (endpoint HTTPS próprio).

## 1. Intenção e porquê

Uma única skill publicada deve atender várias pessoas sem que cada uma crie skill, Lambda ou informe IDs da Amazon. Para isso o relay precisa (a) **vincular** a conta Alexa à conta HeyCode (OAuth2), (b) **provar** que cada requisição veio mesmo da Amazon, (c) **autorizar dispositivos** por pessoa e instalação e (d) **escolher a máquina** quando houver mais de uma. Meta: **só uma requisição autêntica da Alexa, de uma conta vinculada e de um dispositivo que a pessoa autorizou, chega a uma máquina que é dela.**

## 2. Escopo

Dentro (código e testes): servidor OAuth2 (authorization code + refresh) no relay; verificação de assinatura e de validade das requisições da Alexa; endpoint `POST /v1/alexa`; associação, listagem e revogação de dispositivos; instalação padrão por conta; exclusão da conta e dos dados (LGPD); rascunhos de privacidade, termos e retenção; roteiro do beta fechado.

Fora (trilha seguinte, spec própria): porte das intents do Lambda atual (status, aprovar, ditado, projeto novo) para o endpoint compartilhado, que exige novo tipo de mensagem no protocolo; publicação e certificação da skill; adaptador Postgres; recuperação de senha. O endpoint `/v1/alexa` responde hoje a abertura, ajuda, parar/cancelar e informa com clareza que as demais intents ainda não estão disponíveis no modo compartilhado. O caminho do dono (Lambda + allowlist) segue intocado.

## 3. Account linking (OAuth2)

- Fluxo authorization code, como a Amazon exige: `GET /oauth/authorize` (formulário de login do HeyCode), `POST /oauth/authorize` (valida credenciais, emite código de uso único e redireciona com `state`), `POST /oauth/token` (`authorization_code` e `refresh_token`).
- Cliente da Alexa pré-registrado por variável de ambiente (`client_id`, segredo, lista fechada de `redirect_uri` exatos); qualquer outra `redirect_uri` é recusada, sem redirecionar.
- Código: 10 min, uso único, atado a (cliente, redirect_uri, conta). Access token: 1 h. Refresh token: 30 dias, **rotativo** (cada uso emite um novo e invalida o anterior; reuso de um refresh já usado revoga a família inteira).
- Tokens guardados só como hash. Segredo do cliente comparado em tempo constante.
- PKCE aceito quando enviado (S256). Revogar o vínculo apaga tokens e dispositivos daquela conta.

## 4. Verificação de requisições da Alexa

Conforme a documentação da Amazon: cabeçalhos `SignatureCertChainUrl` e `Signature` (SHA-256 com RSA); URL do certificado `https`, host `s3.amazonaws.com`, caminho começando por `/echo.api/`, porta 443 ou ausente; certificado válido na data, com `echo-api.amazon.com` nos nomes alternativos, cadeia validada contra raízes confiáveis; assinatura conferida sobre o corpo exato; `timestamp` da requisição a no máximo 150 s do relógio do relay; `applicationId` igual ao da skill (`ALEXA_SKILL_ID`). Qualquer falha devolve 400 sem executar nada. Certificado baixado é dado não confiável: só é analisado, nunca executado; cache por URL com validade.

## 5. Dispositivos e escolha da máquina

- Associação por (conta, instalação, dispositivo). Dispositivo desconhecido numa requisição **não executa nada**: a skill diz que o dispositivo precisa ser autorizado no app, e o relay registra uma solicitação pendente que a pessoa aprova (`POST /v1/devices/approve`) ou nega. Nenhuma allowlist global.
- Revogação a qualquer momento (`DELETE /v1/devices/{id}`); dispositivo revogado volta a ser desconhecido.
- Com uma instalação, ela é a escolhida; com mais de uma, a pessoa define a padrão no app (`PUT /v1/default-installation`); sem padrão a skill pede para escolher no app (nunca adivinha).
- O modo `auto` segue o ADR 0031: a ativação por voz só vale para dispositivo associado e depois da primeira confirmação no computador.

## 6. Privacidade e LGPD

- Dados que o relay guarda: e-mail, hash de senha, chaves públicas e nomes das instalações, associações de dispositivo, contadores de uso diário, tokens (hash). **Não** guarda conteúdo de pedidos nem saídas dos agentes além de resultados transitórios em memória.
- `DELETE /v1/account` (autenticado, com confirmação da senha) apaga conta, sessões, tokens, instalações, dispositivos e uso. Retenção do uso diário: 30 dias.
- `docs/legal/` traz rascunhos de política de privacidade, termos de uso e política de retenção **para revisão jurídica do dono**; nada é publicado por mim.

## 7. Critérios de aceite

1. Fluxo OAuth completo com cliente simulado: autorizar, trocar código, usar o token na skill, renovar com rotação; `redirect_uri` fora da lista, código reaproveitado ou expirado, segredo errado e refresh reutilizado são recusados (reuso revoga a família).
2. Requisição da Alexa com assinatura, certificado, timestamp ou `applicationId` inválidos é recusada; uma assinada por certificado de teste válido passa.
3. Dispositivo não associado não executa nada e gera solicitação pendente; só a conta dona aprova; revogado volta a ser recusado.
4. Várias instalações sem padrão: a skill pede a escolha; nunca roteia para a de outra conta.
5. Exclusão da conta apaga tudo e invalida tokens e conexões.
6. Todos os testes anteriores seguem verdes (caminho do dono intacto).

## 8. Decisões (delegadas pelo dono, pela experiência do usuário)

1. Refresh rotativo de 30 dias, para a pessoa não precisar revincular a cada mês e ainda limitar vazamento.
2. Escolha da máquina por instalação padrão definida no app, com a skill pedindo quando faltar, em vez de interrogar por voz a cada pedido.
3. Dispositivo novo exige aprovação no app (um passo único por dispositivo) antes de executar qualquer coisa.

## 9. Riscos

- Validação da cadeia do certificado depende de raízes confiáveis do sistema; em teste usa-se uma raiz injetada.
- `ALEXA_SKILL_ID`, segredo do cliente OAuth e URLs de redirecionamento só existem depois que o dono cria a skill no console da Amazon; o código lê tudo de variáveis de ambiente.
- Mudança de arquitetura: ADRs 0041 a 0043 e atualização do `threat-model.md` (G10).
