#!/usr/bin/env bash
set -euo pipefail

umask 077

BACKUP_ROOT="${BACKUP_ROOT:-}"
DATABASE_URL="${DATABASE_URL:-}"
BACKUP_ENCRYPTION_PASSWORD="${BACKUP_ENCRYPTION_PASSWORD:-}"
PG_BIN_DIR="${PG_BIN_DIR:-/opt/homebrew/opt/postgresql@18/bin}"

if [[ -d "$PG_BIN_DIR" ]]; then
  PATH="$PG_BIN_DIR:$PATH"
fi

if [[ -z "$DATABASE_URL" ]] && command -v security >/dev/null 2>&1; then
  DATABASE_URL="$(security find-generic-password -w -s sc-studio-render-database-url 2>/dev/null || true)"
fi
if [[ -z "$BACKUP_ENCRYPTION_PASSWORD" ]] && command -v security >/dev/null 2>&1; then
  BACKUP_ENCRYPTION_PASSWORD="$(security find-generic-password -w -s sc-studio-backup-password 2>/dev/null || true)"
fi

if [[ -z "$DATABASE_URL" ]]; then
  echo 'DATABASE_URL non configurata né disponibile nel Portachiavi.' >&2
  exit 1
fi
if [[ ${#BACKUP_ENCRYPTION_PASSWORD} -lt 20 ]]; then
  echo 'La password di cifratura deve contenere almeno 20 caratteri.' >&2
  exit 1
fi
case "$BACKUP_ROOT" in
  */sc-studio-backups) ;;
  *)
    echo 'BACKUP_ROOT deve terminare con /sc-studio-backups.' >&2
    exit 1
    ;;
esac

for command_name in pg_dump openssl shasum; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Comando mancante: $command_name" >&2
    exit 1
  fi
done

mkdir -p "$BACKUP_ROOT/daily" "$BACKUP_ROOT/weekly" "$BACKUP_ROOT/monthly"
chmod 700 "$BACKUP_ROOT" "$BACKUP_ROOT/daily" "$BACKUP_ROOT/weekly" "$BACKUP_ROOT/monthly"

temporary_directory="$(mktemp -d "${TMPDIR:-/tmp}/sc-studio-backup.XXXXXX")"
trap 'rm -rf "$temporary_directory"' EXIT

timestamp="$(date -u '+%Y-%m-%dT%H%M%SZ')"
filename="sc-studio-${timestamp}.dump.enc"
raw_dump="$temporary_directory/sc-studio.dump"
daily_backup="$BACKUP_ROOT/daily/$filename"

pg_dump \
  --dbname="$DATABASE_URL" \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-acl \
  --file="$raw_dump"

BACKUP_ENCRYPTION_PASSWORD="$BACKUP_ENCRYPTION_PASSWORD" \
  openssl enc -aes-256-cbc -salt -pbkdf2 -iter 600000 \
  -pass env:BACKUP_ENCRYPTION_PASSWORD \
  -in "$raw_dump" \
  -out "$daily_backup"

rm -f "$raw_dump"
(
  cd "$BACKUP_ROOT/daily"
  shasum -a 256 "$filename" > "$filename.sha256"
)

if [[ "$(date -u '+%u')" == '7' ]]; then
  cp -p "$daily_backup" "$BACKUP_ROOT/weekly/$filename"
  cp -p "$daily_backup.sha256" "$BACKUP_ROOT/weekly/$filename.sha256"
fi
if [[ "$(date -u '+%d')" == '01' ]]; then
  cp -p "$daily_backup" "$BACKUP_ROOT/monthly/$filename"
  cp -p "$daily_backup.sha256" "$BACKUP_ROOT/monthly/$filename.sha256"
fi

find "$BACKUP_ROOT/daily" -type f \( -name '*.dump.enc' -o -name '*.dump.enc.sha256' \) -mtime +14 -print -delete
find "$BACKUP_ROOT/weekly" -type f \( -name '*.dump.enc' -o -name '*.dump.enc.sha256' \) -mtime +56 -print -delete
find "$BACKUP_ROOT/monthly" -type f \( -name '*.dump.enc' -o -name '*.dump.enc.sha256' \) -mtime +370 -print -delete

echo "Backup completato: $daily_backup"
