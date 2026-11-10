# Plano: ditado e criação de projeto em dois turnos

Spec: `docs/superpowers/specs/2026-11-10-dialogo-em-dois-turnos.md`. ADR: `docs/adr/0016-dialogo-em-dois-turnos.md`.

Arquivos: `skill/interaction-model-pt-BR.json`, `skill/lambda/index.js`, `skill/lambda/test/dialog.test.js`,
`skill/lambda/test/envfile.test.js`, `skill/lambda/test/nofetch.test.js`, `skill/lambda/test/w1d.test.js`,
`.gitignore`, `docs/DEPLOY-ALEXA.md`. A ponte não muda.

- [x] Modelo: `AskAgentIntent` com frases só de agente e projeto; `CreateProjectIntent` com frases só de nome e
  agente; seção `dialog` (`SKILL_RESPONSE`) com `instrucao` e `descricao` pedidos pela skill; `prompts`.
- [x] Testes novos (`dialog.test.js`): primeiro turno pede o slot com `Dialog.ElicitSlot` e guarda o contexto na
  sessão; segundo turno usa a sessão, limpa e chama a ponte; slot presente vence a sessão; sem agente não pede a
  frase; regras do modelo (nenhuma frase mistura slot de frase com outro slot; `dialog` e `prompts` coerentes).
- [x] Ajuste do teste antigo do modelo em `w1d.test.js`, que exigia `{projeto}`, `{agente}` e `{instrucao}` na
  mesma frase.
- [x] Lambda: `AskAgent` e `CreateProject` com `getSaved`/`setSaved` sobre `sessionAttributes` e
  `addElicitSlotDirective`.
- [x] Lambda: `loadEnvFile('./env.json')` para a skill hospedada; `skill/lambda/env.json` no `.gitignore`; testes
  em `envfile.test.js`.
- [x] Lambda: `httpFetch` com `http`/`https` nativos quando não há `fetch` global (Node 16 da Alexa-hosted);
  testes em `nofetch.test.js` contra um servidor HTTP local.
- [x] `npm test` em `skill/lambda`: 67 passaram.
- [x] Build do modelo no Alexa Developer Console: sem erros, 2 avisos (slot pedido sem frase de exemplo própria).
- [x] Deploy do código na aba Code, com `env.json` criado só no editor hospedado.
- [x] Simulador: status e pendências reais pela ponte; ditado em dois turnos até "Ditado cancelado.".
- [x] `docs/DEPLOY-ALEXA.md`: `env.json`, Node 16, frases em dois turnos.
- [ ] Trocar `ALLOWED_DEVICE_ID` do simulador pelo do aparelho do dono (depende de o dono falar com o Echo).
- [x] Commit: `fix: ditado e projeto por voz em dois turnos para o modelo compilar na Alexa`.
