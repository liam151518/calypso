"""app/extensions/signing.py. HMAC-SHA-256 signing utilities for the CLI.

The marketplace uses this to sign a packaged extension directory:

    python -m app.extensions.signing sign <ext_dir>

The resulting signature is appended to `calypso-extension.json` so users
can verify the author. The signing key is provided via the
CALYPSO_EXTENSION_SIGNING_KEY environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .manifest import (
    ExtensionManifest,
    compute_checksum,
    parse_manifest,
    sign_manifest,
)


def cmd_sign(ext_dir: Path, secret: str) -> int:
    manifest_path = ext_dir / "calypso-extension.json"
    m = parse_manifest(manifest_path)
    m.checksum = compute_checksum(ext_dir)
    m.signature = sign_manifest(m, secret)
    payload = {
        "id": m.id,
        "version": m.version,
        "type": m.type,
        "name": m.name,
        "author": m.author,
        "description": m.description,
        "homepage": m.homepage,
        "license": m.license,
        "checksum": m.checksum,
        "signature": m.signature,
        **m.extra,
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"signed {m.id}@{m.version} → {m.signature[:16]}…")
    return 0


def cmd_verify(ext_dir: Path, secret: str) -> int:
    manifest_path = ext_dir / "calypso-extension.json"
    m = parse_manifest(manifest_path)
    expected = compute_checksum(ext_dir)
    if m.checksum and m.checksum != expected:
        print(f"CHECKSUM MISMATCH: {m.checksum} vs {expected}")
        return 1
    if not m.signature:
        print("no signature present")
        return 1
    if sign_manifest(m, secret) != m.signature:
        print("BAD SIGNATURE")
        return 1
    print(f"OK {m.id}@{m.version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="calypso-ext")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sign_p = sub.add_parser("sign", help="sign an extension directory")
    sign_p.add_argument("ext_dir", type=Path)

    verify_p = sub.add_parser("verify", help="verify an extension directory")
    verify_p.add_argument("ext_dir", type=Path)

    args = parser.parse_args(argv)
    secret = os.environ.get("CALYPSO_EXTENSION_SIGNING_KEY", "").strip()
    if not secret:
        print("CALYPSO_EXTENSION_SIGNING_KEY is not set", file=sys.stderr)
        return 2
    if args.cmd == "sign":
        return cmd_sign(args.ext_dir, secret)
    if args.cmd == "verify":
        return cmd_verify(args.ext_dir, secret)
    return 0


if __name__ == "__main__":
    sys.exit(main())
