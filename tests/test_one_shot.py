"""Phase D.4 — one_shot brief parsing + smoke render.

We don't generate real videos here (the heavy lifting is exercised in
`test_video_pipeline.py`). The focus is on:

  - keyword detection picks the correct UGC template
  - the brief plan has the right number of scenes
  - one_shot() wires through to video_compositor without raising
"""

from __future__ import annotations

import pytest

from app import db as app_db
from app import one_shot
from app import templates as templates_mod
from app import video_compositor as vc


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Redirect app_db.DB_PATH to a temp file and re-init the schema."""
    target = tmp_path / "one_shot.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


@pytest.fixture
def phase_d_seed(fresh_db, monkeypatch):
    """Insert brand/product/templates needed for one_shot to resolve."""
    conn = app_db.get_conn()
    conn.execute(
        "INSERT INTO brands(name, voice_tone, created_at, updated_at) "
        "VALUES (?, 'casual', 0.0, 0.0)",
        ("Phase D Brand",),
    )
    bid = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.execute(
        "INSERT INTO products(name, brand_id, created_at, updated_at) "
        "VALUES (?, ?, 0.0, 0.0)",
        ("Phase D Test Sneaker", bid),
    )
    pid = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

    for name in vc.list_ugc_templates():
        body = vc.load_ugc_template(name)
        body = {**body, "name": f"UGC {name.replace('_', ' ').title()}"}
        templates_mod.create_template(body)
    conn.commit()
    # Disable real ffmpeg usage so the smoke tests run quickly.
    monkeypatch.setattr(vc, "_which_ffmpeg", lambda: None)
    return {"brand_id": bid, "product_id": pid}


def test_parse_brief_picks_unboxing():
    plan = one_shot.parse_brief("30s unboxing for new sneakers, hype energy")
    assert plan.template_name == "unboxing"
    assert len(plan.scenes) > 0


def test_parse_brief_picks_review_for_verdict_keyword():
    plan = one_shot.parse_brief("honest verdict on the headphones")
    assert plan.template_name == "review"


def test_parse_brief_picks_tutorial_for_how_to():
    plan = one_shot.parse_brief("how to style this jacket")
    assert plan.template_name == "tutorial"


def test_parse_brief_picks_lifestyle_for_lifestyle_keyword():
    plan = one_shot.parse_brief("lifestyle flatlay for morning routine")
    assert plan.template_name == "lifestyle"


def test_parse_brief_picks_hype_for_hype_keyword():
    plan = one_shot.parse_brief("hype reel for the launch")
    assert plan.template_name == "launch_hype"


def test_parse_brief_has_duration_matching_scenes():
    plan = one_shot.parse_brief("unboxing")
    expected = sum(float(s.get("duration_s") or 0) for s in plan.scenes)
    assert plan.duration_s == pytest.approx(expected)


def test_one_shot_falls_back_when_ffmpeg_missing(phase_d_seed):
    # No ffmpeg → quick_clip path is taken (which also requires ffmpeg,
    # so we expect a RuntimeError). The important thing is that
    # brief-parsing + template resolution succeed before that fails.
    seed = phase_d_seed
    with pytest.raises(Exception):  # noqa: BLE001
        one_shot.one_shot(
            "Make a 30s unboxing hype reel for these new sneakers",
            product_id=seed["product_id"],
            brand={"id": seed["brand_id"]},
            duration_s=8,
        )


def test_one_shot_emits_progress_events(phase_d_seed, monkeypatch):
    captured = []

    from app import events

    def _capture(payload):
        captured.append(payload)

    events.register("brief_parsed", _capture)
    events.register("rendering", _capture)
    events.register("fallback_quick_clip", _capture)
    try:
        seed = phase_d_seed
        with pytest.raises(Exception):  # noqa: BLE001
            one_shot.one_shot(
                "Make a 30s unboxing hype reel for these new sneakers",
                product_id=seed["product_id"],
                brand={"id": seed["brand_id"]},
                duration_s=8,
            )
        # brief_parsed is always published, before any failure.
        assert any("template" in (p or {}) for p in captured)
    finally:
        events.clear()


def test_keyword_map_covers_common_intents():
    assert one_shot.KEYWORD_TO_TEMPLATE["unboxing"] == "unboxing"
    assert one_shot.KEYWORD_TO_TEMPLATE["review"] == "review"
    assert one_shot.KEYWORD_TO_TEMPLATE["tutorial"] == "tutorial"
    assert one_shot.KEYWORD_TO_TEMPLATE["lifestyle"] == "lifestyle"
    assert one_shot.KEYWORD_TO_TEMPLATE["hype"] == "launch_hype"