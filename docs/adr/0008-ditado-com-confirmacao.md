# 0008. Ditado de instruções por voz com confirmação

## Status

Aceito. Data: 2026-11-09.

## Contexto

A fase 4 deixa o dono mandar uma tarefa a um agente (Claude, Codex ou Aider) pela Alexa. O reconhecimento de voz erra, o texto ditado pode conter segredos e uma instrução enviada sem conferência executa trabalho real no computador. Spec: `docs/superpowers/specs/2026-11-09-alexa-agent-hub-design.md` (G6, §10).

## Decisão

- Toda instrução passa por confirmação: `AskAgentIntent` chama `POST /dictation`, a ponte guarda o ditado pendente e a Alexa relê o que entendeu, terminando em "Confirma?" com a sessão aberta. `ConfirmIntent` chama `POST /dictation/confirm` e só então `start_run` é chamado; `CancelDictationIntent` descarta o pendente.
- Existe um único ditado pendente: um novo `propose` substitui o anterior. Confirmar sem pendente, ou depois de 60 s, não inicia nada e a fala diz isso. A confirmação consome o pendente, então repetir "confirma" não reenvia.
- Limite de 300 caracteres e texto não vazio; agente fora de claude, codex e aider é recusado.
- Segredos (`sk-...`, `ghp_...`, `AKIA...`, `password=...`) são mascarados como `[segredo]` na fala, nas respostas HTTP e nas mensagens de erro. O agente recebe o texto original, pois o dono pode precisar passar a credencial. A máscara local `_mask` será trocada por `policy.redact.mask_secrets` na ligação ao servidor.
- O intent `AGENTE` usa tipo customizado com ids `claude`, `codex`, `aider`; a Lambda resolve pelo id da resolução de entidade e, na falta dela, pelo texto normalizado.
- Falha de `start_run` vira fala de erro, sem derrubar a ponte.
- Alternativas rejeitadas: enviar direto sem releitura (erros de reconhecimento viram execução); fila de vários ditados pendentes (confusão sobre qual está sendo confirmado); mascarar também o texto enviado ao agente (quebraria instruções legítimas com credenciais).

## Consequências

- O dono ouve sempre o que será executado antes de executar, ao custo de um turno a mais.
- Segredos falados não vazam em voz nem em log, mas o texto original fica em memória até confirmar, expirar ou cancelar, e segue ao agente.
- O estado pendente vive em memória: reiniciar a ponte descarta o ditado, o que é seguro.
- A máscara por regex pode deixar passar formatos de segredo desconhecidos; a lista é mantida em `policy.redact`.
