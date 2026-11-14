# 0054. Hospedagem inicial em VM Always Free com Compose e Caddy

## Status

Aceito. Data: 2026-11-13. Ajusta o ADR 0035 (que sugeria Fly.io): a decisão de plataforma passou a ser do dono.

## Contexto

O ADR 0035 deixou a plataforma em aberto e sugeriu Fly.io. O dono decidiu usar uma VM **Always Free da Oracle Cloud** em São Paulo, para não pagar nada durante o beta. Um VPS não tem o deploy pronto de uma plataforma gerenciada, então HTTPS, firewall, atualizações e backup precisam ser definidos aqui. Spec: `docs/superpowers/specs/2026-11-13-heycode-relay-mvp.md` §6.

## Decisão

- Uma única VM (instância única, como no ADR 0035) com Ubuntu 24.04, **Docker Compose** com dois serviços: o relay (imagem do `infra/Dockerfile`) e o **Caddy** (HTTPS automático por Let's Encrypt). Só o Caddy publica portas (80 e 443); o relay fica na rede interna, porque a origem do cliente vem do `X-Forwarded-For` posto pelo Caddy (ADR 0040).
- Relay endurecido: sistema de arquivos somente leitura (só `/data` é gravável), sem capacidades extras, `no-new-privileges`, usuário sem privilégios (`nobody`) com a pasta `/data` dele no volume.
- Servidor: usuário `deploy` sem root e sem senha, SSH só por chave, `ufw` liberando 22, 80 e 443, atualizações automáticas de segurança.
- Backup diário do banco com a API de backup do SQLite (consistente com o relay no ar), rotação local de 14 dias e **cópia obrigatória para fora do servidor** (rclone). Um backup só local não conta.
- Rejeitado: confiar na Oracle como única cópia dos dados (contas gratuitas podem ser reclamadas por inatividade ou capacidade) e expor a porta do relay direto (permitiria forjar a origem e contornar limites).

## Consequências

Custo zero e controle total, com o dono assumindo a operação. Riscos aceitos: a Oracle pode retirar ou não ter capacidade para a VM gratuita, e a máquina é um ponto único de falha (o componente local reconecta sozinho e os agentes seguem em falha aberta). Migrar para outra hospedagem exige só reconstruir com o mesmo Compose e restaurar o backup (runbook de restauração).
