"""Tests for the Flask web UI (app/server.py).

These tests use Flask's built-in test client. No real network, no real fal.ai.
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
    """Create a fresh Flask app with an isolated .env, upload dir, and DB."""
    env_path = tmp_path / ".env"
    upload_dir = tmp_path / "references" / "uploads"
    upload_dir.mkdir(parents=True)

    # Point the structured-data DB at a per-test file so we never inherit
    # state from the on-disk `.calypso/calypso.db`.
    from app import db as app_db
    db_path = tmp_path / "calypso.db"
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)

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
    """Test client that opts GETs into the legacy Jinja UI via HX-Request.

    The SPA serves at `/generate`, `/outputs`, etc. when web/dist/index.html
    exists. The legacy Jinja tests in this file were written before the SPA
    shipped; by tagging every GET with `HX-Request` we tell the server
    that this is an HTMX-driven partial request and the SPA fallback is
    skipped, returning the Jinja HTML the assertions target.

    POST/PATCH/DELETE routes keep their original behavior (no HX-Request)
    so the 204/302 contracts the tests assert are preserved.
    """
    c = app.test_client()

    def _hx_get(url, **kw):
        headers = kw.pop("headers", {}) or {}
        headers.setdefault("HX-Request", "true")
        return c.get(url, headers=headers, **kw)

    class HxClient:
        def get(self, url, **kw):
            return _hx_get(url, **kw)

        def post(self, url, **kw):
            return c.post(url, **kw)

        def patch(self, url, **kw):
            return c.patch(url, **kw)

        def put(self, url, **kw):
            return c.put(url, **kw)

        def delete(self, url, **kw):
            return c.delete(url, **kw)

    return HxClient()


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
    def test_homepage_serves_spa_or_redirects(self, client):
        """With web/dist/ built, `/` serves the SPA bundle (200, HTML).
        Without it, the legacy redirect kicks in (302 → /generate)."""
        resp = client.get("/")
        if resp.status_code in (301, 302, 308):
            assert "/generate" in resp.headers["Location"]
        else:
            assert resp.status_code == 200
            assert b"<!doctype html>" in resp.data.lower() or b"<html" in resp.data.lower()


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
        # Now returns an HTML fragment (job card with polling wiring)
        body = resp.data.decode()
        assert "job-card" in body
        assert "test prompt" in body
        assert 'hx-get="/generate/' in body and "/status" in body

    def test_reference_id_translates_to_local_path(self, client, env_with_fal, monkeypatch, tmp_path):
        """The dropdown sends an id (filename); server resolves it to a local path."""
        from app import server as srv
        from scripts import generate as gen_mod

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        target = upload_dir / "ref_42.png"
        target.write_bytes(b"\x89PNG\r\n\x1a\n")
        monkeypatch.setattr(srv, "REFERENCES_UPLOAD_DIR", upload_dir)

        captured = {}

        def fake_generate(prompt, *, model="auto", reference=None, **kwargs):
            captured["reference"] = reference
            captured["prompt"] = prompt
            from pathlib import Path
            class R:
                output_path = Path("/tmp/fake.mp4")
                model = "h3-max"
                duration_seconds = 8
                resolution = "768p"
                cost_usd = 0.4
                elapsed_seconds = 1.0
                reference_used = reference
                source_request_id = "x"
            return R()

        monkeypatch.setattr(gen_mod, "generate", fake_generate)
        monkeypatch.setattr(jobs, "run_generate", fake_generate)

        resp = client.post(
            "/generate",
            data={"prompt": "with ref", "model": "auto", "reference": "ref_42.png"},
        )
        assert resp.status_code == 200
        assert captured["reference"] == str(target)
        assert captured["prompt"] == "with ref"

    def test_reference_id_outside_upload_dir_rejected_silently(self, client, env_with_fal, monkeypatch, tmp_path):
        """A reference id that escapes the upload dir is treated as 'no reference'."""
        from app import server as srv
        from scripts import generate as gen_mod

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        monkeypatch.setattr(srv, "REFERENCES_UPLOAD_DIR", upload_dir)

        captured = {}

        def fake_generate(prompt, *, reference=None, **kwargs):
            captured["reference"] = reference
            from pathlib import Path
            class R:
                output_path = Path("/tmp/fake.mp4")
                model = "h3-max"; duration_seconds = 8; resolution = "768p"
                cost_usd = 0.4; elapsed_seconds = 1.0
                reference_used = reference; source_request_id = "x"
            return R()

        monkeypatch.setattr(gen_mod, "generate", fake_generate)
        monkeypatch.setattr(jobs, "run_generate", fake_generate)

        resp = client.post(
            "/generate",
            data={"prompt": "with bad ref", "model": "auto", "reference": "../../etc/passwd"},
        )
        assert resp.status_code == 200
        assert captured["reference"] is None


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
        assert b"No references uploaded" in resp.data or b"No references yet" in resp.data

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


# ---------- advanced generate: multi-ref, brand injection, drafts ----------

class TestMultiRefSubmit:
    def _seed_refs(self, upload_dir: Path, n: int = 2):
        upload_dir.mkdir(parents=True, exist_ok=True)
        names = []
        for i in range(n):
            p = upload_dir / f"ref_{i}.png"
            p.write_bytes(b"\x89PNG\r\n\x1a\n")
            names.append(p.name)
        return names

    def _stub_generate(self, monkeypatch, captured):
        from scripts import generate as gen_mod

        def fake(prompt, *, reference=None, **kwargs):
            captured.setdefault("calls", []).append(
                {"prompt": prompt, "reference": reference}
            )
            class R:
                output_path = Path("/tmp/fake.mp4")
                model = "h3-max"
                duration_seconds = 8
                resolution = "768p"
                cost_usd = 0.4
                elapsed_seconds = 1.0
                reference_used = reference
                source_request_id = "x"
            return R()

        monkeypatch.setattr(gen_mod, "generate", fake)
        monkeypatch.setattr(jobs, "run_generate", fake)

    def test_multi_ref_creates_batch(self, client, env_with_fal, tmp_path, monkeypatch):
        upload_dir = tmp_path / "uploads"
        ids = self._seed_refs(upload_dir, n=3)
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)
        captured = {}
        self._stub_generate(monkeypatch, captured)

        resp = client.post(
            "/generate",
            data={
                "prompt": "three refs at once",
                "model": "auto",
                "ref_ids": ids,  # Flask test client expands lists
            },
        )
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "batch-card" in body
        assert "Batch" in body
        # Three generate calls were made, one per ref
        assert len(captured["calls"]) == 3

    def test_single_ref_creates_one_job(self, client, env_with_fal, tmp_path, monkeypatch):
        upload_dir = tmp_path / "uploads"
        ids = self._seed_refs(upload_dir, n=1)
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)
        captured = {}
        self._stub_generate(monkeypatch, captured)

        resp = client.post(
            "/generate",
            data={"prompt": "single", "ref_ids": ids},
        )
        assert resp.status_code == 200
        body = resp.data.decode()
        # Single-job path: not a batch card.
        assert "batch-card" not in body
        assert "job-card" in body
        assert len(captured["calls"]) == 1

    def test_multi_ref_silently_drops_invalid(
        self, client, env_with_fal, tmp_path, monkeypatch
    ):
        upload_dir = tmp_path / "uploads"
        ids = self._seed_refs(upload_dir, n=1)
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)
        captured = {}
        self._stub_generate(monkeypatch, captured)

        # One good id, one traversal attempt. The bad id is kept in the batch.
        # as a (filename, None) tuple, creating a no-ref job alongside the good one.
        resp = client.post(
            "/generate",
            data={"prompt": "with bad ref", "ref_ids": ids + ["../../etc/passwd"]},
        )
        assert resp.status_code == 200
        assert len(captured["calls"]) == 2
        # Good ref resolved to its absolute path.
        good = [c for c in captured["calls"] if c["reference"] is not None]
        assert len(good) == 1
        # Bad ref resolved to None (no path-traversal escape).
        bad = [c for c in captured["calls"] if c["reference"] is None]
        assert len(bad) == 1


class TestBrandInjection:
    def test_brand_block_prepended_to_prompt(
        self, client, env_with_fal, tmp_path, monkeypatch
    ):
        from app import brand as brand_mod
        from app import db as app_db

        # Reset DB to a temp file
        db_path = tmp_path / "calypso.db"
        app_db.reset_for_tests(db_path)
        monkeypatch.setattr(app_db, "DB_PATH", db_path)

        b = brand_mod.save_brand(
            "Gachakingdoms",
            tagline="Pull the blade",
            audience="Collectors",
            palette=["#ff6a1f", "#0a0a0c"],
            voice="cinematic",
        )
        brand_mod.set_active_brand(b["id"])

        captured = {}

        def fake(prompt, *, reference=None, **kwargs):
            captured["prompt"] = prompt
            class R:
                output_path = Path("/tmp/fake.mp4")
                model = "h3-max"; duration_seconds = 8; resolution = "768p"
                cost_usd = 0.4; elapsed_seconds = 1.0
                reference_used = reference; source_request_id = "x"
            return R()

        from scripts import generate as gen_mod
        monkeypatch.setattr(gen_mod, "generate", fake)
        monkeypatch.setattr(jobs, "run_generate", fake)

        resp = client.post("/generate", data={"prompt": "Hero draws blade"})
        assert resp.status_code == 200
        assert "[BRAND]" in captured["prompt"]
        assert "Name: Gachakingdoms" in captured["prompt"]
        assert "Hero draws blade" in captured["prompt"]

    def test_explicit_brand_id_overrides_active(
        self, client, env_with_fal, tmp_path, monkeypatch
    ):
        from app import brand as brand_mod
        from app import db as app_db

        db_path = tmp_path / "calypso.db"
        app_db.reset_for_tests(db_path)
        monkeypatch.setattr(app_db, "DB_PATH", db_path)

        a = brand_mod.save_brand("ActiveBrand")
        b = brand_mod.save_brand("ExplicitBrand")
        brand_mod.set_active_brand(a["id"])

        captured = {}

        def fake(prompt, *, reference=None, **kwargs):
            captured["prompt"] = prompt
            class R:
                output_path = Path("/tmp/fake.mp4")
                model = "h3-max"; duration_seconds = 8; resolution = "768p"
                cost_usd = 0.4; elapsed_seconds = 1.0
                reference_used = reference; source_request_id = "x"
            return R()

        from scripts import generate as gen_mod
        monkeypatch.setattr(gen_mod, "generate", fake)
        monkeypatch.setattr(jobs, "run_generate", fake)

        resp = client.post(
            "/generate",
            data={"prompt": "Hi", "brand_id": str(b["id"])},
        )
        assert resp.status_code == 200
        assert "Name: ExplicitBrand" in captured["prompt"]
        assert "Name: ActiveBrand" not in captured["prompt"]


class TestDraftRoutes:
    def test_save_then_drafts_api_round_trip(self, client, tmp_path, monkeypatch):
        from app import db as app_db

        db_path = tmp_path / "calypso.db"
        app_db.reset_for_tests(db_path)
        monkeypatch.setattr(app_db, "DB_PATH", db_path)

        resp = client.post(
            "/drafts/save",
            data={"name": "Hero reveal", "body": "Close-up on a hero in firelight."},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        resp = client.get("/drafts/api?draft_query=hero")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Hero reveal" in body

    def test_favorite_toggle(self, client, tmp_path, monkeypatch):
        from app import db as app_db
        from app import drafts

        db_path = tmp_path / "calypso.db"
        app_db.reset_for_tests(db_path)
        monkeypatch.setattr(app_db, "DB_PATH", db_path)
        d = drafts.save_draft("x", "y")

        resp = client.post(f"/drafts/{d['id']}/favorite")
        assert resp.status_code == 302
        fetched = drafts.get_draft(d["id"])
        assert fetched["is_favorite"] is True


class TestRefsTagsRoute:
    def test_set_tags_round_trip(self, client, tmp_path, monkeypatch):
        from app import refs as refs_mod

        upload_dir = tmp_path / "uploads"
        (upload_dir).mkdir(parents=True)
        (upload_dir / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)

        resp = client.post(
            "/references/img.png/tags",
            data={"tags": "character, hero"},
        )
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "character" in body
        assert "hero" in body
        assert refs_mod.get_tags("img.png") == ["character", "hero"]

    def test_tag_set_returns_partial_for_htmx(self, client, tmp_path, monkeypatch):
        from app import refs as refs_mod

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir(parents=True)
        (upload_dir / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)

        resp = client.post(
            "/references/img.png/tags",
            data={"tags": "background"},
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        # Just the editor partial, not the whole page.
        assert b"<html" not in resp.data


class TestBrandPage:
    def test_brand_page_renders(self, client):
        resp = client.get("/brand")
        assert resp.status_code == 200
        assert b"Brand" in resp.data
        assert b"New brand" in resp.data

    def test_save_then_brand_visible(self, client, tmp_path, monkeypatch):
        from app import db as app_db

        db_path = tmp_path / "calypso.db"
        app_db.reset_for_tests(db_path)
        monkeypatch.setattr(app_db, "DB_PATH", db_path)

        resp = client.post(
            "/brand/save",
            data={
                "name": "TestBrand",
                "tagline": "Hello world",
                "palette": "#ff6a1f, #0a0a0c",
                "set_active": "1",
            },
        )
        assert resp.status_code == 302

        resp = client.get("/brand")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "TestBrand" in body
        assert "Hello world" in body
        assert "#ff6a1f" in body

    def test_activate_and_clear(self, client, tmp_path, monkeypatch):
        from app import brand as brand_mod
        from app import db as app_db

        db_path = tmp_path / "calypso.db"
        app_db.reset_for_tests(db_path)
        monkeypatch.setattr(app_db, "DB_PATH", db_path)
        b = brand_mod.save_brand("ActiveTest")

        resp = client.post(f"/brand/{b['id']}/activate")
        assert resp.status_code == 302
        assert brand_mod.get_active_brand()["id"] == b["id"]

        resp = client.post("/brand/clear")
        assert resp.status_code == 302
        assert brand_mod.get_active_brand() is None


class TestOutputsPromptDisclosure:
    def test_outputs_renders_prompt_link(self, client, tmp_path, monkeypatch):
        from app import db as app_db
        out = tmp_path / "outputs" / "20260101-120000"
        out.mkdir(parents=True)
        (out / "video.mp4").write_bytes(b"x")
        monkeypatch.setattr(jobs, "OUTPUTS_DIR", tmp_path / "outputs")

        # Also create a job_link so the disclosure reveals.
        app_db.reset_for_tests(tmp_path / "calypso.db")
        monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "calypso.db")
        app_db.get_conn().execute(
            "INSERT INTO job_links(job_id, prompt_body, ref_ids_json, created_at) VALUES (?, ?, ?, ?)",
            ("20260101-120000", "Test prompt body", "[]", 0),
        )

        resp = client.get("/outputs")
        assert resp.status_code == 200
        assert b"View prompt" in resp.data

    def test_outputs_prompt_partial_returns_prompt(self, client, tmp_path, monkeypatch):
        from app import brand as brand_mod
        from app import db as app_db

        db_path = tmp_path / "calypso.db"
        app_db.reset_for_tests(db_path)
        monkeypatch.setattr(app_db, "DB_PATH", db_path)
        b = brand_mod.save_brand("FooBrand")
        conn = app_db.get_conn()
        conn.execute(
            "INSERT INTO job_links(job_id, prompt_body, brand_id, ref_ids_json, created_at) VALUES (?, ?, ?, ?, ?)",
            ("20260101-120000", "[BRAND]\\nName: Foo\\n[/BRAND]\\n[PROMPT]\\nTest\\n[/PROMPT]", b["id"], "[]", 0),
        )

        resp = client.get("/outputs/20260101-120000/prompt")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Test" in body
        assert "Brand: FooBrand" in body
