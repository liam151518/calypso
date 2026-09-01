#!/usr/bin/env bash
# Calypso. Local-first Flask web UI launcher.
# Run me once after cloning: `bash run.sh`
# Re-running is safe. Installs are skipped if already done.

set -euo pipefail

# Resolve repo root (parent of this script) and cd there
cd "$(dirname "$0")"
ROOT="$(pwd)"

# Pick a Python. Prefer python3, fall back to python.
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "error: python3 not found on PATH. Install Python 3.10+ first." >&2
  exit 1
fi

VENV_DIR="$ROOT/.venv"
REQ_FILE="$ROOT/app/requirements.txt"

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "→ creating virtualenv at $VENV_DIR"
  "$PY" -m venv "$VENV_DIR"
fi

# Install / upgrade requirements (idempotent)
echo "→ installing dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
"$VENV_DIR/bin/pip" install -q -r "$REQ_FILE"

# Build the React SPA (idempotent. Skipped if already built and node_modules present).
if [ -d "$ROOT/web" ]; then
  echo "→ building SPA"
  bash "$ROOT/scripts/build_web.sh"
fi

# Pick a port. Allow override via CALYPSO_PORT.
PORT="${CALYPSO_PORT:-8765}"
export CALYPSO_PORT="$PORT"

# Open the browser after a brief delay (background, non-blocking)
(
  sleep 2
  if command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:${PORT}" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:${PORT}" >/dev/null 2>&1 || true
  fi
) &

echo
echo "  ▸ Calypso running at http://127.0.0.1:${PORT}"
echo "  ▸ Press Ctrl-C to stop"
echo

# Run the app (exec so signals propagate correctly)
exec "$VENV_DIR/bin/python" -m app.server
