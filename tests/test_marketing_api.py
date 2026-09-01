"""tests/test_marketing_api.py. Pytest for the Phase F JSON API."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    db = Path(tempfile.mkdtemp()) / "m.db"
    import app.db as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db)
    db_mod.init_db(db)
    yield


@pytest.fixture
def client(monkeypatch):
    from app.server import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_contact_lifecycle(client):
    r = client.post("/api/contacts", json={
        "email": "A@X.com", "first_name": "A", "consent_marketing": True,
    })
    assert r.status_code in (200, 201)
    cid = r.get_json()["id"]
    r2 = client.get("/api/contacts")
    data = r2.get_json()
    assert any(c["email"] == "a@x.com" for c in data["contacts"])
    r3 = client.delete(f"/api/contacts/{cid}")
    assert r3.status_code == 200


def test_contact_invalid_email_rejected(client):
    r = client.post("/api/contacts", json={"email": "no-at"})
    assert r.status_code == 400


def test_unsubscribe_endpoint(client):
    client.post("/api/contacts", json={"email": "u@x.com", "consent_marketing": True})
    r = client.post("/api/contacts/unsubscribe", json={"email": "u@x.com"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_campaign_lifecycle(client):
    r = client.post("/api/campaigns", json={"name": "Test", "channel": "email"})
    assert r.status_code in (200, 201)
    cid = r.get_json()["id"]
    r2 = client.patch(f"/api/campaigns/{cid}", json={"status": "scheduled"})
    assert r2.status_code == 200
    # send should also work
    r3 = client.post(f"/api/campaigns/{cid}/send")
    assert r3.status_code == 200


def test_campaign_invalid_channel_rejected(client):
    r = client.post("/api/campaigns", json={"name": "x", "channel": "smoke"})
    assert r.status_code == 400


def test_landing_page_lifecycle(client):
    r = client.post("/api/pages", json={"title": "Signup", "slug": "signup"})
    assert r.status_code in (200, 201)
    pid = r.get_json()["id"]
    r2 = client.get("/api/pages")
    assert any(p["id"] == pid for p in r2.get_json()["pages"])
    r3 = client.patch(f"/api/pages/{pid}", json={"published": True})
    assert r3.status_code == 200
    r4 = client.delete(f"/api/pages/{pid}")
    assert r4.status_code == 200


def test_social_post_lifecycle(client):
    r = client.post("/api/social", json={"platform": "x", "body": "hi"})
    assert r.status_code in (200, 201)
    pid = r.get_json()["id"]
    r2 = client.patch(f"/api/social/{pid}", json={"status": "queued"})
    assert r2.status_code == 200


def test_social_post_invalid_platform(client):
    r = client.post("/api/social", json={"platform": "myspace", "body": "x"})
    assert r.status_code == 400


def test_analytics_aggregate_empty(client):
    r = client.get("/api/analytics/aggregate?days=1")
    assert r.status_code == 200
    assert "aggregate" in r.get_json()


def test_analytics_record_unknown_kind_rejected(client):
    r = client.post("/api/analytics/events", json={"kind": "bogus"})
    assert r.status_code == 400


def test_scheduler_job_lifecycle(client):
    r = client.post("/api/scheduler/jobs", json={
        "name": "x", "kind": "send_campaign", "run_at": 9999999999,
    })
    assert r.status_code in (200, 201)
    jid = r.get_json()["id"]
    r2 = client.delete(f"/api/scheduler/jobs/{jid}")
    assert r2.status_code == 200


def test_scheduler_invalid_kind(client):
    r = client.post("/api/scheduler/jobs", json={
        "name": "x", "kind": "unicorn", "run_at": 9999999999,
    })
    assert r.status_code == 400


def test_compliance_export(client):
    client.post("/api/contacts", json={"email": "g@x.com", "consent_marketing": True})
    r = client.post("/api/compliance/export", json={"email": "g@x.com"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["found"] is True
    assert data["contact"]["email"] == "g@x.com"


def test_compliance_erase(client):
    client.post("/api/contacts", json={"email": "g@x.com", "consent_marketing": True})
    r = client.post("/api/compliance/erase", json={"email": "g@x.com"})
    assert r.status_code == 200
    assert r.get_json()["erased"] is True
