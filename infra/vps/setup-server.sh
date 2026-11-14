#!/usr/bin/env bash
# Prepara uma VM Ubuntu 24.04 limpa para o relay (rode UMA vez, como root ou com sudo).
# Faz: atualizacoes automaticas, Docker, firewall (22, 80, 443), SSH so por chave, usuario `deploy` sem root.
# Nao baixa nem executa nada de terceiros alem dos pacotes oficiais do Ubuntu.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "rode como root: sudo bash $0" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
# As imagens da Oracle trazem o iptables-persistent com regras que barram tudo fora do 22. Ele conflita com o ufw
# (no Ubuntu 24.04 o ufw "Breaks" iptables-persistent): remova-o antes e deixe o ufw cuidar do firewall.
apt-get purge -y iptables-persistent netfilter-persistent 2>/dev/null || true
iptables -F INPUT 2>/dev/null || true
ip6tables -F INPUT 2>/dev/null || true

apt-get update -y
apt-get upgrade -y
apt-get install -y --no-install-recommends \
  docker.io docker-compose-v2 ufw unattended-upgrades ca-certificates curl git sqlite3

# --- atualizacoes de seguranca automaticas ---
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

# --- usuario de deploy (sem senha, sem root; acesso so por chave) ---
if ! id deploy >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" deploy
fi
usermod -aG docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
if [ -f /root/deploy_authorized_keys ]; then
  install -m 600 -o deploy -g deploy /root/deploy_authorized_keys /home/deploy/.ssh/authorized_keys
fi
install -d -o deploy -g deploy /opt/heycode /var/backups/heycode

# --- SSH endurecido: sem senha, sem login de root ---
install -d /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/99-heycode.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
sshd -t && systemctl reload ssh

# --- firewall ---
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# --- swap pequeno (VMs de 1 GB seguram melhor um pico de build) ---
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

systemctl enable --now docker
echo "Pronto. Proximo passo: como usuario deploy, clonar o repositorio em /opt/heycode e subir (infra/vps/README.md)."
