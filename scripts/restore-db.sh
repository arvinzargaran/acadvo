#!/usr/bin/env bash
#
# Restore a backup produced by scripts/backup-db.sh.
#
#   ./scripts/restore-db.sh backups/acadvo-20260819T031500Z.sql.gz
#
# THIS OVERWRITES THE TARGET DATABASE. The dump is taken with --clean, so every
# table it contains is dropped and recreated. The script stops the backend first
# so no request writes into a half-restored schema, and starts it again after.
#
# Practise this on a scratch host before you need it. The restore path is the
# half of a backup system that actually gets exercised in an emergency, and it
# is the half nobody tests.

set -euo pipefail

cd "$(dirname "$0")/.."

DUMP="${1:-}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"

if [[ -z "$DUMP" || ! -f "$DUMP" ]]; then
  echo "usage: $0 <backup.sql.gz>" >&2
  exit 1
fi

POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"

echo "About to restore $DUMP into database '$POSTGRES_DB'."
echo "Everything currently in it will be replaced."
read -r -p "Type the database name to confirm: " confirm
[[ "$confirm" == "$POSTGRES_DB" ]] || { echo "aborted."; exit 1; }

echo "==> stopping backend"
docker compose -f "$COMPOSE_FILE" stop backend

echo "==> restoring"
# ON_ERROR_STOP=1 so a failed statement aborts loudly instead of leaving a
# partially-restored database that psql reports as a success.
gzip -dc "$DUMP" | docker compose -f "$COMPOSE_FILE" exec -T db \
  psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
       --no-password --set ON_ERROR_STOP=1

echo "==> starting backend (runs 'alembic upgrade head' on boot)"
docker compose -f "$COMPOSE_FILE" start backend

echo "==> done. Check https://\$APP_DOMAIN and the backend logs before declaring victory."
