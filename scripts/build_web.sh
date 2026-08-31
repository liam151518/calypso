#!/usr/bin/env bash
# Build the React + Tailwind + shadcn SPA that lives in web/.
# Idempotent: skips npm install if node_modules already exists.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${ROOT_DIR}/web"

cd "${WEB_DIR}"

if [ ! -d node_modules ]; then
  echo "[build_web] Installing npm dependencies…"
  npm install --no-audit --no-fund --prefer-offline
fi

echo "[build_web] Building SPA…"
npm run build

echo "[build_web] Done. Output at ${WEB_DIR}/dist/"
