# Relay em uma VM (Oracle Always Free ou qualquer Ubuntu 24.04)

Decisão e riscos: ADR 0054. Estado: pacote **pronto para uso, ainda não validado numa VM real** até a primeira instalação; o roteiro abaixo é o que será conferido nela.

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

```bash
crontab -e   # 17 3 * * * BACKUP_REMOTE=meu-remote:heycode /opt/heycode/infra/vps/backup.sh >>/var/log/heycode-backup.log 2>&1
```

Configure um destino fora da VM (`rclone config`, por exemplo Backblaze B2 ou um bucket privado). Teste a restauração (`docs/runbooks/restauracao-do-banco.md`) antes de confiar.

## 5. Operação

- Atualizar: `git pull && docker compose --env-file relay.env up -d --build`.
- Logs: `docker compose logs -f relay`; reinício: `docker compose restart relay`.
- **Nunca** publique a porta 8080 do relay (ADR 0040).
- Se a Oracle avisar de reclamação por inatividade, a VM precisa de uso: o relay conectado já conta, mas confirme na política atual.
