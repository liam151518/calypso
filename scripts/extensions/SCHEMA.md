# Extension manifest schema (v1)

Every marketplace extension ships a `manifest.json` at its root. The
runner uses the manifest to load code + grant permissions.

```json
{
  "schema": "calypso.extension/1",
  "id": "com.example.first-extension",
  "name": "First Extension",
  "version": "1.0.0",
  "vendor": "Example Co.",
  "description": "Adds brand voice presets to the Studio Pro picker.",
  "permissions": ["studio_pro:read", "studio_pro:write", "outputs:read"],
  "entry": "main.py",
  "checksum_algo": "sha256",
  "checksum": "abcdef...",
  "signature_algo": "hmac-sha256",
  "signature": "..base64.."
}
```

## Fields

| Field | Required | Description |
|-------|----------|-------------|
| `schema` | yes | Must be `calypso.extension/1` |
| `id` | yes | Reverse-DNS unique id |
| `name` | yes | Display name |
| `version` | yes | semver |
| `vendor` | no | Display name of the publisher |
| `description` | no | Plain-text description (<= 400 chars) |
| `permissions` | yes | List of permission strings |
| `entry` | yes | Relative path to the entrypoint module inside the bundle |
| `checksum_algo` | yes | Currently `sha256` |
| `checksum` | yes | Hex digest of the bundle contents minus the manifest + signature file |
| `signature_algo` | yes | `hmac-sha256` |
| `signature` | yes | HMAC of the manifest bytes (canonical JSON), keyed by `calypso_signing` |

## Permissions

| Scope | Grants |
|-------|--------|
| `studio_pro:read` | read Studio Pro runs and agent logs |
| `studio_pro:write` | create suggestions, accept, schedule |
| `outputs:read` | read `outputs` rows |
| `outputs:write` | publish outputs to platforms |
| `marketing:read` / `marketing:write` | contacts / campaigns |
| `automation:write` | install automation rules |
| `clipboard` | use system clipboard for the Studio Pro clipboard importer |

Anything not listed is denied at boot.

## Verification

```bash
python3 scripts/extensions/signing.py verify my-bundle.tar.gz
```

Exits 0 when the signature + checksum are valid. Returns the parsed
manifest on stdout.