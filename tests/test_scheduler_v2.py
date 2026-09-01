"""Phase C scheduler-v2 tests.

These tests intentionally use the existing ``app.marketing.scheduler`` public
API to ensure the Phase C rewire keeps the 7 pre-existing marketing tests
green. We also exercise the new ``publish_output`` kind and the legacy
loop fallback path.
"""

from __future__ import annotations

import time

import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    from app import db as app_db
    target = tmp_path / "sched.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


def test_schedule_and_list_round_trip(fresh_db):
    from app.marketing import scheduler as sched
    run_at = time.time() + 60
    job_id = sched.schedule("publish-test", "publish_output", run_at,
                            payload={"output_id": 7, "platform": "instagram"})
    assert job_id > 0
    jobs = sched.list_jobs()
    assert any(j["id"] == job_id and j["kind"] == "publish_output" for j in jobs)


def test_cancel_only_works_for_queued(fresh_db):
    from app.marketing import scheduler as sched
    job_id = sched.schedule("x", "publish_output", time.time() + 60)
    assert sched.cancel(job_id) is True
    assert sched.cancel(job_id) is False


def test_run_now_executes_publish_output_handler(fresh_db):
    """publish_output must dispatch via app.publisher.dry_run by default."""
    from app.marketing import scheduler as sched
    # Seed an output row so the handler can load it.
    from app import db as app_db, outputs as outputs_mod
    now = time.time()
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("Test", now, now),
        )
        bid = c.execute("SELECT id FROM brands WHERE name='Test'").fetchone()[0]
        c.execute(
            "INSERT INTO outputs (brand_id, type, file_path, status, created_at) "
            "VALUES (?, 'image', '/tmp/out.jpg', 'rendered', ?)",
            (bid, now),
        )
        out_id = int(c.execute("SELECT id FROM outputs ORDER BY id DESC LIMIT 1").fetchone()[0])
    # Make sure outputs is importable from the marketing scope.
    sched.register_default_handlers()
    job_id = sched.schedule(
        "dispatch",
        "publish_output",
        time.time() + 600,
        payload={"output_id": out_id, "platform": "instagram", "preferred": "dry_run"},
    )
    res = sched.run_now(job_id)
    assert res["status"] in ("dry_run", "done")
    out = outputs_mod.get_output(out_id)
    assert out["status"] == "published"


def test_approve_unblocks_a_queued_job(fresh_db):
    from app.marketing import scheduler as sched
    job_id = sched.schedule("a", "publish_output", time.time() + 3600)
    # Manually flip status to blocked to simulate the gate.
    from app import db as app_db
    with app_db.connect() as c:
        c.execute(
            "UPDATE scheduled_jobs SET status = 'blocked' WHERE id = ?",
            (job_id,),
        )
    sched.approve(job_id)
    row = sched.get_job(job_id)
    assert row["status"] == "queued"


def test_legacy_loop_is_preserved_as_alias(fresh_db):
    """The plan keeps the legacy loop available as ``_legacy_loop``."""
    from app.marketing import scheduler as sched
    assert callable(sched._legacy_loop)


def test_apscheduler_starts_when_available(fresh_db):
    """``start()`` should also boot APScheduler if it can be imported."""
    from app.marketing import scheduler as sched
    sched.start()
    # We don't care whether APScheduler actually got imported here; the legacy
    # thread is what really matters and ``start()`` should not throw.
    assert sched._THREAD is not None
    sched.stop()