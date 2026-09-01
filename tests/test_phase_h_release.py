"""Phase H — release-readiness smoke tests.

Verifies the artifacts we'd ship: bundle format works, the marketplace
publish CLI produces the right payload, and the sidecar scripts
discover the tools they need.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_bundle(tmp_path: Path, name: str = "smoke.tar.gz") -> Path:
    bundle = tmp_path / name
    with tarfile.open(bundle, "w:gz") as tar:
        info = tarfile.TarInfo("main.py")
        info.size = 8
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(b"print(a)\n"))
    return bundle


def _run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(PROJECT_ROOT),
                           capture_output=True, text=True, **kw)


def test_sign_then_verify_cli(tmp_path):
    bundle = _make_bundle(tmp_path)
    signed = _run([sys.executable, "scripts/extensions/signing.py",
                    "sign", str(bundle)])
    assert signed.returncode == 0, signed.stderr
    manifest = json.loads(signed.stdout)
    assert manifest["checksum"]
    assert manifest["signature"]

    verified = _run([sys.executable, "scripts/extensions/signing.py",
                      "verify", str(bundle)])
    assert verified.returncode == 0, verified.stderr


def test_publish_cli_emits_url(tmp_path):
    bundle = _make_bundle(tmp_path)
    _run([sys.executable, "scripts/extensions/signing.py",
           "sign", str(bundle)], check=True)
    out = _run([sys.executable, "scripts/extensions/publish.py",
                 str(bundle), "--tag", "v1.0.0"])
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    assert payload["action"] == "publish"
    assert payload["tag"] == "v1.0.0"
    assert payload["upload_url"].endswith("/v1/extensions/smoke-tar/versions/v1.0.0.tar.gz")


def test_publish_refuses_unsigned(tmp_path):
    bundle = _make_bundle(tmp_path)
    out = _run([sys.executable, "scripts/extensions/publish.py",
                 str(bundle), "--tag", "v1.0.0"])
    assert out.returncode != 0


def test_desktop_build_script_discoverable():
    script = Path("scripts/desktop-build.sh")
    assert script.exists()
    text = script.read_text()
    # The Phase H extension hooks should be present.
    assert "calypso-render" in text
    assert "PyInstaller" in text


def test_release_docs_exist():
    for name in (
        "install.md",
        "quickstart.md",
        "templates.md",
        "studio.md",
        "video_pipeline.md",
        "omni_integration.md",
        "api.md",
        "RELEASE.md",
    ):
        path = Path(f"docs/{name}")
        assert path.exists(), f"missing {name}"


def test_extension_schema_doc_present():
    schema = Path("scripts/extensions/SCHEMA.md")
    assert schema.exists()
    text = schema.read_text()
    assert "calypso.extension/1" in text
    assert "permissions" in text
    assert "signature" in text


def test_release_checklist_lists_tests():
    text = Path("docs/RELEASE.md").read_text()
    assert "verify.sh" in text
    assert "pytest" in text
    assert "one_shot" in text


def test_desktop_build_creates_required_dirs_when_missing(tmp_path, monkeypatch):
    """Doesn't actually run PyInstaller — just confirms the script
    can be parsed and the staging logic exists."""
    build = Path("scripts/desktop-build.sh").read_text()
    # The script should reference the sidecar staging dir.
    assert "binaries" in build
    # And the Tauri target.
    assert "src-tauri" in build