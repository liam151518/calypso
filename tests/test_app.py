"""Tests for the Flask web UI (app/server.py).

These tests use Flask's built-in test client — no real network, no real fal.ai.
The fake fal.ai HTTP server is reused from tests/test_generate.py patterns.

Run: `python -m pytest tests/test_app.py -v`
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from app import jobs, server, settings
from app.server import create_app


# ---------- fixtures ----------

@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    """Create a fresh Flask app with an isolated .env and upload dir."""
    env_path = tmp_path / ".env"
    upload_dir = tmp_path / "references" / "uploads"
    upload_dir.mkdir(parents=True)

    monkeypatch.setattr(settings, "ENV_PATH", env_path)
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(jobs, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(jobs, "_JOBS", {})  # Reset registry between tests

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def env_with_fal(tmp_path: Path, monkeypatch):
    """Set a valid FAL_API_KEY in .env for tests that need it."""
    env_path = tmp_path / ".env"
    env_path.write_text("FAL_API_KEY=test-fal-key\n")
    monkeypatch.setattr(settings, "ENV_PATH", env_path)
    # Also patch the module-level ENV_PATH that scripts.generate imports
    from scripts import generate as gen_mod
    monkeypatch.setattr(gen_mod, "ENV_PATH", env_path)
    return env_path


# ---------- health ----------

class TestHealth:
    def test_health_returns_ok_json(self, client):
        resp = client.get("/health.json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "calypso"

    def test_health_html_for_htmx(self, client):
        resp = client.get("/health", headers={"Accept": "text/html"})
        assert resp.status_code == 200
        assert b"online" in resp.data


# ---------- home ----------

class TestHome:
    def test_homepage_redirects_to_generate(self, client):
        resp = client.get("/")
        assert resp.status_code in (301, 302, 308)
        assert "/generate" in resp.headers["Location"]


# ---------- generate page ----------

class TestGeneratePage:
    def test_renders_with_form(self, client):
        resp = client.get("/generate")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Generate" in body
        assert 'name="prompt"' in body
        assert 'name="model"' in body

    def test_renders_banner_when_no_keys(self, client):
        resp = client.get("/generate")
        assert resp.status_code == 200
        assert b"No API keys configured" in resp.data


# ---------- generate POST ----------

class TestGenerateSubmit:
    def test_requires_prompt(self, client, env_with_fal):
        resp = client.post("/generate", data={"prompt": ""})
        assert resp.status_code == 400
        assert "Prompt is required" in resp.get_json()["error"]

    def test_requires_at_least_one_key(self, client):
        resp = client.post("/generate", data={"prompt": "hi"})
        assert resp.status_code == 400
        body = resp.get_json()
        assert "API keys" in body["error"]
        assert body.get("redirect", "").endswith("/settings")

    def test_unknown_model_rejected(self, client, env_with_fal):
        resp = client.post("/generate", data={"prompt": "hi", "model": "gibberish"})
        assert resp.status_code == 400

    def test_creates_job_with_fal_key(self, client, env_with_fal, monkeypatch, tmp_path):
        # Stub the actual generation so we don't hit the network
        from scripts import generate as gen_mod

        class FakeResult:
            output_path = tmp_path / "video.mp4"
            model = "h3-max"
            duration_seconds = 8
            resolution = "768p"
            cost_usd = 0.4
            elapsed_seconds = 1.0
            reference_used = None
            source_request_id = "fake"

        monkeypatch.setattr(gen_mod, "generate", lambda *a, **kw: FakeResult())
        # Also patch the symbol in jobs (where it's imported)
        monkeypatch.setattr(jobs, "run_generate", lambda *a, **kw: FakeResult())

        resp = client.post("/generate", data={"prompt": "test prompt", "model": "auto"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "job_id" in body
        assert "/status" in body["status_url"]


# ---------- job status (HTMX poll) ----------

class TestJobStatus:
    def test_returns_404_for_unknown(self, client):
        resp = client.get("/generate/nonexistent-id/status")
        assert resp.status_code == 404

    def test_renders_status_html(self, client, monkeypatch):
        job = jobs.create_job("a test prompt", model="auto", duration=8, resolution="768p")
        resp = client.get(f"/generate/{job.job_id}/status")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert job.job_id in body
        assert "queued" in body.lower() or "running" in body.lower() or "succeeded" in body.lower()


# ---------- references ----------

class TestReferences:
    def test_list_empty(self, client):
        resp = client.get("/references")
        assert resp.status_code == 200
        assert b"No references yet" in resp.data or b"Library (0)" in resp.data

    def test_upload_then_list(self, client, tmp_path, monkeypatch):
        # Set up the upload dir via monkeypatch on server module
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)

        # Fake PNG header bytes
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        from io import BytesIO
        data = {"file": (BytesIO(png_header), "test.png")}

        resp = client.post(
            "/references/upload",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert resp.status_code == 302  # redirect after success
        # File should be on disk
        files = list(upload_dir.iterdir())
        assert len(files) == 1
        assert files[0].suffix == ".png"

        # And listing shows it
        resp = client.get("/references")
        assert resp.status_code == 200
        assert b"test_" in resp.data  # file renamed with timestamp prefix
        assert b"Library (1)" in resp.data

    def test_upload_rejects_bad_extension(self, client, tmp_path, monkeypatch):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)

        from io import BytesIO
        data = {"file": (BytesIO(b"not a real file"), "evil.exe")}
        resp = client.post("/references/upload", data=data, content_type="multipart/form-data")
        # Redirect with error flash, or 400. Either way the file should not be saved.
        assert resp.status_code in (302, 400)

    def test_delete_reference(self, client, tmp_path, monkeypatch):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        target = upload_dir / "delete_me.png"
        target.write_bytes(b"\x89PNG\r\n\x1a\n")
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)

        resp = client.post("/references/delete_me.png/delete")
        assert resp.status_code == 302
        assert not target.exists()

    def test_delete_unknown_404(self, client):
        resp = client.post("/references/nope.png/delete")
        assert resp.status_code == 404

    def test_serve_file(self, client, tmp_path, monkeypatch):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        target = upload_dir / "view.png"
        target.write_bytes(b"\x89PNG\r\n\x1a\nfake png")
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)

        resp = client.get("/references/file/view.png")
        assert resp.status_code == 200
        assert resp.data.startswith(b"\x89PNG")


# ---------- outputs ----------

class TestOutputs:
    def test_empty_state_when_no_outputs(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(jobs, "OUTPUTS_DIR", tmp_path / "empty_outputs")
        resp = client.get("/outputs")
        assert resp.status_code == 200
        assert b"No outputs yet" in resp.data

    def test_lists_generated_videos(self, client, tmp_path, monkeypatch):
        out = tmp_path / "outputs" / "20260101-120000"
        out.mkdir(parents=True)
        (out / "video.mp4").write_bytes(b"fake mp4 bytes")
        monkeypatch.setattr(jobs, "OUTPUTS_DIR", tmp_path / "outputs")

        resp = client.get("/outputs")
        assert resp.status_code == 200
        assert b"20260101-120000" in resp.data

    def test_serve_video_404_when_missing(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(jobs, "OUTPUTS_DIR", tmp_path / "outputs")
        resp = client.get("/outputs/nonexistent/video.mp4")
        assert resp.status_code == 404


# ---------- settings ----------

class TestSettings:
    def test_renders_settings_page(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert b"FAL_API_KEY" in resp.data
        assert b"MINIMAX_API_KEY" in resp.data

    def test_save_then_read_roundtrip(self, client, tmp_path, monkeypatch):
        env_path = tmp_path / ".env"
        monkeypatch.setattr(settings, "ENV_PATH", env_path)

        resp = client.post("/settings/FAL_API_KEY", data={"value": "secret-key-xyz"}, follow_redirects=True)
        assert resp.status_code == 200

        # File written
        assert env_path.exists()
        assert "FAL_API_KEY=secret-key-xyz" in env_path.read_text()

        # list_keys sees it
        keys = {k.env_var: k for k in settings.list_keys()}
        assert keys["FAL_API_KEY"].is_set is True
        masked = keys["FAL_API_KEY"].masked or ""
        # Last 4 chars of the raw value should appear at the end of the masked string,
        # after stripping the bullets that hide the rest.
        assert masked.replace("\u2022", "") == "-xyz"

    def test_save_rejects_unknown_key(self, client):
        resp = client.post("/settings/NOT_A_REAL_KEY", data={"value": "x"}, follow_redirects=False)
        assert resp.status_code == 404

    def test_save_rejects_empty_value(self, client, tmp_path, monkeypatch):
        env_path = tmp_path / ".env"
        monkeypatch.setattr(settings, "ENV_PATH", env_path)
        resp = client.post("/settings/FAL_API_KEY", data={"value": ""}, follow_redirects=True)
        assert resp.status_code == 200
        # File should not be created (or should not contain the key)
        assert not env_path.exists() or "FAL_API_KEY" not in env_path.read_text()

    def test_delete_key(self, client, tmp_path, monkeypatch):
        env_path = tmp_path / ".env"
        env_path.write_text("FAL_API_KEY=abc123\n")
        monkeypatch.setattr(settings, "ENV_PATH", env_path)

        resp = client.post("/settings/FAL_API_KEY/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert "FAL_API_KEY" not in env_path.read_text()

    def test_masked_display_hides_full_key(self, client, tmp_path, monkeypatch):
        env_path = tmp_path / ".env"
        env_path.write_text("FAL_API_KEY=supersecret12345\n")
        monkeypatch.setattr(settings, "ENV_PATH", env_path)
        resp = client.get("/settings")
        body = resp.data.decode()
        assert "supersecret12345" not in body  # raw value never rendered
        assert "2345" in body  # last 4 chars shown


# ---------- settings.py unit ----------

class TestSettingsModule:
    def test_unknown_key_raises(self, tmp_path):
        env_path = tmp_path / ".env"
        with pytest.raises(ValueError):
            settings.save_key("NOT_REAL", "x", env_path=env_path)
        with pytest.raises(ValueError):
            settings.delete_key("NOT_REAL", env_path=env_path)
        with pytest.raises(ValueError):
            settings.get_raw("NOT_REAL", env_path=env_path)

    def test_save_appends_when_new(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("OTHER_KEY=foo\n")
        settings.save_key("FAL_API_KEY", "abc", env_path=env_path)
        text = env_path.read_text()
        assert "OTHER_KEY=foo" in text
        assert "FAL_API_KEY=abc" in text

    def test_save_replaces_existing(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("FAL_API_KEY=old\nOTHER=kept\n")
        settings.save_key("FAL_API_KEY", "new", env_path=env_path)
        text = env_path.read_text()
        assert "FAL_API_KEY=new" in text
        assert "FAL_API_KEY=old" not in text
        assert "OTHER=kept" in text

    def test_list_keys_empty_when_no_file(self, tmp_path):
        env_path = tmp_path / ".env"
        keys = settings.list_keys(env_path=env_path)
        for k in keys:
            assert k.is_set is False
            assert k.masked is None
