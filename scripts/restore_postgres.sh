#!/usr/bin/env bash
set -euo pipefail

umask 077

encrypted_backup="${1:-}"
RESTORE_DATABASE_URL="${RESTORE_DATABASE_URL:-}"
BACKUP_ENCRYPTION_PASSWORD="${BACKUP_ENCRYPTION_PASSWORD:-}"
PG_BIN_DIR="${PG_BIN_DIR:-/opt/homebrew/opt/postgresql@18/bin}"

if [[ -d "$PG_BIN_DIR" ]]; then
  PATH="$PG_BIN_DIR:$PATH"
fi

if [[ -z "$RESTORE_DATABASE_URL" ]] && command -v security >/dev/null 2>&1; then
  RESTORE_DATABASE_URL="$(security find-generic-password -w -s sc-studio-restore-database-url 2>/dev/null || true)"
fi
if [[ -z "$BACKUP_ENCRYPTION_PASSWORD" ]] && command -v security >/dev/null 2>&1; then
  BACKUP_ENCRYPTION_PASSWORD="$(security find-generic-password -w -s sc-studio-backup-password 2>/dev/null || true)"
fi

if [[ ! -f "$encrypted_backup" || ! -f "$encrypted_backup.sha256" ]]; then
  echo 'Specificare un backup cifrato con il relativo file .sha256.' >&2
  exit 1
fi
if [[ -z "$RESTORE_DATABASE_URL" ]]; then
  echo 'RESTORE_DATABASE_URL non configurata né disponibile nel Portachiavi.' >&2
  exit 1
fi
if [[ ${#BACKUP_ENCRYPTION_PASSWORD} -lt 20 ]]; then
  echo 'Password di cifratura mancante o non valida.' >&2
  exit 1
fi

for command_name in pg_restore psql openssl shasum; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Comando mancante: $command_name" >&2
    exit 1
  fi
done

(
  cd "$(dirname "$encrypted_backup")"
  shasum -a 256 -c "$(basename "$encrypted_backup").sha256"
)

existing_tables="$(psql "$RESTORE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -c \
  "SELECT COUNT(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public';")"
if [[ "$existing_tables" != '0' ]]; then
  echo 'Ripristino rifiutato: il database di destinazione non è vuoto.' >&2
  exit 1
fi

temporary_directory="$(mktemp -d "${TMPDIR:-/tmp}/sc-studio-restore.XXXXXX")"
trap 'rm -rf "$temporary_directory"' EXIT
raw_dump="$temporary_directory/sc-studio.dump"

BACKUP_ENCRYPTION_PASSWORD="$BACKUP_ENCRYPTION_PASSWORD" \
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 \
  -pass env:BACKUP_ENCRYPTION_PASSWORD \
  -in "$encrypted_backup" \
  -out "$raw_dump"

pg_restore \
  --dbname="$RESTORE_DATABASE_URL" \
  --no-owner \
  --no-acl \
  --exit-on-error \
  --single-transaction \
  "$raw_dump"

restored_tables="$(psql "$RESTORE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -c \
  "SELECT COUNT(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public';")"
echo "Ripristino completato e verificato: $restored_tables tabelle pubbliche."
