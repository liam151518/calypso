#!/usr/bin/env bash
# scripts/self-host.sh. Bootstrap a self-hosted Calypso Docker deployment.
#
# Run from repo root: `./scripts/self-host.sh`
#
# What it does:
#   1. Prompts for DOMAIN + EMAIL (or reads from .env).
#   2. Generates a strong admin password into .env.
#   3. Runs `docker compose build` + `docker compose up -d`.
#   4. Waits for /api/health to respond and prints the URL.
#
# Designed for a fresh VPS or local server. Idempotent. Re-running won't
# destroy existing data.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [[ ! -f docker-compose.yml ]]; then
  echo "FATAL: docker-compose.yml not found at $ROOT"; exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "FATAL: docker not installed"; exit 1
fi

# ---- 1. .env handling ----
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "Created .env from .env.example. Please review before continuing."
  else
    echo "FATAL: .env.example missing"; exit 1
  fi
fi

# ---- 2. Required keys ----
ensure_var() {
  local key="$1" prompt="$2"
  if ! grep -qE "^${key}=" .env || grep -qE "^${key}=$" .env; then
    read -r -p "${prompt}: " val
    sed -i.bak "s/^${key}=$/${key}=${val}/" .env || echo "${key}=${val}" >> .env
  fi
}

ensure_var DOMAIN "Public domain (e.g. calypso.example.com)"
ensure_var EMAIL  "Email for Let's Encrypt notifications"

if ! grep -qE "^CALYPSO_ADMIN_PASSWORD=" .env; then
  pw=$(openssl rand -hex 24 || python3 -c "import secrets;print(secrets.token_hex(24))")
  echo "CALYPSO_ADMIN_PASSWORD=$pw" >> .env
  echo "==> Generated admin password (saved to .env)."
fi

# ---- 3. Build + start ----
echo "==> docker compose build..."
docker compose build

echo "==> docker compose up -d..."
docker compose up -d

# ---- 4. Wait for health ----
echo "==> Waiting for /api/health..."
DOMAIN=$(grep -E "^DOMAIN=" .env | cut -d= -f2-)
for i in {1..30}; do
  if curl -sf -m 2 "http://localhost:8080/api/health" >/dev/null 2>&1; then
    echo "==> Calypso is healthy."
    echo "    Open: http://${DOMAIN:-localhost}/"
    exit 0
  fi
  sleep 1
done

echo "WARNING: Calypso didn't come up healthy in 30s."
echo "  Check logs with: docker compose logs -f calypso"
exit 1
