# Runbook: relay fora do ar

**Efeito para o usuário:** a skill diz que o computador está offline; os agentes seguem normais (falha aberta); o `heycode connect` reconecta sozinho com backoff de 1 a 60 s.

1. Confirme: `curl -fsS https://<relay>/health` (esperado `{"ok":true}`) e a página de status.
2. Plataforma: veja o estado da máquina e os logs recentes. Reinicie a máquina se estiver parada (a instância é única).
3. Volume: confirme que `/data/relay.db` está montado. Sem volume o relay recusa subir (`RELAY_DB` ausente) em vez de perder dados.
4. Se subiu mas rejeita conexões: veja o limite de taxa e as cotas; nenhuma delas deve bloquear `/v1/connect`.
5. Depois de voltar: confira que as instalações reconectaram (`last_seen` recente) e avise quem reportou.
6. Registre o incidente e vire a causa em teste, gate ou ADR (retrospectiva, SDLC etapa 12).
