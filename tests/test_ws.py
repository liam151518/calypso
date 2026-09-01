"""Phase G.6 — WebSocket / SSE render progress tests."""

from __future__ import annotations

import json
import time

from app import events as events_mod


def _iter_sse(gen, max_events=10):
    """Pull `max_events` from an SSE generator without exhausting it."""
    pulled = []
    for _ in range(max_events):
        try:
            pulled.append(next(gen))
        except StopIteration:
            break
    return pulled


def test_queue_api_appends_events():
    events_mod.clear()
    job = "test_job_1"
    events_mod.enqueue(job, "queued")
    events_mod.enqueue(job, "started")
    events_mod.enqueue(job, "exported", {"output_id": 5})
    drained = events_mod.drain(job)
    names = [e["name"] for e in drained]
    assert names == ["queued", "started", "exported"]


def test_queue_api_drain_empty_for_unknown_job():
    events_mod.clear()
    assert events_mod.drain("nope") == []


def test_subscriber_register_and_publish():
    events_mod.clear()
    seen: list[dict] = []

    def cb(payload):
        seen.append(payload)

    events_mod.register("hello", cb)
    try:
        events_mod.publish("hello", {"x": 1})
        events_mod.publish("hello", {"x": 2})
        assert [p["x"] for p in seen] == [1, 2]
    finally:
        events_mod.unregister("hello", cb)


def test_subscriber_errors_are_swallowed():
    events_mod.clear()
    seen: list[int] = []

    def boom(_payload):
        raise RuntimeError("boom")

    def ok(_payload):
        seen.append(1)

    events_mod.register("mixed", boom)
    events_mod.register("mixed", ok)
    try:
        events_mod.publish("mixed", {})  # must not raise
        assert seen == [1]
    finally:
        events_mod.clear_queue()
        events_mod._subscribers.clear()  # type: ignore[attr-defined]


def test_sse_stream_emits_queued_events():
    from app import ws as ws_mod

    events_mod.clear()
    job = "sse_job"
    events_mod.enqueue(job, "queued")
    events_mod.enqueue(job, "exported", {"output_id": 42})

    # The generator should emit both events and then terminate (because
    # 'exported' is in the closing set). Drain everything within timeout.
    chunks = list(ws_mod.stream_for(job, timeout_s=2.0))
    text = "".join(chunks)
    assert "event: queued" in text
    assert "event: exported" in text
    # Confirm the exported payload made it through.
    assert '"output_id": 42' in text


def test_sse_stream_terminates_after_export():
    from app import ws as ws_mod

    events_mod.clear()
    job = "sse_done"
    events_mod.enqueue(job, "started")
    events_mod.enqueue(job, "exported")
    # Exhaust the generator.
    chunks = list(ws_mod.stream_for(job, timeout_s=1.0))
    assert any("event: exported" in c for c in chunks)


def test_sse_stream_handles_no_events():
    from app import ws as ws_mod

    events_mod.clear()
    gen = ws_mod.stream_for("never", timeout_s=0.5)
    # Should at least emit a heartbeat-timeout marker.
    chunks = list(gen)
    assert any("heartbeat" in c for c in chunks)


def test_render_endpoint_emits_events_via_compositor(tmp_path, monkeypatch):
    """End-to-end: rendering a tiny template publishes progress events."""
    from app import db as app_db
    from app import templates as tpl_mod

    db = tmp_path / "r.db"
    monkeypatch.setattr(app_db, "DB_PATH", db)
    app_db.reset_for_tests(db)
    app_db.init_db(db)

    tid = tpl_mod.create_template({
        "name": "Tiny",
        "aspect_ratio": "1:1",
        "canvas": {"width": 256, "height": 256},
        "layers": [
            {"id": "bg", "type": "shape", "name": "BG",
             "config": {"shape_type": "rectangle", "fill_color": "#000"}},
        ],
    })

    from app import compositor as comp_mod

    events_mod.clear()
    res = comp_mod.render(tid, job_id="render_job_42", cache_hit_only=True)
    assert res.output_id > 0

    drained = events_mod.drain("render_job_42")
    names = [e["name"] for e in drained]
    assert "started" in names
    assert "layers_composed" in names
    assert "exported" in names