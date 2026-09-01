"""tests/test_pipelines.py. Pytest suite for app.pipelines."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

# Isolated DB so we don't trample the real .calypso/calypso.db
_TMP = Path(tempfile.mkdtemp(prefix="calypso-pipelines-"))


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    monkeypatch.setattr("app.db.DB_PATH", _TMP / "test.db")
    import app.db as db_mod

    db_mod.init_db(_TMP / "test.db")
    yield
    # wipe tables
    import sqlite3

    conn = sqlite3.connect(str(_TMP / "test.db"))
    conn.executescript(
        "DELETE FROM pipeline_runs; DELETE FROM pipelines;"
    )
    conn.commit()
    conn.close()


def _good_pipeline():
    return {
        "nodes": [
            {"id": "t", "type": "trigger", "params": {"mode": "manual"}},
            {"id": "m", "type": "model", "params": {"model_id": "minimax/h3"}},
            {"id": "p", "type": "prompt", "params": {"mode": "inline", "body": "hello"}},
            {"id": "g", "type": "generate", "params": {"duration": 6, "resolution": "768p"}},
        ],
        "edges": [
            {"source": "t", "target": "m"},
            {"source": "m", "target": "g"},
            {"source": "p", "target": "g"},
        ],
    }


def test_create_list_get_pipeline():
    from app import pipelines

    p = pipelines.create_pipeline("promo-1", **_good_pipeline())
    assert p["id"] > 0
    assert p["name"] == "promo-1"
    assert len(p["nodes"]) == 4
    listed = pipelines.list_pipelines()
    assert any(x["id"] == p["id"] for x in listed)
    got = pipelines.get_pipeline(p["id"])
    assert got is not None
    assert got["name"] == "promo-1"


def test_update_pipeline():
    from app import pipelines

    p = pipelines.create_pipeline("demo", **_good_pipeline())
    out = pipelines.update_pipeline(p["id"], name="renamed", max_workers=4)
    assert out["name"] == "renamed"
    assert out["max_workers"] == 4


def test_delete_pipeline():
    from app import pipelines

    p = pipelines.create_pipeline("tmp", **_good_pipeline())
    assert pipelines.delete_pipeline(p["id"]) is True
    assert pipelines.get_pipeline(p["id"]) is None


def test_validation_rejects_two_triggers():
    from app import pipelines
    from app.pipelines import PipelineError

    bad = {
        "nodes": [
            {"id": "t1", "type": "trigger", "params": {"mode": "manual"}},
            {"id": "t2", "type": "trigger", "params": {"mode": "manual"}},
        ],
        "edges": [],
    }
    with pytest.raises(PipelineError):
        pipelines.create_pipeline("dup-trigger", **bad)


def test_validation_rejects_unknown_type():
    from app import pipelines
    from app.pipelines import PipelineError

    bad = {
        "nodes": [
            {"id": "x", "type": "banana", "params": {}},
        ],
        "edges": [],
    }
    with pytest.raises(PipelineError):
        pipelines.create_pipeline("bogus", **bad)


def test_validation_rejects_unknown_edge_target():
    from app import pipelines
    from app.pipelines import PipelineError

    bad = {
        "nodes": [{"id": "t", "type": "trigger", "params": {"mode": "manual"}}],
        "edges": [{"source": "t", "target": "nope"}],
    }
    with pytest.raises(PipelineError):
        pipelines.create_pipeline("bad-edge", **bad)


def test_topo_order_respects_edges():
    from app import pipelines

    p = pipelines.create_pipeline("topo", **_good_pipeline())
    order = pipelines._topo_order(p["nodes"], p["edges"])
    # `t` must precede `m` which must precede `g`; `p` is independent.
    assert order.index("t") < order.index("m") < order.index("g")


def test_topo_rejects_cycle():
    from app import pipelines
    from app.pipelines import PipelineError

    cyclic = {
        "nodes": [
            {"id": "a", "type": "prompt", "params": {"mode": "inline", "body": "x"}},
            {"id": "b", "type": "prompt", "params": {"mode": "inline", "body": "y"}},
        ],
        "edges": [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ],
    }
    with pytest.raises(PipelineError):
        pipelines._topo_order(cyclic["nodes"], cyclic["edges"])


def test_run_pipeline_basic_completes(monkeypatch):
    from app import pipelines

    # Replace job creation with a stub so we don't hit the network.
    def fake_create_job(*args, **kwargs):
        from dataclasses import dataclass, field
        @dataclass
        class StubJob:
            job_id: str = "stub-job"
            status: str = "queued"
            output_path: str | None = None
            def to_dict(self):
                return {"job_id": self.job_id, "status": self.status,
                        "output_path": self.output_path,
                        "model": kwargs.get("model"),
                        "duration": kwargs.get("duration"),
                        "resolution": kwargs.get("resolution"),
                        "ref_ids": kwargs.get("ref_ids", [])}
        return StubJob()

    monkeypatch.setattr("app.pipeline_nodes.jobs.create_job", fake_create_job)

    p = pipelines.create_pipeline("runme", **_good_pipeline())
    run = pipelines.run_pipeline(p["id"])
    # wait up to 2s for completion
    deadline = time.time() + 2.0
    while time.time() < deadline:
        run = pipelines.get_run(run["id"])
        if run and run["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert run is not None
    assert run["status"] == "succeeded"
    assert len(run["log"]) >= 4


def test_run_pipeline_creates_video_job(monkeypatch):
    from app import pipelines

    captured = {}

    def fake_create_job(*args, **kwargs):
        captured["model"] = kwargs.get("model")
        captured["duration"] = kwargs.get("duration")
        captured["resolution"] = kwargs.get("resolution")
        from dataclasses import dataclass
        @dataclass
        class StubJob:
            job_id: str = "stub-job"
            status: str = "queued"
            output_path: str | None = None
            def to_dict(self):
                return {"job_id": self.job_id, "status": self.status,
                        "output_path": self.output_path}
        return StubJob()

    monkeypatch.setattr("app.pipeline_nodes.jobs.create_job", fake_create_job)

    # Patch the model node runner to produce a deterministic ModelSpec-like dict
    from app import pipeline_nodes as pn
    class StubModel:
        id = "minimax/h3"
        name = "stub"
    pn.NODE_RUNNERS["model"] = lambda ctx, params, inputs: {"model": StubModel()}

    p = pipelines.create_pipeline("capture", **_good_pipeline())
    run = pipelines.run_pipeline(p["id"])
    deadline = time.time() + 2.0
    while time.time() < deadline:
        run = pipelines.get_run(pipelines.list_runs(p["id"])[0]["id"])
        if run["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert captured.get("model") == "minimax/h3"
    assert captured.get("duration") == 6


def test_node_schema_includes_every_runner():
    from app import node_schema
    from app import pipeline_nodes

    schemas = set(node_schema.NODE_SCHEMAS.keys())
    runners = set(pipeline_nodes.NODE_RUNNERS.keys())
    assert schemas == runners
