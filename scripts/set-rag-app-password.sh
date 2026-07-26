#!/usr/bin/env bash
# Sets/rotates the login password for the rag_app role created by
# migrations/0002_scoped_app_role.sql. Password is never stored in a
# tracked file -- pass it via environment (e.g. sourced from .env, which
# is gitignored) each time this runs. Safe to re-run (idempotent ALTER).
#
# Mirrors internal-db/scripts/set-app-role-passwords.sh. Runs through
# `docker exec` by default (the deploy host has no local psql client --
# only the Postgres container does). This role lives in internal-db's
# Postgres instance/container (internal-db-db-1), not a separate rag-01
# container -- see 0001_rag_schema.sql.
#
# Usage: RAG_APP_PASSWORD=... ./scripts/set-rag-app-password.sh
set -euo pipefail

: "${RAG_APP_PASSWORD:?Set RAG_APP_PASSWORD}"

CONTAINER_NAME="${POSTGRES_CONTAINER:-internal-db-db-1}"
DB_USER="${POSTGRES_USER:-hellfire}"
DB_NAME="${POSTGRES_DB:-hellfire_internal}"

run_psql() {
  # Piped via stdin, not -c: psql only does :'var' interpolation when
  # reading a script, not for -c's simple-query path.
  if [ -n "${DATABASE_URL:-}" ] && [ -z "${POSTGRES_CONTAINER:-}" ] && command -v psql >/dev/null 2>&1; then
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 "$@"
  else
    docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 "$@"
  fi
}

run_psql \
  -v rag_pw="$RAG_APP_PASSWORD" \
  <<'SQL'
ALTER ROLE rag_app WITH PASSWORD :'rag_pw';
SQL

echo "done. rag_app password set."
