"""Phase H — marketplace extension signing tests."""

from __future__ import annotations

import io
import json
import os
import stat
import tarfile
from pathlib import Path

import pytest

from scripts.extensions import signing as signing_mod


def _make_stub_bundle(tmp_path: Path, files: dict[str, bytes]) -> Path:
    """Create a tar.gz bundle with the given files."""
    bundle = tmp_path / "stub.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    return bundle


def test_sign_then_verify_roundtrip(tmp_path):
    bundle = _make_stub_bundle(tmp_path, {
        "main.py": b"print('hi')\n",
        "README.md": b"# stub",
    })
    manifest = signing_mod.sign_bundle(bundle)
    assert manifest["schema"] == signing_mod.SCHEMA
    assert manifest["checksum"]
    assert manifest["signature"]

    verified = signing_mod.verify_bundle(bundle)
    assert verified == manifest


def test_verify_detects_tampered_file(tmp_path):
    bundle = _make_stub_bundle(tmp_path, {"main.py": b"original"})
    signing_mod.sign_bundle(bundle)

    # Tamper with the bundle by re-packing with a different file.
    data = bundle.read_bytes()
    tar = tarfile.open(bundle, "r:gz")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as out:
        out.addfile(
            tarfile.TarInfo("main.py")._replace_chunks(b"tampered"),  # type: ignore[attr-defined]
            io.BytesIO(b"tampered"),
        ) if False else None  # placeholder

    # Easier tamper: rewrite the bundle with a single different file
    # but keep the manifest + signature from the signed bundle.
    buf2 = io.BytesIO()
    with tarfile.open(fileobj=buf2, mode="w:gz") as out:
        # Reuse the manifest + signature, add a tampered file.
        with tarfile.open(bundle, "r:gz") as src:
            for m in src.getmembers():
                f = src.extractfile(m)
                if f is not None:
                    payload = f.read()
                else:
                    payload = b""
                if m.name == "main.py":
                    payload = b"tampered"
                    m.size = len(payload)
                out.addfile(m, io.BytesIO(payload))
    bundle.write_bytes(buf2.getvalue())

    with pytest.raises(ValueError):
        signing_mod.verify_bundle(bundle)


def test_verify_detects_tampered_manifest(tmp_path):
    bundle = _make_stub_bundle(tmp_path, {"main.py": b"hi"})
    manifest = signing_mod.sign_bundle(bundle)

    # Open the bundle and rewrite the manifest with different text.
    buf = io.BytesIO()
    with tarfile.open(bundle, "r:gz") as src, \
            tarfile.open(fileobj=buf, mode="w:gz") as out:
        for m in src.getmembers():
            f = src.extractfile(m)
            payload = f.read() if f else b""
            if m.name == "manifest.json":
                tampered = dict(manifest)
                tampered["name"] = "Renamed"
                payload = signing_mod._canonical_manifest_bytes(tampered)
                m.size = len(payload)
            out.addfile(m, io.BytesIO(payload))
    bundle.write_bytes(buf.getvalue())

    with pytest.raises(ValueError):
        signing_mod.verify_bundle(bundle)


def test_sign_refuses_when_manifest_present(tmp_path):
    bundle = _make_stub_bundle(tmp_path, {
        "main.py": b"a",
        "manifest.json": b'{"old": true}',
    })
    with pytest.raises(ValueError):
        signing_mod.sign_bundle(bundle)


def test_verify_unknown_schema(tmp_path):
    bundle = _make_stub_bundle(tmp_path, {"main.py": b"a"})
    # Sign first to add a real manifest.
    signing_mod.sign_bundle(bundle)
    # Now patch the schema in-place (bypass checksum/signature — should
    # still fail because we check schema first).
    buf = io.BytesIO()
    with tarfile.open(bundle, "r:gz") as src, \
            tarfile.open(fileobj=buf, mode="w:gz") as out:
        for m in src.getmembers():
            f = src.extractfile(m)
            payload = f.read() if f else b""
            if m.name == "manifest.json":
                obj = json.loads(payload)
                obj["schema"] = "calypso.extension/99"
                payload = signing_mod._canonical_manifest_bytes(obj)
                m.size = len(payload)
            out.addfile(m, io.BytesIO(payload))
    bundle.write_bytes(buf.getvalue())

    with pytest.raises(ValueError):
        signing_mod.verify_bundle(bundle)


def test_sign_with_empty_bundle(tmp_path):
    bundle = _make_stub_bundle(tmp_path, {"main.py": b""})
    manifest = signing_mod.sign_bundle(bundle)
    assert manifest["checksum"]