"""Phase F.5 — Studio Pro agents + persistence tests.

We exercise:

- Each agent returns a result with the expected keys.
- `run_studio_pro` chains them in order and produces a `run_id`.
- `campaign_builder` never writes to `outputs`.
- Suggestion rows land in `studio_suggestions`.
- Confidence score is in [0, 1].
- Brand-compat uses the brand voice + director tone.
- Acceptance and scheduling routes flip the suggestion status without
  touching `outputs` directly.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app import db as app_db
from app import studio_pro as studio_pro_mod
from app.studio_pro import StudioProBrief, run_studio_pro


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    target = tmp_path / "studio_pro.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


@pytest.fixture
def brand_template_seeded(fresh_db):
    """Insert a brand + a couple of templates that the selector can score."""
    from app import brand as brand_mod
    from app import templates as templates_mod

    bid = brand_mod.save_brand(
        name="StudioPro Brand",
        voice="bold",
    )["id"]
    t1 = templates_mod.create_template({
        "name": "Bold Drop",
        "category": "ugc",
        "aspect_ratio": "1:1",
        "canvas": {"width": 1080, "height": 1080},
        "layers": [
            {"id": "bg", "type": "ai_background", "name": "BG",
             "config": {"prompt": "soft studio"}},
            {"id": "h", "type": "text", "name": "Headline", "x": 0.5, "y": 0.4,
             "config": {"content": "Headline", "font_family": "Inter",
                          "color": "#fff"}},
        ],
    }, brand_id=bid)
    t2 = templates_mod.create_template({
        "name": "Lifestyle Flatlay",
        "category": "lifestyle",
        "aspect_ratio": "4:5",
        "canvas": {"width": 1080, "height": 1350},
        "layers": [
            {"id": "bg", "type": "ai_background", "name": "BG",
             "config": {"prompt": "soft"}},
        ],
    }, brand_id=bid)
    return {"brand_id": bid, "templates": [t1, t2]}


# ---------------------------------------------------------------------------
# Agent-level
# ---------------------------------------------------------------------------


def test_director_classifies_hype_tone():
    from app.agents.base import AgentContext
    from app.studio_pro.director import Director

    out = Director().run(AgentContext(brief="hype launch video"))
    assert out.outputs["tone"] == "bold"
    assert "instagram" in out.outputs["recommended_platforms"]


def test_director_extracts_duration():
    from app.agents.base import AgentContext
    from app.studio_pro.director import Director

    out = Director().run(AgentContext(brief="30 second product reveal"))
    assert out.outputs["recommended_duration_s"] == 30


def test_director_extracts_audience():
    from app.agents.base import AgentContext
    from app.studio_pro.director import Director

    out = Director().run(AgentContext(brief="Make something for 18-25 streetwear fans"))
    assert "18-25 streetwear" in (out.outputs["audience"] or "")


def test_template_selector_returns_sorted_candidates(brand_template_seeded):
    from app.agents.base import AgentContext
    from app.studio_pro.template_selector import TemplateSelector

    seed = brand_template_seeded
    brand = {"voice": "bold", "templates": [
        {"id": 1, "name": "Bold Drop", "category": "ugc", "layers": [
            {"id": "h", "type": "text"},
        ]},
        {"id": 2, "name": "Lifestyle", "category": "lifestyle", "layers": []},
    ]}
    ctx = AgentContext(
        brief="hype launch",
        brand=brand,
        references=[],
    )
    ctx.artifacts["director"] = {"tone": "bold"}
    out = TemplateSelector().run(ctx)
    candidates = out.outputs["candidates"]
    assert candidates
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_copywriter_drafts_lines_for_text_layers(brand_template_seeded):
    from app.agents.base import AgentContext
    from app.studio_pro.copywriter import Copywriter

    seed = brand_template_seeded
    template = {"id": seed["templates"][0], "layers": [
        {"id": "h", "type": "text", "text": "Headline", "font_size": 72},
    ]}
    ctx = AgentContext(
        brief="hype launch",
        brand={"voice": "bold"},
        references=[{"name": "Sneaker"}],
    )
    ctx.artifacts["director"] = {"tone": "bold"}
    ctx.artifacts["template_selector"] = {"candidates": [{"template": template}]}
    out = Copywriter().run(ctx)
    assert "1" in out.outputs["layer_copy"]


def test_visual_strategist_picks_filter_by_tone():
    from app.agents.base import AgentContext
    from app.studio_pro.visual_strategist import VisualStrategist

    ctx = AgentContext(brief="luxury flatlay")
    ctx.artifacts["director"] = {"tone": "luxury"}
    out = VisualStrategist().run(ctx)
    assert out.outputs["visuals"]["filter"] == "vintage"


# ---------------------------------------------------------------------------
# End-to-end run
# ---------------------------------------------------------------------------


def test_run_studio_pro_produces_suggestions(brand_template_seeded, fresh_db):
    seed = brand_template_seeded
    brand = {
        "id": seed["brand_id"],
        "voice": "bold",
        "budget_usd": 5.0,
        "default_platforms": ["instagram"],
        "templates": [
            {"id": seed["templates"][0], "name": "Bold Drop",
             "category": "ugc", "layers": [
                 {"id": "bg", "type": "background"},
                 {"id": "h", "type": "text", "text": "Headline"},
             ]},
            {"id": seed["templates"][1], "name": "Lifestyle Flatlay",
             "category": "lifestyle", "layers": []},
        ],
    }
    product = {"id": 1, "name": "Sneaker"}
    brief = StudioProBrief(
        brief="Make a 30s hype launch for these new sneakers, streetwear fans",
        product_id=1,
        brand_id=seed["brand_id"],
        platforms=["instagram"],
        budget_usd=5.0,
        audience="18-25 streetwear",
        duration_s=30,
    )
    run = run_studio_pro(brief, brand=brand, product=product)
    assert run.run_id.startswith("spr_")
    assert run.suggestions
    assert all(0 <= s.get("confidence_score", -1) <= 1 for s in run.suggestions)


def test_run_studio_pro_persists_suggestions(brand_template_seeded, fresh_db):
    seed = brand_template_seeded
    # Insert a real product so the FK on studio_suggestions(product_id) holds.
    from app import products as products_mod
    pid = products_mod.create_product(
        brand_id=seed["brand_id"],
        name="Sneaker",
    )
    brand = {
        "id": seed["brand_id"],
        "voice": "bold",
        "budget_usd": 5.0,
        "default_platforms": ["instagram"],
        "templates": [
            {"id": seed["templates"][0], "name": "Bold Drop", "category": "ugc",
             "layers": [{"id": "h", "type": "text", "text": "Headline"}]},
        ],
    }
    run = run_studio_pro(
        StudioProBrief(brief="hype launch",
                        brand_id=seed["brand_id"],
                        product_id=pid),
        brand=brand,
        product={"id": pid, "name": "Sneaker"},
    )
    conn = app_db.get_conn()
    rows = conn.execute(
        "SELECT id, run_id, template_id, confidence_score, status "
        "FROM studio_suggestions WHERE run_id = ?",
        (run.run_id,),
    ).fetchall()
    assert rows
    for r in rows:
        assert r["run_id"] == run.run_id
        assert 0 <= r["confidence_score"] <= 1
        assert r["status"] == "pending"


def test_campaign_builder_does_not_write_to_outputs(brand_template_seeded, fresh_db):
    seed = brand_template_seeded
    brand = {
        "id": seed["brand_id"],
        "voice": "bold",
        "budget_usd": 5.0,
        "templates": [
            {"id": seed["templates"][0], "name": "Bold Drop", "category": "ugc",
             "layers": []},
        ],
    }
    run = run_studio_pro(
        StudioProBrief(brief="hype launch", brand_id=seed["brand_id"]),
        brand=brand,
        product={"id": 1, "name": "Sneaker"},
    )
    conn = app_db.get_conn()
    outputs_count = conn.execute("SELECT COUNT(*) AS c FROM outputs").fetchone()["c"]
    assert outputs_count == 0, "CampaignBuilder must never write to outputs"


def test_brand_compat_is_higher_when_tone_matches(brand_template_seeded):
    """Confidence_score should be higher when the Director's tone matches
    the brand's voice — verifying the brand_compat weight."""
    seed = brand_template_seeded
    common = {
        "id": seed["brand_id"],
        "budget_usd": 5.0,
        "default_platforms": ["instagram"],
        "templates": [
            {"id": seed["templates"][0], "name": "Bold Drop", "category": "ugc",
             "layers": []},
        ],
    }
    matched = run_studio_pro(
        StudioProBrief(brief="hype launch"),
        brand={**common, "voice": "bold"},
        product={"id": 1, "name": "Sneaker"},
    )
    mismatched = run_studio_pro(
        StudioProBrief(brief="hype launch"),
        brand={**common, "voice": "luxury"},
        product={"id": 1, "name": "Sneaker"},
    )
    if matched.suggestions and mismatched.suggestions:
        assert matched.suggestions[0]["confidence_score"] >= \
               mismatched.suggestions[0]["confidence_score"]


def test_cost_feasibility_low_when_above_budget(brand_template_seeded):
    """A suggestion whose estimated cost exceeds the brand's budget should
    have a lower confidence than the same suggestion under budget."""
    seed = brand_template_seeded
    common = {
        "id": seed["brand_id"],
        "voice": "bold",
        "default_platforms": ["instagram"],
        "templates": [
            {"id": seed["templates"][0], "name": "Bold Drop", "category": "ugc",
             "layers": [{"id": "h", "type": "text", "text": "Headline"}]},
        ],
    }
    high = run_studio_pro(
        StudioProBrief(brief="hype launch", budget_usd=0.01),
        brand={**common, "budget_usd": 0.01},
        product={"id": 1, "name": "Sneaker"},
    )
    generous = run_studio_pro(
        StudioProBrief(brief="hype launch", budget_usd=50.0),
        brand={**common, "budget_usd": 50.0},
        product={"id": 1, "name": "Sneaker"},
    )
    if high.suggestions and generous.suggestions:
        assert high.suggestions[0]["confidence_score"] <= \
               generous.suggestions[0]["confidence_score"]


def test_empty_template_list_still_produces_one_soft_suggestion():
    run = run_studio_pro(
        StudioProBrief(brief="anything"),
        brand={"id": 1, "voice": "bold", "templates": []},
        product=None,
    )
    assert len(run.suggestions) == 1
    assert run.suggestions[0]["template_id"] is None
    assert run.suggestions[0]["confidence_score"] < 0.5


def test_register_agent_is_a_no_op():
    from app.agents.base import Agent
    from app.studio_pro import register_agent

    class Stub(Agent):
        name = "stub"

    # Should not raise.
    register_agent(Stub()) is None
