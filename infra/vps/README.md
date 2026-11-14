# Relay em uma VM (Oracle Always Free ou qualquer Ubuntu 24.04)

Decisão e riscos: ADR 0054. Estado: **validado numa VM real** (Oracle Always Free, Ubuntu 24.04, 1 GB): preparo do servidor, construção da imagem, relay saudável com sistema de arquivos somente leitura e uso de ~43 MB de memória, e backup agendado com arquivo verificado. Ainda **não validado**: o HTTPS do Caddy (depende do DNS) e a restauração a partir do backup.

## 1. Preparar o servidor (uma vez)

1. Crie a VM (Ubuntu 24.04) com **sua chave SSH pública** e IP público. Na rede da Oracle, a lista de segurança da sub-rede precisa permitir entrada nas portas **22, 80 e 443** (TCP).
2. Entre como o usuário padrão da imagem (`ubuntu`) e rode o script de preparação como root:
   ```bash
   scp -i CHAVE_PRIVADA infra/vps/setup-server.sh ubuntu@IP:/tmp/
   scp -i CHAVE_PRIVADA CHAVE_PUBLICA.pub ubuntu@IP:/tmp/deploy_authorized_keys
   ssh -i CHAVE_PRIVADA ubuntu@IP 'sudo install -m 600 /tmp/deploy_authorized_keys /root/deploy_authorized_keys && sudo bash /tmp/setup-server.sh'
   ```
3. Daqui em diante use o usuário `deploy` (sem root): `ssh -i CHAVE_PRIVADA deploy@IP`.

## 2. DNS

Aponte `staging-api.` e `staging-app.` (mesmo IP público da VM, registro `A`) **antes** de subir o Caddy: ele só emite o certificado se o nome já resolver para este servidor. No Cloudflare, deixe os dois como "somente DNS" (nuvem cinza) para o Caddy validar o certificado.

## 3. Subir

```bash
cd /opt/heycode && git clone <seu-repositorio> . && cd infra/vps
cp relay.env.example relay.env && chmod 600 relay.env   # preencha os segredos (openssl rand -hex 32)
$EDITOR Caddyfile                                        # troque os dois dominios
docker compose --env-file relay.env up -d --build
docker compose ps && curl -fsS https://staging-api.heycode.dev.br/health
```

## 4. Backup (obrigatório, com cópia externa)

A imagem mínima do Ubuntu não tem `cron`: o backup diário (03:17) roda por um **timer do systemd**, instalado como administrador (usuário `ubuntu`, que tem `sudo`; o `deploy` não tem):

```bash
sudo install -m 644 /opt/heycode/infra/vps/heycode-backup.service /opt/heycode/infra/vps/heycode-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now heycode-backup.timer
sudo systemctl start heycode-backup.service && journalctl -u heycode-backup.service -n 5 --no-pager   # teste agora
```

Cada execução grava `relay-AAAAMMDDTHHMMSSZ.db.gz` (modo 600) em `/var/backups/heycode`, valida que o arquivo abre e tem as tabelas e guarda os 14 mais recentes. **O backup só local não conta.** Para copiar para fora, instale e configure o `rclone` (por exemplo Backblaze B2 ou um bucket privado) e crie `/opt/heycode/infra/vps/backup.env` (modo 600) com `BACKUP_REMOTE=meu-remote:heycode`. Teste a restauração (`docs/runbooks/restauracao-do-banco.md`) antes de confiar.

## 5. Operação

- Atualizar: `git pull && docker compose --env-file relay.env up -d --build`.
- Logs: `docker compose logs -f relay`; reinício: `docker compose restart relay`.
- **Nunca** publique a porta 8080 do relay (ADR 0040).
- Se a Oracle avisar de reclamação por inatividade, a VM precisa de uso: o relay conectado já conta, mas confirme na política atual.
