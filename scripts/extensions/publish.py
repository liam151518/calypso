#!/usr/bin/env python3
"""scripts/extensions/publish.py — Push a signed bundle to the marketplace
object store and notify the Calypso registry.

Usage:
    python3 publish.py path/to/extension.tar.gz \
        --tag v1.0.0 \
        --registry $CALYPSO_MARKETPLACE_REGISTRY

This script doesn't actually upload anything yet — it prints the action
it would take so CI can pick it up. The CI layer (or a future
`orbit push` hook) fills in the upload step.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make `scripts` importable when invoked as a sub-script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.extensions.signing import verify_bundle


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s).strip("-").lower() or "x"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle")
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--registry",
        default="https://marketplace.calypso.dev",
        help="Base URL of the marketplace registry",
    )
    args = parser.parse_args(argv)

    bundle = Path(args.bundle)
    if not bundle.exists():
        print(f"FAIL: bundle not found: {bundle}", file=sys.stderr)
        return 1
    try:
        manifest = verify_bundle(bundle)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: signature verification failed: {exc}", file=sys.stderr)
        return 1

    ext_id = manifest["id"]
    slug = _slug(ext_id)
    uploaded_path = (
        f"{args.registry.rstrip('/')}/v1/extensions/{slug}/versions/{args.tag}.tar.gz"
    )
    print(json.dumps({
        "action": "publish",
        "id": ext_id,
        "name": manifest["name"],
        "version": manifest["version"],
        "tag": args.tag,
        "permissions": manifest["permissions"],
        "checksum": manifest["checksum"],
        "upload_url": uploaded_path,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))