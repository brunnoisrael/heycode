#!/usr/bin/env bash
# Backup consistente do banco do relay (API de backup do SQLite, com o relay no ar) + rotacao + copia externa.
# Agende no cron do usuario deploy:  17 3 * * * /opt/heycode/infra/vps/backup.sh >>/var/log/heycode-backup.log 2>&1
# ATENCAO: um backup que fica so neste servidor NAO e backup. Configure BACKUP_REMOTE (rclone) ou copie para
# fora por conta propria (ver README). O backup contem hashes de senha e chaves publicas: proteja o destino.
set -euo pipefail

DEST="${BACKUP_DIR:-/var/backups/heycode}"
KEEP="${BACKUP_KEEP:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$DEST/relay-$STAMP.db"
mkdir -p "$DEST"
umask 077
trap 'rm -f "$FILE"' ERR # nunca deixa um backup parcial ou vazio para tras

# executa dentro de uma copia efemera da imagem do relay, lendo o mesmo volume
docker run --rm -i --user "$(id -u):$(id -g)" \
  -v heycode_relay_data:/data:ro \
  -v "$DEST":/out \
  --entrypoint python heycode-relay:local - "$STAMP" <<'PY'
import sqlite3, sys
src = sqlite3.connect("file:/data/relay.db?mode=ro", uri=True)
dst = sqlite3.connect(f"/out/relay-{sys.argv[1]}.db")
src.backup(dst)
dst.close(); src.close()
PY

# confere que o arquivo abre e tem as tabelas esperadas
python3 - "$FILE" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
names = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
assert {"accounts", "installations"} <= names, names
PY

gzip -f "$FILE"
chmod 600 "$FILE.gz"
ls -1t "$DEST"/relay-*.db.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f

if [ -n "${BACKUP_REMOTE:-}" ]; then
  rclone copy "$FILE.gz" "$BACKUP_REMOTE" --immutable
  echo "copiado para $BACKUP_REMOTE"
else
  echo "AVISO: BACKUP_REMOTE nao configurado; este backup so existe neste servidor." >&2
fi
echo "ok: $FILE.gz"
