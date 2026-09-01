# Calypso Dockerfile. Single-image Python backend + built SPA.
#
# Build:    docker build -t calypso:latest .
# Run:      docker run -p 8080:8080 -v $PWD/data:/data calypso:latest
# Compose:  see docker-compose.yml (recommended: Caddy + Calypso + volumes)
#
# Phase B deliverable. The SPA is expected to be built first:
#     cd web && npm ci && npm run build
# The build step embeds web/dist/ into the image so the Flask app can serve
# it directly from the same process (no separate static host).

FROM python:3.12-slim AS base

# Avoid interactive prompts and keep Python logs unbuffered.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CALYPSO_HOST=0.0.0.0 \
    CALYPSO_PORT=8080 \
    CALYPSO_HOME=/data

# System deps. We intentionally keep this minimal. Runtime deps are all
# pure-Python (Flask, requests, pillow, etc.).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates curl tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what we need to install first, for layer caching.
COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY web/dist/ ./web/dist/
COPY brand/ ./brand/
COPY references/ ./references/

# Install Calypso + runtime deps. The package installs the `calypso` CLI
# which boots the Flask app via `python -m app.server`.
RUN python -m pip install --upgrade pip \
 && python -m pip install -e .

# Persistent volume mount point for SQLite DB, outputs/, references/.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8080/api/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "app.server"]
