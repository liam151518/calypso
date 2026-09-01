"""Tests for the /api/models, /api/cost-estimate, /api/image-generate,
/api/image-jobs, /api/image-outputs, and /outputs/file endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import image_jobs, jobs, server, settings
from app.server import create_app


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    env_path = tmp_path / ".env"
    upload_dir = tmp_path / "references" / "uploads"
    upload_dir.mkdir(parents=True)

    from app import db as app_db
    db_path = tmp_path / "calypso.db"
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)

    monkeypatch.setattr(settings, "ENV_PATH", env_path)
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(jobs, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(jobs, "_JOBS", {})
    monkeypatch.setattr(image_jobs, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(image_jobs, "_IMAGE_JOBS", {})

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_api_models_returns_list_and_defaults(client):
    r = client.get("/api/models", headers={"Accept": "application/json"})
    assert r.status_code == 200
    data = r.get_json()
    assert "models" in data
    assert "defaults" in data
    assert data["defaults"]["video"]
    assert data["defaults"]["image"]
    assert len(data["models"]) >= 10


def test_api_models_filters_video_and_image(client):
    r = client.get("/api/models", headers={"Accept": "application/json"})
    data = r.get_json()
    cats = {m["category"] for m in data["models"]}
    assert "video" in cats
    assert "image" in cats


def test_api_cost_estimate_video(client):
    r = client.post(
        "/api/cost-estimate",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps({"model": "minimax/h3", "duration": 8, "resolution": "768p"}),
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "estimate" in data
    est = data["estimate"]
    assert est["category"] == "video"
    assert est["usd"] > 0


def test_api_cost_estimate_image(client):
    r = client.post(
        "/api/cost-estimate",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps({"model": "flux-pro/v1.1", "num_images": 2}),
    )
    assert r.status_code == 200
    data = r.get_json()
    est = data["estimate"]
    assert est["category"] == "image"
    assert est["usd"] > 0


def test_api_image_generate_requires_prompt(client):
    r = client.post(
        "/api/image-generate",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps({"prompt": ""}),
    )
    assert r.status_code == 400


def test_api_image_generate_requires_keys(client, tmp_path):
    # No keys configured.
    r = client.post(
        "/api/image-generate",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps({"prompt": "test"}),
    )
    assert r.status_code == 400


def test_api_image_generate_creates_job(client, tmp_path, monkeypatch):
    env_path = Path(settings.ENV_PATH)
    env_path.write_text("FAL_API_KEY=fake\n")
    monkeypatch.setattr(image_jobs, "_read_fal_key", lambda: "fake")

    # Don't actually start the run — we'll verify job creation only.
    def fake_start(job):
        job.status = "succeeded"
        job.output_paths = [str(jobs.OUTPUTS_DIR / job.job_id / "image-1.png")]
        (jobs.OUTPUTS_DIR / job.job_id).mkdir(parents=True, exist_ok=True)
        (jobs.OUTPUTS_DIR / job.job_id / "image-1.png").write_bytes(b"\x89PNG\r\n")
        job.cost_usd = 0.05
        return None

    monkeypatch.setattr(image_jobs, "start_image_job", fake_start)

    r = client.post(
        "/api/image-generate",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps({"prompt": "render this", "model": "flux-pro/v1.1"}),
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["job"]["prompt"] == "render this"
    assert data["job"]["model"] == "flux-pro/v1.1"


def test_api_image_jobs_empty(client):
    r = client.get("/api/image-jobs", headers={"Accept": "application/json"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["jobs"] == []


def test_api_image_jobs_get_404_for_unknown(client):
    r = client.get("/api/image-jobs/nope", headers={"Accept": "application/json"})
    assert r.status_code == 404


def test_api_image_jobs_get_returns_existing(client, monkeypatch):
    job = image_jobs.create_image_job("a prompt")
    r = client.get(
        f"/api/image-jobs/{job.job_id}", headers={"Accept": "application/json"}
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["job"]["job_id"] == job.job_id


def test_api_image_outputs_empty(client):
    r = client.get("/api/image-outputs", headers={"Accept": "application/json"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["outputs"] == []


def test_api_outputs_file_serves_image(client, tmp_path):
    job_id = "test-job-1"
    out_dir = jobs.OUTPUTS_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    img = out_dir / "image-1.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    r = client.get(f"/outputs/file/{job_id}/image-1.png")
    assert r.status_code == 200


def test_api_outputs_file_404_for_missing(client):
    r = client.get("/outputs/file/nope/image-1.png")
    assert r.status_code == 404


def test_api_outputs_file_blocks_path_traversal(client):
    r = client.get("/outputs/file/../server.py")
    # Flask's routing normalises paths; this should never resolve to server.py.
    assert r.status_code in (404, 308, 400)


def test_image_page_renders(client):
    r = client.get("/image", headers={"HX-Request": "true"})
    assert r.status_code == 200
