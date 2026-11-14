# 0056. Backup por timer do systemd e nome fixo do projeto Compose

## Status

Aceito. Data: 2026-11-14. Complementa os ADRs 0054 e 0055.

## Contexto

A validação do pacote de VM na máquina real mostrou três coisas: a imagem mínima do Ubuntu não tem `cron`; o usuário `deploy` (sem `sudo`, de propósito) não grava em `/var/log`; e o nome do projeto do Compose vem do nome da pasta (`vps`), o que fazia o volume do banco se chamar `vps_relay_data` e não `heycode_relay_data`, como o `backup.sh` esperava. O backup também precisa rodar como o dono dos arquivos de backup, não como o `nobody` do contêiner.

## Decisão

- O agendamento é um **timer do systemd** (`heycode-backup.timer` e `.service`), instalado uma vez pelo administrador, rodando como `deploy`, com log no journal (`journalctl -u heycode-backup.service`) e `Persistent=true` (recupera execução perdida se a máquina estava desligada).
- O `docker-compose.yml` fixa `name: heycode`: volumes `heycode_relay_data` e `heycode_caddy_data`, independentes da pasta de instalação.
- O `backup.sh` roda o contêiner com `--user "$(id -u):$(id -g)"` e `-i` (lê o script do stdin), grava o arquivo com modo 600, valida o banco e **apaga o arquivo parcial em qualquer erro** (`trap ... ERR`).
- Rejeitado: instalar `cron` só para isso (mais um serviço e log fora do journal) e dar `sudo` ao `deploy` (amplia o alcance de um acesso comprometido).

## Consequências

Backup agendado sem dependências novas, com falha visível no journal. Custo: a instalação do timer exige o usuário administrador (uma vez), e o destino externo continua sendo configuração manual do dono (`BACKUP_REMOTE`).
