#!/usr/bin/env bash
set -euo pipefail

# Porta de /var/www/sistema_arq/shared/scripts/backup_postgres.sh: mesmo
# formato de .env (DATABASE_URL), mas checkout direto (sem shared/) — os
# dumps ficam fora do working tree do git, em /home/rod/backups, para não
# interagir com git clean/status.

APP_ROOT="/var/www/dojo"
ENV_FILE="$APP_ROOT/.env"
BACKUP_DIR="/home/rod/backups/dojo/postgres"
LOG_DIR="/home/rod/backups/dojo/logs"
LOG_FILE="$LOG_DIR/postgres-backup.log"
LOCK_FILE="/tmp/dojo_postgres_backup.lock"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

{
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] backup start"

  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERRO: arquivo de ambiente nao encontrado: $ENV_FILE"
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERRO: DATABASE_URL nao definido em $ENV_FILE"
    exit 1
  fi

  timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
  db_name="$(echo "$DATABASE_URL" | sed -E 's#^[^:]+://[^/]+/([^?]+).*$#\1#')"
  [[ -z "$db_name" || "$db_name" == "$DATABASE_URL" ]] && db_name="database"

  outfile="$BACKUP_DIR/${db_name}_${timestamp}.dump"
  tmpfile="$outfile.tmp"

  flock -n 9 || { echo "Backup ja em execucao, saindo"; exit 0; }

  pg_dump \
    --format=custom \
    --no-owner \
    --no-privileges \
    --file "$tmpfile" \
    "$DATABASE_URL"

  pg_restore -l "$tmpfile" >/dev/null
  mv "$tmpfile" "$outfile"
  chmod 600 "$outfile"

  find "$BACKUP_DIR" -type f -name '*.dump' -mtime +"$RETENTION_DAYS" -delete

  latest_size="$(du -h "$outfile" | awk '{print $1}')"
  echo "Backup concluido: $outfile ($latest_size)"
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] backup end"
} >> "$LOG_FILE" 2>&1 9> "$LOCK_FILE"
