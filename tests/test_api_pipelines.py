"""tests/test_api_pipelines.py. Pytest suite for /api/pipelines endpoints."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="calypso-pipeline-api-"))


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    monkeypatch.setattr("app.db.DB_PATH", _TMP / "test.db")
    import app.db as db_mod

    db_mod.init_db(_TMP / "test.db")
    yield


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.pipeline_nodes.jobs.create_job", lambda *a, **kw: None)
    from app.server import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _good_pipeline_payload(name: str = "api-test") -> dict:
    return {
        "name": name,
        "description": "test pipeline",
        "nodes": [
            {"id": "t", "type": "trigger", "params": {"mode": "manual"}},
            {"id": "p", "type": "prompt", "params": {"mode": "inline", "body": "hi"}},
        ],
        "edges": [],
        "max_workers": 2,
        "enabled": True,
    }


def test_node_schemas_endpoint(client):
    res = client.get("/api/pipelines/node-schemas")
    assert res.status_code == 200
    data = res.get_json()
    assert "trigger" in data["schemas"]
    assert "generate" in data["schemas"]
    assert "control" in data["categories"]


def test_create_pipeline(client):
    res = client.post("/api/pipelines", json=_good_pipeline_payload("new-pipe"))
    assert res.status_code == 201
    p = res.get_json()["pipeline"]
    assert p["name"] == "new-pipe"


def test_create_rejects_two_triggers(client):
    payload = _good_pipeline_payload()
    payload["nodes"].append({"id": "t2", "type": "trigger", "params": {"mode": "manual"}})
    res = client.post("/api/pipelines", json=payload)
    assert res.status_code == 400


def test_list_get_update_delete(client):
    p1 = client.post("/api/pipelines", json=_good_pipeline_payload("p1")).get_json()["pipeline"]
    p2 = client.post("/api/pipelines", json=_good_pipeline_payload("p2")).get_json()["pipeline"]
    res = client.get("/api/pipelines")
    listed = res.get_json()["pipelines"]
    assert {p["id"] for p in listed} >= {p1["id"], p2["id"]}

    res = client.get(f"/api/pipelines/{p1['id']}")
    assert res.get_json()["pipeline"]["name"] == "p1"

    res = client.patch(f"/api/pipelines/{p1['id']}", json={"name": "renamed"})
    assert res.get_json()["pipeline"]["name"] == "renamed"

    res = client.delete(f"/api/pipelines/{p1['id']}")
    assert res.status_code == 200
    assert res.get_json()["deleted"] is True


def test_run_pipeline(client):
    p = client.post("/api/pipelines", json=_good_pipeline_payload()).get_json()["pipeline"]
    res = client.post(f"/api/pipelines/{p['id']}/run")
    assert res.status_code == 202
    run = res.get_json()["run"]
    # wait
    deadline = time.time() + 2
    while time.time() < deadline:
        r = client.get(f"/api/pipelines/runs/{run['id']}")
        if r.get_json()["run"]["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert r.get_json()["run"]["status"] == "succeeded"


def test_list_runs_per_pipeline(client):
    p = client.post("/api/pipelines", json=_good_pipeline_payload()).get_json()["pipeline"]
    client.post(f"/api/pipelines/{p['id']}/run")
    res = client.get(f"/api/pipelines/{p['id']}/runs")
    assert res.status_code == 200
    runs = res.get_json()["runs"]
    assert len(runs) >= 1


def test_get_run_404(client):
    res = client.get("/api/pipelines/runs/99999")
    assert res.status_code == 404


def test_get_pipeline_404(client):
    res = client.get("/api/pipelines/99999")
    assert res.status_code == 404


def test_run_pipeline_missing(client):
    res = client.post("/api/pipelines/99999/run")
    assert res.status_code == 400


def test_delete_missing(client):
    res = client.delete("/api/pipelines/99999")
    assert res.status_code == 404


def test_update_missing(client):
    res = client.patch("/api/pipelines/99999", json={"name": "x"})
    assert res.status_code == 404


def test_pipeline_with_model_and_generate(monkeypatch, client):
    """End-to-end: model + prompt + generate → fake create_job invoked."""
    captured = {}

    def fake_create_job(*a, **kw):
        captured["model"] = kw.get("model")
        captured["duration"] = kw.get("duration")
        from dataclasses import dataclass

        @dataclass
        class StubJob:
            job_id: str = "stub"
            status: str = "queued"
            output_path: str | None = None

            def to_dict(self):
                return {"job_id": self.job_id, "status": self.status, "output_path": self.output_path}

        return StubJob()

    monkeypatch.setattr("app.pipeline_nodes.jobs.create_job", fake_create_job)
    from app import pipeline_nodes as pn

    class StubModel:
        id = "minimax/h3"
        name = "stub"

    pn.NODE_RUNNERS["model"] = lambda ctx, params, inputs: {"model": StubModel()}

    payload = _good_pipeline_payload("e2e")
    payload["nodes"] = [
        {"id": "t", "type": "trigger", "params": {"mode": "manual"}},
        {"id": "m", "type": "model", "params": {"model_id": "minimax/h3"}},
        {"id": "p", "type": "prompt", "params": {"mode": "inline", "body": "hi"}},
        {"id": "g", "type": "generate", "params": {"duration": 6, "resolution": "768p"}},
    ]
    payload["edges"] = [
        {"source": "t", "target": "m"},
        {"source": "m", "target": "g"},
        {"source": "p", "target": "g"},
    ]
    p = client.post("/api/pipelines", json=payload).get_json()["pipeline"]
    run = client.post(f"/api/pipelines/{p['id']}/run").get_json()["run"]
    deadline = time.time() + 2
    while time.time() < deadline:
        r = client.get(f"/api/pipelines/runs/{run['id']}").get_json()["run"]
        if r["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert r["status"] == "succeeded"
    assert captured.get("model") == "minimax/h3"
