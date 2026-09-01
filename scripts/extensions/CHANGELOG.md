# Extension marketplace tooling

`scripts/extensions/` contains the marketplace tooling for first-party
+ community extensions.

| File | Purpose |
|------|---------|
| `SCHEMA.md` | Manifest format spec |
| `signing.py` | HMAC-SHA256 sign + verify |
| `publish.py` | Build a publish manifest + upload URL |

## Workflow

1. Bundle the extension into a tar.gz (manifest.json at root).
2. Run `python3 scripts/extensions/signing.py sign bundle.tar.gz` to
   inject the signed manifest + signature.
3. Run `python3 scripts/extensions/publish.py bundle.tar.gz --tag vX.Y.Z`
   to print the upload URL.
4. CI uploads the signed bundle to the URL and posts a webhook to the
   registry so it knows there's a new version.

## Verifying third-party bundles

```bash
CALYPSO_SIGNING_KEY=$YOUR_SECRET \
    python3 scripts/extensions/signing.py verify third-party.tar.gz
```

Exits 0 when the signature + checksum are valid.

## Permissions

The manifest's `permissions` list is enforced at boot by the runner.
See `SCHEMA.md#permissions` for the full list.