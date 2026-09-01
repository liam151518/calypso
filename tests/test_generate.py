"""Tests for scripts/generate.py. The unified CLI entry point.

Run: `python -m pytest tests/test_generate.py -v`
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts import generate
from scripts.generate import GenerateResult, load_env, pick_model, resolve_reference


# ---------- env loading ----------

class TestLoadEnv:
    def test_loads_simple_key_value(self, tmp_path: Path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        monkeypatch.setattr(generate, "ENV_PATH", env_file)
        env = load_env()
        assert env["FOO"] == "bar"
        assert env["BAZ"] == "qux"

    def test_strips_quotes(self, tmp_path: Path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text('FOO="bar"\nBAZ=\'qux\'\n')
        monkeypatch.setattr(generate, "ENV_PATH", env_file)
        env = load_env()
        assert env["FOO"] == "bar"
        assert env["BAZ"] == "qux"

    def test_skips_comments_and_blank_lines(self, tmp_path: Path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("\n# comment\n\nFOO=bar\n")
        monkeypatch.setattr(generate, "ENV_PATH", env_file)
        env = load_env()
        assert env == {"FOO": "bar"}

    def test_missing_file_returns_empty(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(generate, "ENV_PATH", tmp_path / "missing.env")
        assert load_env() == {}


# ---------- model routing ----------

class TestPickModel:
    def test_explicit_model_returned_as_is(self):
        assert pick_model("h3-cloud", True, True) == "h3-cloud"
        assert pick_model("kling", True, True) == "kling"
        assert pick_model("h3-max", True, True) == "h3-max"

    def test_auto_prefers_h3_cloud_when_available(self):
        assert pick_model("auto", has_h3_cloud=True, has_fal=True) == "h3-cloud"

    def test_auto_falls_back_to_fal_when_no_h3(self):
        assert pick_model("auto", has_h3_cloud=False, has_fal=True) == "h3-max"

    def test_auto_exits_when_no_keys(self, capsys):
        with pytest.raises(SystemExit):
            pick_model("auto", has_h3_cloud=False, has_fal=False)
        captured = capsys.readouterr()
        assert "no API keys" in captured.err


# ---------- reference resolution ----------

class TestResolveReference:
    def test_explicit_path_returned(self, tmp_path: Path):
        img = tmp_path / "ref.png"
        img.write_bytes(b"fake png data")
        path, url = resolve_reference(str(img))
        assert path == img
        assert url is None

    def test_explicit_missing_path_exits(self, tmp_path: Path, capsys):
        with pytest.raises(SystemExit):
            resolve_reference(str(tmp_path / "nope.png"))
        assert "reference not found" in capsys.readouterr().err

    def test_no_reference_no_vault_returns_none(self, tmp_path: Path, monkeypatch):
        from scripts import reference_picker
        # Point READY_DIR at an empty dir so load_references() returns []
        empty_ready = tmp_path / "ready"
        empty_ready.mkdir()
        monkeypatch.setattr(reference_picker, "READY_DIR", empty_ready)
        path, url = resolve_reference(None)
        assert path is None
        assert url is None


# ---------- end-to-end with fake API server ----------

class FakeFalAI(BaseHTTPRequestHandler):
    last_body: dict | None = None
    last_path: str | None = None

    def log_message(self, *_args, **_kwargs):
        pass

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body_raw = self.rfile.read(length).decode() if length > 0 else "{}"
        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError:
            body = {}

        type(self).last_body = body
        type(self).last_path = self.path

        # submission
        if "/requests/" not in self.path and not self.path.endswith("/status"):
            self._json(200, {
                "request_id": "req-123",
                "status_url": f"{self.path}/status",
            })
        else:
            self._json(200, {"status": "COMPLETED"})

    def do_GET(self):  # noqa: N802
        # status polling
        if "/status" in self.path:
            self._json(200, {"status": "COMPLETED"})
        elif "/requests/" in self.path:
            self._json(200, {"video": {"url": "http://example.invalid/video.mp4"}})
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def fake_fal_server():
    server = HTTPServer(("127.0.0.1", 0), FakeFalAI)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()


@pytest.fixture(autouse=True)
def reset_fake():
    FakeFalAI.last_body = None
    FakeFalAI.last_path = None


@pytest.fixture
def env_with_fal_key(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FAL_API_KEY=test-key-from-env\n")
    monkeypatch.setattr(generate, "ENV_PATH", env_file)


class TestEndToEndFalAI:
    def test_routes_to_h3_max_when_only_fal_key(
        self, env_with_fal_key, tmp_path: Path, monkeypatch, fake_fal_server, capsys
    ):
        host, port = fake_fal_server

        # Stub out urllib.request.urlretrieve so we don't actually fetch
        def fake_urlretrieve(url, path):
            Path(path).write_bytes(b"fake video bytes")
        monkeypatch.setattr(generate.urllib.request, "urlretrieve", fake_urlretrieve)

        # Stub the fal.ai base URL so the test doesn't hit the real API
        monkeypatch.setattr(generate.FalAIClient, "BASE_URL", f"http://{host}:{port}")
        monkeypatch.setattr(generate.FalAIClient, "SYNC_URL", f"http://{host}:{port}")

        out_dir = tmp_path / "out"
        result = generate.generate(
            "test prompt damascus cabinet",
            model="auto",
            duration=8,
            resolution="768p",
            output_dir=out_dir,
        )

        assert result.model == "h3-max"
        assert result.output_path.exists()
        assert result.output_path.read_bytes() == b"fake video bytes"
        assert result.cost_usd == pytest.approx(0.4, rel=0.1)  # 0.05/s * 8s
        assert result.reference_used is None

        # Submission went to the right model endpoint
        assert "/minimax/h3-max" in (FakeFalAI.last_path or "")

    def test_explicit_kling_routes_to_kling(
        self, env_with_fal_key, tmp_path: Path, monkeypatch, fake_fal_server
    ):
        host, port = fake_fal_server

        def fake_urlretrieve(url, path):
            Path(path).write_bytes(b"kling bytes")
        monkeypatch.setattr(generate.urllib.request, "urlretrieve", fake_urlretrieve)
        monkeypatch.setattr(generate.FalAIClient, "BASE_URL", f"http://{host}:{port}")
        monkeypatch.setattr(generate.FalAIClient, "SYNC_URL", f"http://{host}:{port}")

        result = generate.generate(
            "cinematic hero shot",
            model="kling",
            duration=8,
            resolution="1080p",
            output_dir=tmp_path / "out",
        )
        assert result.model == "kling"
        assert "/kling-video/v2.6/pro" in (FakeFalAI.last_path or "")
        assert result.cost_usd == pytest.approx(0.80, rel=0.1)  # 0.10/s * 8s

    def test_dry_run_doesnt_call_api(
        self, env_with_fal_key, tmp_path: Path, monkeypatch, fake_fal_server, capsys
    ):
        host, port = fake_fal_server
        called = {"count": 0}
        original_post = FakeFalAI.do_POST

        def counting_post(self):
            called["count"] += 1
            return original_post(self)
        monkeypatch.setattr(FakeFalAI, "do_POST", counting_post)
        monkeypatch.setattr(generate.FalAIClient, "BASE_URL", f"http://{host}:{port}")

        result = generate.generate(
            "dry run",
            model="auto",
            dry_run=True,
            output_dir=tmp_path / "out",
        )
        # In dry-run mode we don't actually hit the API
        assert result.cost_usd == 0.0
        assert "[dry-run]" in capsys.readouterr().out


class TestCLI:
    def test_check_keys(self, tmp_path: Path, monkeypatch, capsys):
        env_file = tmp_path / ".env"
        env_file.write_text("FAL_API_KEY=set-key\n")
        monkeypatch.setattr(generate, "ENV_PATH", env_file)
        monkeypatch.setattr("sys.argv", ["generate.py", "--check-keys"])
        rc = generate._cli()
        assert rc == 0
        out = capsys.readouterr().out
        assert "FAL_API_KEY:      set" in out
        assert "MINIMAX_API_KEY:  MISSING" in out

    def test_no_keys_exits(self, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr(generate, "ENV_PATH", tmp_path / "missing.env")
        monkeypatch.setattr("sys.argv", ["generate.py", "a prompt"])
        with pytest.raises(SystemExit) as exc_info:
            generate._cli()
        # load_env returns empty -> pick_model exits -> SystemExit(2)
        assert exc_info.value.code == 2
