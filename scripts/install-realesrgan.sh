#!/usr/bin/env bash
# install-realesrgan.sh. Optional installer for Real-ESRGAN ncnn.
#
# Used by: app/upscale.py when the operator picks the "realesrgan" backend.
# Without this binary, upscale() transparently falls back to the PIL/fal paths.
#
# Tested on macOS (Apple Silicon + Intel). On Linux you'll need the Vulkan SDK
# plus nvidia/cuda drivers — see https://github.com/xinntao/Real-ESRGAN.

set -euo pipefail

if command -v realesrgan-ncnn-vulkan >/dev/null 2>&1; then
    echo "realesrgan-ncnn-vulkan already on PATH"
    exit 0
fi

OS=$(uname -s)
ARCH=$(uname -m)

case "$OS:$ARCH" in
    Darwin:arm64) BIN=realesrgan-ncnn-vulkan-macos ;;
    Darwin:x86_64) BIN=realesrgan-ncnn-vulkan-macos ;;
    Linux:x86_64) BIN=realesrgan-ncnn-vulkan-linux ;;
    *) echo "Unsupported platform: $OS/$ARCH"; exit 1 ;;
esac

RELEASE_URL="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "Downloading Real-ESRGAN ncnn..."
curl -L -o "$TMPDIR/realesrgan.zip" "$RELEASE_URL" || {
    echo "Download failed. Check the URL for your platform." >&2
    exit 1
}

cd "$TMPDIR"
unzip -q realesrgan.zip

INSTALL_DIR="$HOME/.calypso/bin"
mkdir -p "$INSTALL_DIR"

# Find the binary inside the extracted folder
BIN_PATH=$(find "$TMPDIR" -name "$BIN" -type f | head -n 1)
if [[ -z "$BIN_PATH" ]]; then
    BIN_PATH=$(find "$TMPDIR" -name "realesrgan-ncnn-vulkan" -type f | head -n 1)
fi
if [[ -z "$BIN_PATH" ]]; then
    echo "Could not locate the binary in the archive" >&2
    exit 1
fi

cp "$BIN_PATH" "$INSTALL_DIR/realesrgan-ncnn-vulkan"
chmod +x "$INSTALL_DIR/realesrgan-ncnn-vulkan"

echo "Installed to $INSTALL_DIR/realesrgan-ncnn-vulkan"
echo "Add to PATH:  export PATH=\"$INSTALL_DIR:\$PATH\""
echo "Or set:       export REALESRGAN_BIN=\"$INSTALL_DIR/realesrgan-ncnn-vulkan\""
