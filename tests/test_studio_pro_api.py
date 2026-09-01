"""tests/test_studio_pro_api.py. Phase F.4 — Studio Pro HTTP endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


_TMP = Path(tempfile.mkdtemp(prefix="calypso-studio-pro-"))


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    db_path = _TMP / "test.db"
    monkeypatch.setattr("app.db.DB_PATH", db_path)
    import app.db as db_mod

    db_mod.reset_for_tests(db_path)
    db_mod.init_db(db_path)
    yield


@pytest.fixture
def client():
    from app.server import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_generate_returns_run_id_and_suggestions(client):
    res = client.post("/api/studio-pro/generate", json={
        "brief": "hype launch video for new sneakers",
        "platforms": ["instagram"],
        "budget_usd": 5.0,
    })
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["run_id"].startswith("spr_")
    assert body["suggestions"]


def test_generate_rejects_empty_brief(client):
    res = client.post("/api/studio-pro/generate", json={"brief": ""})
    assert res.status_code == 400


def test_log_endpoint_returns_suggestions(client):
    gen = client.post("/api/studio-pro/generate", json={
        "brief": "minimal drop for the new jacket",
    })
    run_id = gen.get_json()["run_id"]
    log_res = client.get(f"/api/studio-pro/{run_id}/log")
    assert log_res.status_code == 200
    log = log_res.get_json()
    assert log["run_id"] == run_id
    assert log["suggestions"]


def test_accept_returns_editor_url(client):
    gen = client.post("/api/studio-pro/generate", json={
        "brief": "lifestyle flatlay for new sneakers",
    })
    suggestions = gen.get_json()["suggestions"]
    if not suggestions or suggestions[0]["template_id"] is None:
        pytest.skip("no template available to accept")
    sid = client.get(
        f"/api/studio-pro/{gen.get_json()['run_id']}/log"
    ).get_json()["suggestions"][0]["id"]
    res = client.post(f"/api/studio-pro/{sid}/accept", json={})
    assert res.status_code == 200
    body = res.get_json()
    assert body["editor_url"].startswith("/editor/")
    assert body["output_id"] > 0


def test_schedule_creates_job(client):
    gen = client.post("/api/studio-pro/generate", json={
        "brief": "review for headphones",
    })
    log = client.get(
        f"/api/studio-pro/{gen.get_json()['run_id']}/log"
    ).get_json()["suggestions"]
    if not log or log[0]["template_id"] is None:
        pytest.skip("no suggestion with template_id")
    sid = log[0]["id"]
    res = client.post(f"/api/studio-pro/{sid}/schedule", json={
        "run_at": 9999999999,
        "platform": "instagram",
    })
    assert res.status_code == 200
    body = res.get_json()
    assert body["job_id"] > 0


def test_accept_404_for_unknown_suggestion(client):
    res = client.post("/api/studio-pro/999999/accept", json={})
    assert res.status_code == 404