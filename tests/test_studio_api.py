"""tests/test_studio_api.py. Pytest suite for /api/studio endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="calypso-studio-"))


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    monkeypatch.setattr("app.db.DB_PATH", _TMP / "test.db")
    import app.db as db_mod

    db_mod.init_db(_TMP / "test.db")
    yield


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.image_jobs.create_image_job",
                        lambda *a, **kw: None)
    from app.server import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_studio_run_returns_artifacts(client):
    res = client.post("/api/studio/run", json={"brief": "Edgy reel for shopify"})
    assert res.status_code == 200
    data = res.get_json()
    assert "artifacts" in data
    assert "treatment" in data["artifacts"]
    assert "scenes" in data["artifacts"]
    assert "shots" in data["artifacts"]
    assert "pipeline" in data["artifacts"]
    assert isinstance(data["log"], list)
    assert data["log"], "expected at least one log entry"


def test_studio_run_persists_pipeline(client):
    res = client.post("/api/studio/run", json={"brief": "Playful tiktok ad for creators"})
    data = res.get_json()
    assert data["pipeline_id"] is not None
    pid = data["pipeline_id"]
    res2 = client.get(f"/api/pipelines/{pid}")
    assert res2.status_code == 200


def test_studio_run_requires_brief(client):
    res = client.post("/api/studio/run", json={})
    assert res.status_code == 400


def test_studio_run_short_brief_rejected(client):
    res = client.post("/api/studio/run", json={"brief": ""})
    assert res.status_code == 400


def test_studio_log_contains_each_agent(client):
    res = client.post("/api/studio/run", json={"brief": "Anything here"})
    log = res.get_json()["log"]
    agents_seen = {entry["agent"] for entry in log}
    for expected in ("director", "screenwriter", "storyboard",
                     "reference_selector", "producer", "qc"):
        assert expected in agents_seen, f"missing {expected} in log"
