#!/usr/bin/env bash
# Run once in WSL Ubuntu as the developer account.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
if [[ ! -f .env.postgres ]]; then
  for name in sentinelops payflow; do
    password=$(openssl rand -hex 32)
    printf 'export %s_DATABASE_URL=postgresql+psycopg://%s:%s@127.0.0.1/%s\n' "${name^^}" "$name" "$password" "$name"
  done > .env.postgres
fi
source .env.postgres
for name in sentinelops payflow; do
  var="${name^^}_DATABASE_URL"
  password="${!var#*://*:}"
  password="${password%@*}"
  [[ "$password" =~ ^[0-9a-f]{64}$ ]]
  if ! sudo -u postgres psql -Atqc "SELECT 1 FROM pg_roles WHERE rolname='$name'" | grep -qx 1; then
    printf "CREATE ROLE %s LOGIN PASSWORD '%s';\n" "$name" "$password" | sudo -u postgres psql -v ON_ERROR_STOP=1
  fi
  if ! sudo -u postgres psql -Atqc "SELECT 1 FROM pg_database WHERE datname='$name'" | grep -qx 1; then
    sudo -u postgres createdb -O "$name" "$name"
  fi
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "REVOKE CONNECT ON DATABASE $name FROM PUBLIC"
done
(cd backend/api && ../../.venv/bin/alembic upgrade head)
(cd applications/payflow/payment-service && ../../../.venv/bin/alembic upgrade head)
