# HeyCode: painel web, rastro da voz e comandos personalizados

Data: 2026-11-13. Status: Aprovada pelo dono em 2026-11-13 ("faz o que achar ideal", depois de a proposta de escopo e de ordem A→B→C ter sido apresentada; registrado pelo agente a pedido expresso).

Base: specs do relay, da skill compartilhada e das intents no modo compartilhado; ADRs 0029 a 0045; `docs/security/threat-model.md`. Inspiração de produto: miblo.ai (site de conta e comunidade, página de ajustes do dispositivo atrás de código, personalização leve, modo reunião).

## 1. Intenção e porquê

O site existe para **gerenciar**: a pessoa precisa ver **o rastro do que a voz aprovou e fez** e **cadastrar comandos novos** que a Alexa executa pelo middleware, sem tocar código. Hoje tudo isso é API crua. Meta: **qualquer pessoa abre o painel, entende em segundos o que a Alexa fez no computador dela, desliga o que não quer e cria um atalho novo sem abrir um editor.**

## 2. Escopo e ordem

1. **Painel web** servido pelo próprio relay: conta, pareamento, computadores, dispositivos Alexa, computador padrão, excluir conta.
2. **Rastro** (auditoria): linha do tempo de tudo que a voz fez; detalhe sob demanda, vindo do computador.
3. **Comandos personalizados, fase A (atalhos para agentes):** modelos de frase ("rode os testes do projeto X no codex") que a Alexa dispara por uma intent genérica, passando pelo ditado com confirmação por voz que já existe.
4. **Fase B (scripts locais) e C (webhooks): fora desta entrega**, apenas especificadas em §6 para não serem improvisadas depois.

Fora também: estúdio de mascotes, galeria, fórum, lembretes, brilho/filtro azul (são do aparelho do Miblo), tradução da interface, app nativo.

## 3. Painel web

- **Servido pelo relay** em `/app` (HTML, CSS e JavaScript sem etapa de build e sem dependências externas), chamando a API JSON que já existe. Uma única peça para publicar.
- **Sessão em cookie** `HttpOnly`, `Secure`, `SameSite=Strict`, com **token anti-CSRF** em todo método que altera estado. O token de cabeçalho `Authorization: Bearer` continua valendo para o `heycode` e para a Alexa; o painel nunca guarda token em `localStorage`.
- **Política de segurança de conteúdo rígida** (sem script inline, sem origem externa, `frame-ancestors 'none'`), mais `X-Content-Type-Options` e `Referrer-Policy`.
- Todo texto vindo de dados (nomes, comandos) entra na página por `textContent`, nunca como HTML.
- **Telas:** entrar/criar conta; pareamento (conferir o código de verificação e confirmar); meus computadores (apelido, remover); dispositivos Alexa (pendentes com aprovar/negar, aprovados com revogar); computador padrão; rastro; comandos; conta (excluir, com senha).
- **Visual:** claro, escuro ou automático; cor de destaque; estado vazio explica o próximo passo. Sem emoji e sem imagens externas.

## 4. Rastro

- O relay grava **metadados** de cada interação autêntica da Alexa e de cada decisão no painel: quando, dispositivo, computador, tipo (intent ou ação do painel), resultado (`ok`, `negado`, `barrado`, `offline`, `erro`) e, para comandos, o nome do atalho. **Nenhum texto de pedido, PIN ou saída de agente.** Retenção de 30 dias (já prometida na política de privacidade), com limpeza automática.
- `GET /v1/audit` (autenticado, só da própria conta, paginado, com filtros por computador, dispositivo e resultado).
- **Detalhe sob demanda:** o painel pede o detalhe ao computador por `bridge-call` a uma rota nova e somente de leitura da ponte local, `GET /voice/audit?limit=`, na lista fechada do executor. Ela devolve as aprovações e execuções recentes **com segredos mascarados**. O relay repassa e esquece.

## 5. Comandos personalizados, fase A (atalhos)

- Um atalho tem: nome falado, apelidos, agente (`claude`, `codex`, `aider`), projeto opcional, modelo de instrução (texto fixo, sem variáveis nesta fase) e uma descrição. Limite de 30 por conta; nome com 2 a 40 caracteres.
- **Como a Alexa chega nele:** uma intent nova, `RunCommandIntent` ("executar {comando}", "rode {comando}", "faça {comando}"), com o slot `comando` livre. O relay normaliza a fala (sem acento, minúsculas), casa com nome e apelidos (exato primeiro, depois semelhança acima de um limiar, e **recusa se houver empate**) e devolve "Não achei esse comando" quando não acha. Casou: monta o mesmo `POST /dictation` do pedido por voz e fala o resultado com "Confirma?". **A execução só acontece depois da confirmação por voz, como hoje.** Atalho nunca roda sozinho.
- **Por que isso não amplia o poder do relay:** ele já pode pedir um ditado a qualquer momento (que exige confirmação por voz). O atalho só guarda o texto. Por isso a fase A **não** precisa de ativação no computador.
- Mudança no modelo de interação: acrescentar `RunCommandIntent` a `skill/interaction-model-pt-BR.json` (aditivo) e um ADR.
- O painel lista, cria, edita, liga/desliga e apaga atalhos, e mostra "dizer: executar <nome>".

## 6. Fases futuras (só desenho, para guiar)

- **B, scripts locais:** a definição do que roda **vive no computador** (`commands.json` na pasta do HeyCode), nunca no relay. O painel só mostra e liga/desliga o que o computador anuncia. Cada script tem nível de risco: `leitura` (roda após a frase), `confirmar` (confirmação por voz) e `pin` (confirmação com PIN). Criar ou alterar script exige `heycode command add` no computador. Executa sem shell, com lista de argumentos fixa, diretório e tempo máximo definidos.
- **C, webhooks:** só destinos fixos cadastrados no computador, nunca URL vinda da voz ou do relay.

## 7. Critérios de aceite

1. Painel: fluxo completo conta → pareamento → aprovar dispositivo → computador padrão → excluir conta, em um navegador de verdade (teste automatizado com Playwright), sem erro de console.
2. Segurança do painel: cookie com as três flags; método de escrita sem token anti-CSRF recusado; cabeçalhos de segurança presentes; nenhuma página carrega recurso externo; injeção de HTML por apelido de computador ou nome de atalho aparece como texto.
3. Rastro: cada tipo de interação gera uma linha com os campos certos e **sem conteúdo**; a conta B nunca vê a linha da conta A; a limpeza de 30 dias funciona; o detalhe vem do computador com segredos mascarados.
4. Atalhos: casamento exato, por apelido e por semelhança; empate e ausência recusados; a execução passa pelo "Confirma?"; limite por conta; isolamento entre contas.
5. A suíte anterior continua verde; o Lambda do dono e o caminho do dono ficam intactos.

## 8. Decisões minhas (o dono delegou)

1. HTML, CSS e JavaScript simples servidos pelo relay (sem React, sem build). Motivo: uma peça só, menor superfície de ataque.
2. Rastro só com metadados no relay e detalhe no computador. Motivo: preserva a promessa de privacidade e mantém o histórico onde está o código.
3. Atalhos primeiro, scripts depois. Motivo: atalhos não ampliam o poder do relay.

## 9. Riscos

- Tela de pareamento e de aprovação são alvos de phishing: o painel só opera em domínio próprio com HTTPS e mostra o código de verificação em destaque.
- Casamento por semelhança pode errar: a confirmação por voz continua sendo a barreira.
- O arquivo `skill/interaction-model-pt-BR.json` tem alteração local não commitada do dono em `main`; a mudança aditiva desta entrega pode conflitar no merge.
