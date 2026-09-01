"""tests/test_extensions.py. Pytest suite for the Phase D plugin marketplace."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app import extensions as ext_mod
from app.extensions import loader
from app.extensions.manifest import (
    compute_checksum,
    parse_manifest,
    sign_manifest,
    verify_signature,
)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    loader.reset_for_tests()
    yield
    loader.reset_for_tests()


def _write_ext(ext_dir: Path, *, id_: str = "demo", body: str = "",
               manifest_extra: dict | None = None) -> Path:
    ext_dir.mkdir(parents=True, exist_ok=True)
    m = {
        "id": id_,
        "version": "0.1.0",
        "type": "channel",
        "name": "Demo",
        "description": body,
        "license": "MIT",
    }
    if manifest_extra:
        m.update(manifest_extra)
    (ext_dir / "calypso-extension.json").write_text(json.dumps(m))
    if body:
        (ext_dir / "extension.py").write_text(body)
    return ext_dir


def test_parse_manifest_minimal(tmp_path):
    d = _write_ext(tmp_path / "demo")
    m = parse_manifest(d / "calypso-extension.json")
    assert m.id == "demo"
    assert m.type == "channel"


def test_parse_manifest_requires_id(tmp_path):
    p = tmp_path / "calypso-extension.json"
    p.write_text(json.dumps({"version": "0.1", "type": "channel", "name": "x"}))
    from app.extensions.manifest import ManifestError
    with pytest.raises(ManifestError):
        parse_manifest(p)


def test_parse_manifest_rejects_unknown_type(tmp_path):
    p = tmp_path / "calypso-extension.json"
    p.write_text(json.dumps({
        "id": "x", "version": "0.1", "type": "alien", "name": "x"
    }))
    from app.extensions.manifest import ManifestError
    with pytest.raises(ManifestError):
        parse_manifest(p)


def test_parse_manifest_rejects_path_traversal_id(tmp_path):
    p = tmp_path / "calypso-extension.json"
    p.write_text(json.dumps({
        "id": "../escape", "version": "0.1", "type": "channel", "name": "x"
    }))
    from app.extensions.manifest import ManifestError
    with pytest.raises(ManifestError):
        parse_manifest(p)


def test_compute_checksum_stable(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    s1 = compute_checksum(tmp_path)
    s2 = compute_checksum(tmp_path)
    assert s1 == s2
    assert len(s1) == 64  # sha256 hex


def test_compute_checksum_changes_when_file_changes(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    s1 = compute_checksum(tmp_path)
    (tmp_path / "a.txt").write_text("world")
    s2 = compute_checksum(tmp_path)
    assert s1 != s2


def test_sign_and_verify_roundtrip(tmp_path):
    d = _write_ext(tmp_path / "x")
    m = parse_manifest(d / "calypso-extension.json")
    m.checksum = compute_checksum(d)
    m.signature = sign_manifest(m, "secret-1")
    assert verify_signature(m, "secret-1") is True
    assert verify_signature(m, "wrong-secret") is False


def test_discover_finds_builtins():
    found = loader.discover()
    assert any(m.id == "calypso-logger-channel" for m in found)
    assert any(m.id == "calypso-csv-importer" for m in found)


def test_enable_disable_and_persist(tmp_path, monkeypatch):
    state_file = tmp_path / "extensions.json"
    monkeypatch.setattr(loader._REGISTRY, "state_path", state_file, raising=False)
    # Force a known state path
    monkeypatch.setenv("CALYPSO_HOME", str(tmp_path))
    loader.discover()
    assert loader.enable("calypso-logger-channel") is True
    assert loader.is_enabled("calypso-logger-channel") is True
    # state persisted
    assert state_file.exists()
    state = json.loads(state_file.read_text())
    assert "calypso-logger-channel" in state["enabled"]
    loader.disable("calypso-logger-channel")
    state = json.loads(state_file.read_text())
    assert "calypso-logger-channel" not in state["enabled"]


def test_enable_unknown_returns_false(tmp_path):
    state_file = tmp_path / "extensions.json"
    tmp_path.mkdir(parents=True, exist_ok=True)
    loader.discover()
    assert loader.enable("does-not-exist") is False


def test_load_builtin_extensions_registers_handlers():
    loader.load_builtin_extensions()
    hooks = loader.registry().hook("channel.logger")
    assert hooks, "logger channel should be registered"
    result = hooks[-1]({"to": "test", "body": "hi"})
    assert result["ok"] is True


def test_list_extensions_includes_builtins():
    loader.load_builtin_extensions()
    items = loader.list_extensions()
    ids = {i["id"] for i in items}
    assert "calypso-logger-channel" in ids
    assert "calypso-csv-importer" in ids
    # both auto-enabled
    enabled = {i["id"] for i in items if i["enabled"]}
    assert "calypso-logger-channel" in enabled
    assert "calypso-csv-importer" in enabled


def test_call_channel_fans_out(tmp_path):
    loader.load_builtin_extensions()
    results = ext_mod.call_channel("logger", {"to": "demo", "body": "hi"})
    assert results
    assert results[0]["ok"] is True


def test_call_form_capture_no_handler():
    """If no handler accepts, returns an error dict. Never raises."""
    res = ext_mod.call_form_capture("nope", {"email": "x@x"})
    assert res["ok"] is False


def test_call_import_csv(tmp_path):
    loader.load_builtin_extensions()
    csv_path = tmp_path / "contacts.csv"
    csv_path.write_text("email,name\nfoo@example.com,Foo\n")
    res = ext_mod.call_import("csv.contacts", csv_path, {})
    assert res["ok"] is True
    assert res["count"] == 1
    assert res["rows"][0]["email"] == "foo@example.com"


def test_extension_with_bad_checksum_is_skipped(tmp_path):
    _write_ext(tmp_path / "x", id_="bad",
               manifest_extra={"checksum": "deadbeef"})
    # explicit scan of tmp_path
    found = loader.discover(tmp_path)
    # the manifest's checksum doesn't match the actual file. Should be skipped.
    assert not any(m.id == "bad" for m in found)


def test_signing_cli_sign_and_verify(tmp_path, monkeypatch, capsys):
    """End-to-end via the CLI module."""
    from app.extensions import signing
    d = _write_ext(tmp_path / "demo")
    monkeypatch.setenv("CALYPSO_EXTENSION_SIGNING_KEY", "topsecret")
    rc = signing.cmd_sign(d, "topsecret")
    assert rc == 0
    data = json.loads((d / "calypso-extension.json").read_text())
    assert data["signature"]
    assert data["checksum"]
    rc = signing.cmd_verify(d, "topsecret")
    assert rc == 0
    rc = signing.cmd_verify(d, "wrong")
    assert rc == 1
