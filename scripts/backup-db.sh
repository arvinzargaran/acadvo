#!/usr/bin/env bash
#
# Take a compressed, verified snapshot of the production database.
#
# The prod stack publishes no host port for Postgres (see docker-compose.prod.yml),
# so this runs pg_dump *inside* the db container and streams the dump out over
# the docker exec pipe. Nothing is written inside the container, so it works
# against the read-only/tmpfs hardening.
#
#   ./scripts/backup-db.sh                  # -> ./backups/acadvo-<utc-stamp>.sql.gz
#   BACKUP_DIR=/mnt/vol ./scripts/backup-db.sh
#   RETENTION_DAYS=30 ./scripts/backup-db.sh
#
# Run it from cron on the host, e.g. nightly at 03:15 UTC:
#   15 3 * * * cd /srv/acadvo && ./scripts/backup-db.sh >> /var/log/acadvo-backup.log 2>&1
#
# A backup that has never been restored is a hope, not a backup. Restore into a
# scratch database and check it every so often — see scripts/restore-db.sh.
#
# IMPORTANT: these dumps contain every user's account and academic record. Keep
# them off the application host (object storage, another machine), encrypted at
# rest, and out of the repo — ./backups is gitignored.

set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "error: $ENV_FILE not found — run this on the deployment host." >&2
  exit 1
fi

# POSTGRES_USER/DB live in the same .env the stack is started with. Sourced in a
# subshell-safe way: only the two names we need are exported onward.
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"

if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_DB:-}" ]]; then
  echo "error: POSTGRES_USER / POSTGRES_DB are not set in $ENV_FILE." >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/acadvo-$STAMP.sql.gz"
TMP="$OUT.partial"

echo "==> dumping $POSTGRES_DB -> $OUT"

# --clean --if-exists so the dump can be replayed over an existing database
# without hand-dropping it first. No --owner juggling: the restore target uses
# the same role name, which the compose file guarantees.
#
# Writing to .partial first means an interrupted run can never leave a truncated
# file that looks like a good backup.
docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
          --clean --if-exists --no-password \
  | gzip -9 > "$TMP"

# Verify before promoting: gzip -t catches a truncated stream, and a dump that
# lost its tail has no terminator line. Both failures are silent otherwise, and
# a corrupt backup is discovered exactly when it is least welcome.
gzip -t "$TMP"
if ! gzip -dc "$TMP" | tail -5 | grep -q 'PostgreSQL database dump complete'; then
  echo "error: dump is incomplete (no terminator) — keeping $TMP for inspection." >&2
  exit 1
fi

mv "$TMP" "$OUT"
echo "==> ok: $(du -h "$OUT" | cut -f1)"

if [[ "$RETENTION_DAYS" -gt 0 ]]; then
  echo "==> pruning backups older than $RETENTION_DAYS days"
  find "$BACKUP_DIR" -name 'acadvo-*.sql.gz' -type f -mtime "+$RETENTION_DAYS" -print -delete
fi
