# Calypso — Installation Guide

## Prerequisites

- **Python 3.11+** (`python3 --version` should report 3.11 or higher)
- **Node 20+** with `npm` (for the SPA)
- **SQLite 3.40+** (bundled with Python)
- **FFmpeg** on `PATH` (Phase D video rendering)
- **Tauri CLI** (`cargo install tauri-cli`) for desktop builds

## Quick start (local development)

```bash
# Clone the repo
git clone https://github.com/<your-org>/calypso.git
cd calypso

# Backend
python3 -m pip install --break-system-packages -r app/requirements.txt
python3 -m pip install --break-system-packages jsonschema rembg onnxruntime apscheduler opencv-python-headless ffmpeg-python Pillow

# Frontend
cd web
npm install --legacy-peer-deps
npm run build
cd ..

# Run the dev server
./run.sh
```

Open http://localhost:5173 (web) and http://localhost:8000 (API).

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Purpose |
|----------|----------|---------|
| `MINIMAX_API_TOKEN` | optional | H3 miniMax model (image + caption fallback) |
| `FAL_API_KEY` | optional | H3 Max, Kling 2.6 Pro, video/image gen |
| `OMNI_API_KEY` | optional | Opt-in Omni motion graphics backend |
| `TELEGRAM_BOT_TOKEN` | optional | Telegram approval gate |
| `TELEGRAM_CHAT_ID` | optional | Telegram chat for approvals |
| `CALYPSO_DB` | optional | Override SQLite path (default `.calypso/calypso.db`) |

Variables left empty simply disable that integration; the rest of
Calypso still works.

## Docker

```bash
docker compose up
```

This builds the SPA, the Flask backend, and Caddy (TLS reverse proxy).
See `docker-compose.yml` and `Caddyfile` for details.

## Desktop (Tauri + PyInstaller)

```bash
./scripts/desktop-build.sh
```

Produces:
- `desktop/src-tauri/binaries/calypso-sidecar-<triple>` (Flask backend)
- `desktop/src-tauri/binaries/calypso-render-<triple>` (headless batch render)
- Installers under `desktop/src-tauri/target/release/bundle/`

## Verifying the install

```bash
bash verify.sh
```

Exits 0 when all checks pass.