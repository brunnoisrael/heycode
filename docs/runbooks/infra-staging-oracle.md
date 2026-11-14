# Staging do relay na Oracle Cloud (Always Free): estado, operação e o que aprendemos

Registro do que existe hoje (2026-11-14), de como foi criado e das armadilhas que custaram tempo. Decisões: ADRs 0054 a 0056. Pacote de deploy: `infra/vps/`.

## O que existe

| Item | Valor |
|---|---|
| VM | `heycode-relay`, forma `VM.Standard.E2.1.Micro` (AMD, 1 OCPU, 1 GB, **Always Free**), Ubuntu 24.04 Minimal, São Paulo (AD-1) |
| IP público | `152.67.63.70` (efêmero: se a VM for recriada, o IP muda e o DNS precisa seguir) |
| Rede | VCN `agent-vcn` (preexistente), sub-rede pública; lista de segurança com entrada em 22, 80 e 443 |
| Firewall local | `ufw` com 22, 80 e 443 |
| DNS | Cloudflare, zona `heycode.dev.br`: `staging-api` e `staging-app` (`A` para o IP, **somente DNS**, nuvem cinza). `ponte.` (túnel `roomcode`, proxied) é de outra instalação e não se toca |
| HTTPS | Caddy (Let's Encrypt), renovação automática; volume `heycode_caddy_data` guarda os certificados |
| Serviços | `docker compose` em `/opt/heycode/infra/vps` (projeto `heycode`): `relay` e `caddy` |
| Segredos | `/opt/heycode/infra/vps/relay.env` (modo 600, só no servidor): `OAUTH_CLIENT_SECRET` gerado lá; o mesmo valor está no account linking do console da Amazon |
| Backup | timer `heycode-backup.timer` (03:17 UTC, `Persistent`), arquivos em `/var/backups/heycode` (14 mais recentes) |
| Acesso | `deploy@IP` (sem `sudo`, só chave) e `ubuntu@IP` (com `sudo`, só para systemd e firewall). Root não entra por SSH, senha desligada |

A chave SSH de deploy fica **no computador do dono** (`C:\Users\Sergio\.heycode-tools\oracle_heycode`), nunca no repositório.

## Operação do dia a dia

```bash
ssh -i CHAVE deploy@152.67.63.70
cd /opt/heycode/infra/vps
docker compose ps && docker compose logs -f relay
docker compose --env-file relay.env up -d --build      # depois de atualizar o codigo
sudo systemctl list-timers heycode-backup.timer         # como ubuntu
```

**Atualizar o código:** o servidor não tem acesso ao repositório (não há remoto Git ainda). Gere e envie um pacote:

```bash
git archive --format=tar.gz --prefix=heycode/ -o heycode-src.tar.gz HEAD     # na raiz do repositorio, no branch certo
scp -i CHAVE heycode-src.tar.gz deploy@IP:/tmp/
ssh -i CHAVE deploy@IP 'cd /opt/heycode && tar xzf /tmp/heycode-src.tar.gz --strip-components=1 && cd infra/vps && docker compose --env-file relay.env up -d --build'
```

O `relay.env` não vem no pacote (não está no Git): ele permanece como está no servidor.

## Como a VM foi criada (e por que levou tentativas)

1. Conta Free Tier (o teste grátis já tinha acabado): só recursos "Always Free elegível" são permitidos. **Nunca faça "Upgrade"** da conta, ou o que passar do limite passa a ser cobrado.
2. Criar instância: nome, imagem **Canonical Ubuntu 24.04 Minimal** (x86 para a Micro; a variante `aarch64` só aparece para a Ampere), forma Micro, VCN existente com IP público, chave SSH colada (só a **pública**), volume de boot padrão (46,6 GB, dentro dos 200 GB gratuitos).
3. São Paulo tem **um único domínio de disponibilidade** e a Oracle devolve "Capacidade insuficiente" para as formas gratuitas com frequência: a A1 (ARM) nunca liberou nas tentativas; a Micro criou na 5ª tentativa, em ~6 minutos. O script `scripts/ops/oracle_retry_create.py` repete o clique em **Criar** a cada ~1 minuto, para no primeiro sucesso (nunca cria duas) e dá um limite de tentativas.
4. Abrir 80 e 443 na lista de segurança da sub-rede (Redes → VCN → Segurança → Regras de entrada, origem `0.0.0.0/0`, TCP).
5. Preparar o servidor com `infra/vps/setup-server.sh`, subir o Compose, apontar o DNS e só então subir o Caddy (ele precisa do DNS resolvendo para obter o certificado).

## Armadilhas encontradas (todas já corrigidas no pacote)

- `ufw` **conflita** com `iptables-persistent` (que a imagem da Oracle traz): remover o segundo antes de instalar o primeiro.
- `pip install .` na imagem falhava: o `pyproject.toml` embute `scripts/gates` e `.githooks` no wheel; o `Dockerfile` precisa copiá-los.
- O nome do volume do Compose vem do nome da pasta (`vps`): fixar `name: heycode`.
- A imagem mínima **não tem `cron`**: usar timer do systemd. O `deploy` não grava em `/var/log`: o log vai para o journal.
- O contêiner do backup roda como `nobody`: precisa de `--user "$(id -u):$(id -g)"` para gravar em `/var/backups`, e de `-i` para ler o script do stdin (sem ele, o Python lê nada e "dá certo" com arquivo vazio; por isso o script valida o banco e apaga o arquivo parcial).
- No console da Oracle os campos do assistente ficam dentro de um **iframe**: automação precisa buscar o frame que contém os `input`.

## Riscos aceitos e pendências

- A Oracle pode reclamar VMs gratuitas com pouco uso ou sem capacidade; **o backup precisa ir para fora do servidor** (hoje só existe cópia local; configurar `rclone` e `BACKUP_REMOTE`).
- 1 GB de RAM: o relay usa ~43 MB, o build da imagem usa o swap de 2 GB. Se o uso crescer, migrar (o Compose roda em qualquer Ubuntu).
- A restauração do backup **nunca foi testada** (`docs/runbooks/restauracao-do-banco.md`).
- Instância única: sem alta disponibilidade (o componente local reconecta sozinho quando o relay volta).
