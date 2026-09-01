"""Tests for scripts/validate_accounts.py.

Run: `python -m pytest tests/test_validate_accounts.py -v`

These tests verify the validator's behavior without making real API calls.
they use monkeypatching and fake HTTP servers.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts import validate_accounts
from scripts.validate_accounts import Check, check_http


# ---------- helpers ----------

class FakeAPI(BaseHTTPRequestHandler):
    """Minimal API server that echoes back what was sent."""

    expected_status = 200
    response_body: dict = {"ok": True}

    def log_message(self, *_args, **_kwargs):
        pass

    def _route(self):
        method = self.command
        path = self.path
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode() if length > 0 else ""
        # Capture
        type(self).last_request = {
            "method": method,
            "path": path,
            "headers": dict(self.headers),
            "body": body,
        }
        self.send_response(type(self).expected_status)
        self.send_header("Content-Type", "application/json")
        payload = json.dumps(type(self).response_body).encode()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        self._route()

    def do_POST(self):  # noqa: N802
        self._route()

    last_request: dict | None = None
    response_body: dict = {"ok": True, "id": "fake-user", "data": {"id": "fake-id"}, "user_id": "u1"}


@pytest.fixture(scope="module")
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), FakeAPI)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()


@pytest.fixture(autouse=True)
def reset_fake():
    FakeAPI.expected_status = 200
    FakeAPI.response_body = {"ok": True, "id": "fake-user", "data": {"id": "fake-id"}, "user_id": "u1"}
    FakeAPI.last_request = None
    yield


# ---------- check_http ----------

class TestCheckHttp:
    def test_returns_failure_when_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        result = check_http(name="test", env_var="MISSING_VAR", url="http://nowhere")
        assert result.ok is False
        assert "not set" in result.detail

    def test_returns_success_with_correct_keys(self, fake_server, monkeypatch):
        host, port = fake_server
        monkeypatch.setenv("MY_TOKEN", "abc123")
        result = check_http(
            name="test",
            env_var="MY_TOKEN",
            url=f"http://{host}:{port}/test",
            expect_json_keys=["ok", "id"],
            timeout=2.0,
        )
        assert result.ok is True

    def test_returns_failure_when_keys_missing(self, fake_server, monkeypatch):
        host, port = fake_server
        monkeypatch.setenv("MY_TOKEN", "abc123")
        FakeAPI.response_body = {"ok": True}  # missing "id"
        result = check_http(
            name="test",
            env_var="MY_TOKEN",
            url=f"http://{host}:{port}/test",
            expect_json_keys=["ok", "id"],
            timeout=2.0,
        )
        assert result.ok is False

    def test_returns_failure_on_http_error(self, fake_server, monkeypatch):
        host, port = fake_server
        monkeypatch.setenv("MY_TOKEN", "abc123")
        FakeAPI.expected_status = 401
        FakeAPI.response_body = {"error": "bad token"}
        result = check_http(
            name="test",
            env_var="MY_TOKEN",
            url=f"http://{host}:{port}/test",
            timeout=2.0,
        )
        assert result.ok is False
        assert "401" in result.detail

    def test_sends_bearer_token_when_var_name_suggests_it(self, fake_server, monkeypatch):
        host, port = fake_server
        monkeypatch.setenv("MY_BEARER", "xyz")
        check_http(
            name="test",
            env_var="MY_BEARER",
            url=f"http://{host}:{port}/test",
            timeout=2.0,
        )
        assert FakeAPI.last_request is not None
        assert FakeAPI.last_request["headers"].get("Authorization") == "Bearer xyz"


# ---------- load_env_file ----------

class TestLoadEnvFile:
    def test_loads_simple_kv(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("TEST_VAR_1", raising=False)
        (tmp_path / ".env").write_text("TEST_VAR_1=hello\n")
        validate_accounts.load_env_file(tmp_path / ".env")
        import os
        assert os.environ.get("TEST_VAR_1") == "hello"

    def test_skips_comments(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("TEST_VAR_2", raising=False)
        (tmp_path / ".env").write_text("# this is a comment\nTEST_VAR_2=ok\n")
        validate_accounts.load_env_file(tmp_path / ".env")
        import os
        assert os.environ.get("TEST_VAR_2") == "ok"

    def test_does_not_override_existing(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("TEST_VAR_3", "preset")
        (tmp_path / ".env").write_text("TEST_VAR_3=fromfile\n")
        validate_accounts.load_env_file(tmp_path / ".env")
        import os
        assert os.environ.get("TEST_VAR_3") == "preset"

    def test_handles_missing_file(self, tmp_path: Path):
        # Should not raise
        validate_accounts.load_env_file(tmp_path / "nope")


# ---------- CLI ----------

class TestCLI:
    def test_main_returns_0_when_all_fail_and_not_strict(self, monkeypatch, capsys):
        # Patch CHECKS to use simple stubs that always fail
        def always_fail():
            return Check(name="stub", env_var="STUB", ok=False, detail="nope")

        monkeypatch.setattr(validate_accounts, "CHECKS", [always_fail])
        monkeypatch.setattr("sys.argv", ["validate_accounts.py"])
        rc = validate_accounts.main()
        assert rc == 0

    def test_main_returns_1_when_strict(self, monkeypatch):
        def always_fail():
            return Check(name="stub", env_var="STUB", ok=False, detail="nope")

        monkeypatch.setattr(validate_accounts, "CHECKS", [always_fail])
        monkeypatch.setattr("sys.argv", ["validate_accounts.py", "--strict"])
        rc = validate_accounts.main()
        assert rc == 1

    def test_only_filter(self, monkeypatch):
        def check_minimax_stub():
            return Check(name="minimax", env_var="X1", ok=False, detail="no")

        def check_fal_stub():
            return Check(name="fal", env_var="X2", ok=False, detail="no")

        monkeypatch.setattr(validate_accounts, "CHECKS", [check_minimax_stub, check_fal_stub])
        monkeypatch.setattr("sys.argv", ["validate_accounts.py", "--only", "minimax", "--strict"])
        rc = validate_accounts.main()
        assert rc == 1
