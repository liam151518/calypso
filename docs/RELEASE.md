# Calypso Release Process

Phase E deliverable. Run from the repo root.

## One-time setup

```bash
# 1. Tag the release.
git tag -a v0.1.0 -m "Calypso v0.1.0"
git push origin v0.1.0

# 2. The GitHub Actions workflow `.github/workflows/release.yml` will:
#    - run pytest, vitest, build the SPA,
#    - build the Tauri installers via `scripts/desktop-build.sh`,
#    - attach them to the GitHub release,
#    - publish the marketplace catalog to docs/marketplace/index.json.
```

## Local release

```bash
./scripts/desktop-build.sh         # produces installers + sidecar
python -m app.extensions.signing sign <ext_dir>   # sign extensions
```

## Channels

| Channel | Format | Sign | Hosting |
|---------|--------|------|---------|
| macOS   | `.dmg` | Developer ID | GitHub Releases |
| Windows | `.exe` (NSIS) + `.msi` | Signtool | GitHub Releases |
| Linux   | `.AppImage` + `.deb` | GPG | GitHub Releases |
| Docker  | OCI image | Cosign | ghcr.io/calypso/calypso |
| Self-host | `docker compose` | n/a | user-provided |

## Public marketplace

The marketplace lives at `docs/marketplace/` and is published to GitHub
Pages on every release. Adding a community extension:

1. Fork the repo.
2. Add your extension under `app/extensions/builtin/<your-id>/`.
3. Submit a PR. CI will lint, sign, and add it to the catalog.
