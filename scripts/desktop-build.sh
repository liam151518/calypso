#!/usr/bin/env bash
# scripts/desktop-build.sh. Build the Calypso desktop sidecar + Tauri shell.
#
# Phase H extends the legacy two-stage build with:
#   - The `calypso-render` sidecar binary (Phase A.4 / Phase G compositor
#     CLI entry). Useful for headless batch rendering on machines that
#     don't run the full GUI.
#   - A release checklist driven by `docs/RELEASE.md`.
#
# Run from repo root: `./scripts/desktop-build.sh`
#
# Outputs land under `desktop/src-tauri/binaries/` and
# `desktop/src-tauri/target/release/bundle/` for installer distribution.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

PYI="${PYI:-pyinstaller}"
TAURI_DIR="$ROOT/desktop/src-tauri"
BIN_DIR="$TAURI_DIR/binaries"
SPEC="$ROOT/scripts/calypso.spec"
ENTRYP="$ROOT/scripts/calypso_entry.py"

mkdir -p "$BIN_DIR"

# Determine host triple (Tauri convention: <arch>-<vendor>-<os>).
case "$(uname -s)" in
  Darwin) OS=apple; ARCH="$(uname -m)" ;;
  Linux)  OS=unknown; ARCH="$(uname -m)" ;;
  MINGW*|CYGWIN*|MSYS*) OS=pc; ARCH="windows-msvc" ;;
  *) echo "Unsupported OS: $(uname -s)"; exit 1 ;;
esac

TRIPLE="${ARCH}-${OS}"
echo "==> Target triple: $TRIPLE"

# -------- stage 1: PyInstaller sidecar --------
if [[ ! -f "$SPEC" ]]; then
  echo "FATAL: $SPEC not found"; exit 1
fi
if [[ ! -f "$ENTRYP" ]]; then
  echo "FATAL: $ENTRYP not found"; exit 1
fi

echo "==> PyInstaller: building sidecar..."
$PYI "$SPEC" --noconfirm --clean

# PyInstaller drops dist/calypso-sidecar (or .exe on Windows).
EXT=""
[[ "$OS" == "pc" ]] && EXT=".exe"

if [[ ! -f "$ROOT/dist/calypso-sidecar$EXT" ]]; then
  echo "FATAL: PyInstaller did not produce dist/calypso-sidecar$EXT"
  exit 1
fi
cp "$ROOT/dist/calypso-sidecar$EXT" "$BIN_DIR/calypso-sidecar-${TRIPLE}${EXT}"
chmod +x "$BIN_DIR/calypso-sidecar-${TRIPLE}${EXT}" || true
echo "==> Sidecar at: $BIN_DIR/calypso-sidecar-${TRIPLE}${EXT}"

# Tauri also expects a generic name when there's only one triple.
cp "$BIN_DIR/calypso-sidecar-${TRIPLE}${EXT}" "$BIN_DIR/calypso-sidecar${EXT}"

# -------- Phase H: calypso-render sidecar (headless batch render) --------
# A lighter binary that imports the Compositor without the Flask
# server. Lets a desktop user schedule batches in the background.
RENDER_SPEC="$ROOT/scripts/calypso_render.spec"
RENDER_ENTRY="$ROOT/scripts/calypso_render_entry.py"
if [[ -f "$RENDER_SPEC" && -f "$RENDER_ENTRY" ]]; then
  echo "==> PyInstaller: building calypso-render sidecar..."
  $PYI "$RENDER_SPEC" --noconfirm --clean
  if [[ -f "$ROOT/dist/calypso-render$EXT" ]]; then
    cp "$ROOT/dist/calypso-render$EXT" \
       "$BIN_DIR/calypso-render-${TRIPLE}${EXT}"
    cp "$BIN_DIR/calypso-render-${TRIPLE}${EXT}" \
       "$BIN_DIR/calypso-render${EXT}"
    chmod +x "$BIN_DIR/calypso-render-${TRIPLE}${EXT}" || true
    echo "==> Render sidecar at: $BIN_DIR/calypso-render-${TRIPLE}${EXT}"
  else
    echo "WARNING: calypso-render build did not produce dist/calypso-render$EXT"
  fi
else
  echo "INFO: calypso-render sidecar not configured (missing $RENDER_SPEC)"
fi

# -------- stage 2: Tauri --------
if ! command -v cargo >/dev/null 2>&1; then
  echo "WARNING: cargo not found. Skipping Tauri build (sidecar only)."
  echo "  Install Rust + cargo-tauri then re-run."
  exit 0
fi

echo "==> Tauri build..."
cd "$ROOT/desktop"
npm ci --no-audit --no-fund || npm install --no-audit --no-fund
npm run build

echo "==> Done. Installers under desktop/src-tauri/target/release/bundle/"
