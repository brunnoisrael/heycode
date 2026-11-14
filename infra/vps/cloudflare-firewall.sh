#!/usr/bin/env bash
# Deixa as portas 80 e 443 abertas SO para a Cloudflare (ADR 0058). Rode como root, depois de ligar o proxy
# (nuvem laranja) nos registros DNS. O SSH (22) nao e tocado.
#
#   sudo bash cloudflare-firewall.sh apply    # aplica (idempotente; roda de novo a cada boot pelo systemd)
#   sudo bash cloudflare-firewall.sh remove   # volta a aceitar 80/443 de qualquer origem
#   sudo bash cloudflare-firewall.sh status   # mostra as regras em vigor
#
# Por que nao basta o ufw: as portas publicadas pelo Docker passam pela cadeia FORWARD, antes das regras do
# ufw. O filtro precisa estar na cadeia DOCKER-USER, que o Docker reserva para regras do administrador.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LIST="${CLOUDFLARE_IPS:-$HERE/cloudflare-ips.txt}"
CHAIN="HEYCODE-WEB"
V4='^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$'
V6='^[0-9a-fA-F:]+/[0-9]{1,3}$'

[ "$(id -u)" -eq 0 ] || { echo "rode como root: sudo bash $0 ${1:-apply}" >&2; exit 1; }

ranges() { # $1 = expressao regular da familia; imprime so as linhas validas
  grep -Ev '^\s*(#|$)' "$LIST" | grep -E "$1" || true
}

detach() { # tira os saltos e apaga a cadeia, se existirem
  local cmd="$1"
  for port in 80 443; do
    while "$cmd" -D DOCKER-USER -p tcp -m conntrack --ctorigdstport "$port" --ctdir ORIGINAL -j "$CHAIN" 2>/dev/null; do :; done
  done
  "$cmd" -F "$CHAIN" 2>/dev/null || true
  "$cmd" -X "$CHAIN" 2>/dev/null || true
}

attach() { # $1 = iptables|ip6tables, $2 = expressao regular da familia
  local cmd="$1" count=0
  "$cmd" -L DOCKER-USER -n >/dev/null 2>&1 || return 0 # sem Docker nesta familia: nada a filtrar aqui
  detach "$cmd"
  "$cmd" -N "$CHAIN"
  while read -r range; do
    "$cmd" -A "$CHAIN" -s "$range" -j RETURN
    count=$((count + 1))
  done < <(ranges "$2")
  if [ "$count" -eq 0 ]; then
    detach "$cmd"
    echo "nenhuma faixa valida em $LIST para $cmd: nada aplicado" >&2
    return 1
  fi
  "$cmd" -A "$CHAIN" -j DROP
  for port in 80 443; do
    # --ctorigdstport: a porta que o cliente pediu, antes do redirecionamento do Docker para o conteiner
    "$cmd" -I DOCKER-USER -p tcp -m conntrack --ctorigdstport "$port" --ctdir ORIGINAL -j "$CHAIN"
  done
  echo "$cmd: 80/443 aceitam $count faixas da Cloudflare"
}

ufw_rules() { # $1 = allow|delete ; regras do ufw valem para o que NAO passa pelo Docker (ex.: IPv6 sem NAT)
  local action="$1" range
  while read -r range; do
    if [ "$action" = allow ]; then
      ufw allow proto tcp from "$range" to any port 80,443 comment 'cloudflare' >/dev/null
    else
      ufw --force delete allow proto tcp from "$range" to any port 80,443 >/dev/null 2>&1 || true
    fi
  done < <(ranges "$V4"; ranges "$V6")
}

case "${1:-apply}" in
  apply)
    [ -r "$LIST" ] || { echo "lista nao encontrada: $LIST" >&2; exit 1; }
    attach iptables "$V4"
    attach ip6tables "$V6"
    if command -v ufw >/dev/null; then
      ufw_rules allow
      ufw --force delete allow 80/tcp >/dev/null 2>&1 || true
      ufw --force delete allow 443/tcp >/dev/null 2>&1 || true
    fi
    echo "Pronto. Confira de fora da Cloudflare: curl -m 5 https://IP_DA_VM/health -k   (deve dar tempo esgotado)"
    ;;
  remove)
    detach iptables
    detach ip6tables
    if command -v ufw >/dev/null; then
      ufw allow 80/tcp >/dev/null
      ufw allow 443/tcp >/dev/null
      ufw_rules delete
    fi
    echo "Filtro removido: 80/443 aceitam qualquer origem."
    ;;
  status)
    iptables -S DOCKER-USER 2>/dev/null | grep -- "$CHAIN" || echo "iptables: sem filtro"
    iptables -S "$CHAIN" 2>/dev/null | grep -c -- '-j RETURN' | sed 's/^/faixas IPv4 aceitas: /' || true
    ip6tables -S "$CHAIN" 2>/dev/null | grep -c -- '-j RETURN' | sed 's/^/faixas IPv6 aceitas: /' || true
    ;;
  *)
    echo "uso: $0 apply|remove|status" >&2
    exit 2
    ;;
esac
