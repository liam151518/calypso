# Release Checklist

Run through this checklist before tagging a release.

## 1. Tests

```bash
python3 -m pytest -q           # backend
cd web && npx vitest run        # frontend
cd web && npx tsc --noEmit      # type check
bash verify.sh                  # release readiness
```

All four must exit 0. Pre-existing failures in `test_video_clients.py`
(month-rollover SpendState bug) and the 8 `e2e/test_*.py`
timeout errors are tracked separately and are not blockers for an
early Phase H release.

## 2. Build

```bash
cd web && npm run build         # SPA bundle
./scripts/desktop-build.sh      # PyInstaller sidecar + Tauri shell
```

The desktop build produces installers under
`desktop/src-tauri/target/release/bundle/`:

- `.deb` + `.AppImage` on Linux
- `.dmg` on macOS
- `.exe` (NSIS) + `.msi` on Windows

## 3. Smoke test

```bash
python3 -m app one_shot "Make a 30s unboxing for these new sneakers, hype energy, 18-25 streetwear"
ls -la outputs/videos/
```

The render should land in `outputs/videos/`. Review it manually.

## 4. Docs

- [x] `docs/install.md` — fresh-install walkthrough
- [x] `docs/quickstart.md` — first-render walkthrough
- [x] `docs/templates.md` — Template schema reference
- [x] `docs/studio.md` — Studio Pro agent architecture
- [x] `docs/video_pipeline.md` — UGC + one_shot + motion + cost cap
- [x] `docs/omni_integration.md` — when to enable Omni
- [x] `docs/api.md` — full HTTP API reference
- [x] `docs/RELEASE.md` — this file

## 5. Marketplace

The extension manifest schema lives at
`scripts/extensions/SCHEMA.md`. HMAC signing key (`calypso_signing`)
is provided via env var; the bundle includes the verify helper at
`scripts/extensions/signing.py`.

To release a new extension:

```bash
python3 scripts/extensions/sign.py path/to/extension.tar.gz
python3 scripts/extensions/publish.py --tag v0.X
```

## 6. Tag

```bash
git tag -s v0.X -m "Calypso v0.X"
git push --tags
```

The release workflow builds the SPA, the desktop bundles, and uploads
to the marketplace object store.

## 7. Self-hosting (Docker)

For a self-hosted installation, publish the SPA + Flask container via
`docker compose up`. The bundled `Caddyfile` reverse-proxies traffic to
the Flask app and serves the SPA bundle as static files. Update the
`.env` file with the marketplace URL and signing key, then restart.