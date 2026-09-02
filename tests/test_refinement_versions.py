"""Tests for the Refinement Studio versions CRUD + API."""

from __future__ import annotations

import json
import time

import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    from app import db as app_db
    target = tmp_path / "versions.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


@pytest.fixture
def seeded_output(fresh_db):
    """Insert one output row + an existing file."""
    from app import db as app_db
    now = time.time()
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("RefineBrand", now, now),
        )
        bid = c.execute(
            "SELECT id FROM brands WHERE name='RefineBrand'"
        ).fetchone()[0]
        c.execute(
            "INSERT INTO outputs (brand_id, type, file_path, status, "
            "created_at, layers_json, filter_settings) "
            "VALUES (?, 'image', '/tmp/orig.jpg', 'draft', ?, '[]', '{}')",
            (bid, now),
        )
        oid = c.execute(
            "SELECT id FROM outputs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    return oid


def test_create_version_round_trip(fresh_db, seeded_output):
    from app import refinement as refine
    ver = refine.create_version(
        seeded_output,
        layers_json=[{"id": "bg", "type": "ai_background"}],
        filter_settings={"filter_name": "moody", "intensity": 0.7},
        file_path="/tmp/v1.jpg",
        notes="first edit",
        cost_usd=0.04,
    )
    assert ver["id"] > 0
    assert ver["output_id"] == seeded_output
    assert ver["file_path"] == "/tmp/v1.jpg"
    assert ver["notes"] == "first edit"
    assert json.loads(ver["layers_json"]) == [{"id": "bg", "type": "ai_background"}]
    assert json.loads(ver["filter_settings"]) == {"filter_name": "moody", "intensity": 0.7}


def test_list_versions_newest_first(fresh_db, seeded_output):
    from app import refinement as refine
    refine.create_version(seeded_output, layers_json=[], filter_settings={},
                          file_path="/tmp/a.jpg")
    time.sleep(0.01)
    refine.create_version(seeded_output, layers_json=[], filter_settings={},
                          file_path="/tmp/b.jpg")
    versions = refine.list_versions(seeded_output)
    assert len(versions) == 2
    assert versions[0]["file_path"] == "/tmp/b.jpg"   # newest
    assert versions[1]["file_path"] == "/tmp/a.jpg"


def test_delete_version(fresh_db, seeded_output):
    from app import refinement as refine
    ver = refine.create_version(seeded_output, layers_json=[], filter_settings={},
                                file_path="/tmp/del.jpg")
    assert refine.delete_version(ver["id"]) is True
    assert refine.get_version(ver["id"]) is None
    assert refine.delete_version(99999) is False  # no-op


def test_promote_version_swaps_file_path(fresh_db, seeded_output):
    from app import db as app_db, refinement as refine
    ver = refine.create_version(seeded_output, layers_json=[], filter_settings={},
                                file_path="/tmp/promote.jpg")
    assert refine.promote_version(ver["id"]) is True
    with app_db.connect() as c:
        new_path = c.execute(
            "SELECT file_path FROM outputs WHERE id = ?",
            (seeded_output,),
        ).fetchone()[0]
    assert new_path == "/tmp/promote.jpg"


def test_promote_unknown_version_returns_false(fresh_db):
    from app import refinement as refine
    assert refine.promote_version(999999) is False


# ---- API endpoints -----------------------------------------------------


@pytest.fixture
def app_with_db(fresh_db):
    from app.server import create_app
    return create_app()


@pytest.fixture
def client(app_with_db):
    return app_with_db.test_client()


def test_api_versions_list_empty(client, seeded_output):
    res = client.get(f"/api/outputs/{seeded_output}/versions")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["versions"] == []


def test_api_versions_create_returns_row(client, seeded_output):
    res = client.post(f"/api/outputs/{seeded_output}/versions", json={
        "layers_json": [{"id": "bg", "type": "ai_background"}],
        "filter_settings": {"filter_name": "neon"},
        "file_path": "/tmp/x.jpg",
        "notes": "test",
        "cost_usd": 0.05,
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["version"]["file_path"] == "/tmp/x.jpg"


def test_api_versions_create_requires_file_path(client, seeded_output):
    res = client.post(f"/api/outputs/{seeded_output}/versions", json={
        "filter_settings": {},
    })
    assert res.status_code == 400


def test_api_versions_create_unknown_output(client):
    res = client.post("/api/outputs/999999/versions", json={
        "file_path": "/tmp/x.jpg",
    })
    assert res.status_code == 404


def test_api_versions_promote_swaps_file(client, seeded_output, fresh_db):
    from app import db as app_db, refinement as refine
    ver = refine.create_version(seeded_output, layers_json=[], filter_settings={},
                                file_path="/tmp/promoted.jpg")
    res = client.post(
        f"/api/outputs/{seeded_output}/versions/{ver['id']}/promote"
    )
    assert res.status_code == 200
    with app_db.connect() as c:
        path = c.execute(
            "SELECT file_path FROM outputs WHERE id = ?", (seeded_output,)
        ).fetchone()[0]
    assert path == "/tmp/promoted.jpg"


def test_api_versions_promote_unknown_returns_404(client, seeded_output):
    res = client.post(
        f"/api/outputs/{seeded_output}/versions/999999/promote"
    )
    assert res.status_code == 404


def test_api_versions_delete(client, seeded_output):
    from app import refinement as refine
    ver = refine.create_version(seeded_output, layers_json=[], filter_settings={},
                                file_path="/tmp/del.jpg")
    res = client.delete(
        f"/api/outputs/{seeded_output}/versions/{ver['id']}"
    )
    assert res.status_code == 200
    assert res.get_json()["deleted"] is True
    assert refine.get_version(ver["id"]) is None


def test_api_versions_list_unknown_output_returns_404(client):
    res = client.get("/api/outputs/999999/versions")
    assert res.status_code == 404
