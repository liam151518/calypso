#!/usr/bin/env python3
"""scripts/extensions/signing.py — HMAC-SHA256 verifier + signer for
marketplace extension bundles.

Usage:
    python3 signing.py sign path/to/extension.tar.gz     # write manifest.json in-place
    python3 signing.py verify path/to/extension.tar.gz   # exit 0 if signature is valid
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import io
import json
import os
import sys
import tarfile
from pathlib import Path

SIGNATURE_ALGO = "hmac-sha256"
CHECKSUM_ALGO = "sha256"
SCHEMA = "calypso.extension/1"
SENTINEL_UNSIGNED = "__UNSIGNED__"

# Names of files excluded from the checksum (we sign the rest of the
# bundle's contents byte-for-byte, including other metadata).
EXCLUDED_FROM_CHECKSUM = {"manifest.json", "signature.b64"}


def _read_key() -> bytes:
    key = os.environ.get("CALYPSO_SIGNING_KEY")
    if not key:
        # Dev fallback so the verifier doesn't crash out of the box.
        key = "dev-only-calypso-extension-signing-key"
    return key.encode("utf-8")


def _canonical_manifest_bytes(manifest: dict) -> bytes:
    """Stable JSON encoding used for signing (sort keys, no spaces)."""
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _bundle_digest(bundle: tarfile.TarFile) -> str:
    h = hashlib.sha256()
    for member in sorted(bundle.getmembers(), key=lambda m: m.name):
        if member.name in EXCLUDED_FROM_CHECKSUM:
            continue
        f = bundle.extractfile(member)
        if f is None:
            # Directory entry — digest the path + mode so two
            # archives with the same files but different directory
            # entries diverge.
            h.update(f"DIR:{member.name}:{oct(member.mode)}".encode())
            continue
        h.update(f"FILE:{member.name}:{oct(member.mode)}:".encode())
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sign_bundle(bundle_path: Path) -> dict:
    """Compute + write manifest.json + signature.b64 in-place.

    The HMAC is taken over the canonical bytes of the manifest with
    the `signature` field set to a constant sentinel (`__UNSIGNED__`).
    The verifier reconstructs the same canonical form before recomputing
    the HMAC — this avoids the self-signing chicken-and-egg problem.
    """
    import base64
    with tarfile.open(bundle_path, "r:gz") as tar:
        if "manifest.json" in tar.getnames():
            raise ValueError(
                "bundle already has a manifest.json — refusing to overwrite"
            )
        digest = _bundle_digest(tar)

    manifest = {
        "schema": SCHEMA,
        "id": bundle_path.stem,  # placeholder; authors edit before repacking
        "name": bundle_path.stem,
        "version": "0.0.1",
        "permissions": [],
        "entry": "main.py",
        "checksum_algo": CHECKSUM_ALGO,
        "checksum": digest,
        "signature_algo": SIGNATURE_ALGO,
        "signature": SENTINEL_UNSIGNED,  # replaced after HMAC computation
    }
    payload = _canonical_manifest_bytes(manifest)
    sig = hmac.new(_read_key(), payload, hashlib.sha256).digest()
    sig_b64 = base64.b64encode(sig).decode("ascii")
    manifest["signature"] = sig_b64

    # Rewrite the bundle by re-creating it with manifest.json +
    # signature.b64 injected at the top.
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as out, \
            tarfile.open(bundle_path, "r:gz") as src:
        # Inject the signature file first so it sorts before user files.
        sig_bytes = base64.b64decode(manifest["signature"])
        siginfo = tarfile.TarInfo("signature.b64")
        siginfo.size = len(sig_bytes)
        siginfo.mode = 0o644
        out.addfile(siginfo, io.BytesIO(sig_bytes))

        for member in src.getmembers():
            if member.name == "signature.b64":
                continue
            extracted = src.extractfile(member)
            if extracted is None:
                out.addfile(member)
            else:
                data = extracted.read()
                member.size = len(data)
                out.addfile(member, io.BytesIO(data))

        manifest_bytes = _canonical_manifest_bytes(manifest)
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest_bytes)
        manifest_info.mode = 0o644
        out.addfile(manifest_info, io.BytesIO(manifest_bytes))

    bundle_path.write_bytes(buf.getvalue())
    return manifest


def verify_bundle(bundle_path: Path) -> dict:
    """Verify signature + checksum. Returns parsed manifest on success."""
    with tarfile.open(bundle_path, "r:gz") as tar:
        manifest_member = tar.getmember("manifest.json")
        sig_member = tar.getmember("signature.b64")
        manifest_bytes = tar.extractfile(manifest_member).read()
        sig_bytes = tar.extractfile(sig_member).read()

    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError(f"unsupported schema {manifest.get('schema')!r}")
    # Replace the signature with the sentinel so the canonical bytes
    # used for HMAC match the ones we signed.
    manifest_for_sig = dict(manifest)
    manifest_for_sig["signature"] = SENTINEL_UNSIGNED
    expected_sig = hmac.new(
        _read_key(),
        _canonical_manifest_bytes(manifest_for_sig),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected_sig, sig_bytes):
        raise ValueError(
            "signature mismatch — bundle has been tampered with"
        )

    with tarfile.open(bundle_path, "r:gz") as tar:
        actual_checksum = _bundle_digest(tar)
    if actual_checksum != manifest["checksum"]:
        raise ValueError(
            f"checksum mismatch ({actual_checksum} != {manifest['checksum']})"
        )
    return manifest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign")
    s.add_argument("bundle")
    v = sub.add_parser("verify")
    v.add_argument("bundle")
    args = parser.parse_args(argv)

    if args.cmd == "sign":
        manifest = sign_bundle(Path(args.bundle))
        json.dump(manifest, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "verify":
        try:
            manifest = verify_bundle(Path(args.bundle))
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        json.dump(manifest, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))