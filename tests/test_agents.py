"""tests/test_agents.py. Pytest suite for the Phase C multi-agent Studio."""

from __future__ import annotations

import pytest

from app.agents import (
    AGENTS,
    AgentContext,
    StudioError,
    all_agents,
    register_agent,
    run_studio,
)


def test_default_chain_has_seven_agents():
    assert len(AGENTS) == 7
    names = [a.name for a in AGENTS]
    assert names[0] == "director"
    assert "screenwriter" in names
    assert "storyboard" in names
    assert "reference_selector" in names
    assert "asset_forge" in names
    assert "producer" in names
    assert "qc" in names


def test_register_agent_appends_plugin():
    class Echo(AGENTS[0].__class__):
        name = "echo_plugin"
        inputs = ()
        outputs = ("echo",)
        description = "test plugin"

    register_agent(Echo())
    try:
        names = [a.name for a in all_agents()]
        assert "echo_plugin" in names
        assert names.index("echo_plugin") > names.index("producer")
    finally:
        # pop our plugin
        from app import agents as a_mod
        a_mod._PLUGIN_AGENTS.clear()


def test_register_rejects_duplicate_name():
    class Dup(AGENTS[0].__class__):
        name = "director"  # already exists
        outputs = ("x",)

    with pytest.raises(ValueError):
        register_agent(Dup())


def test_director_emits_treatment():
    ctx = AgentContext(brief="A playful reel for ecommerce founders")
    from app.agents.director import Director
    res = Director().run(ctx)
    t = res.outputs["treatment"]
    assert t["audience"] == "ecommerce operators"
    assert t["tone"] == "playful"
    assert "vertical" in t["format"]
    assert ctx.artifacts["treatment"]["audience"] == "ecommerce operators"


def test_director_extracts_explicit_cta():
    ctx = AgentContext(brief="cta: Start your free trial today")
    from app.agents.director import Director
    res = Director().run(ctx)
    assert "free trial" in res.outputs["treatment"]["cta"].lower()


def test_screenwriter_default_beats():
    from app.agents.screenwriter import Screenwriter
    ctx = AgentContext(brief="anything goes")
    Director = __import__("app.agents.director", fromlist=["Director"]).Director
    Director().run(ctx)
    res = Screenwriter().run(ctx)
    scenes = res.outputs["scenes"]
    slugs = [s["slug"] for s in scenes]
    assert "hook" in slugs
    assert "cta" in slugs


def test_screenwriter_parses_explicit_beats():
    from app.agents.director import Director
    from app.agents.screenwriter import Screenwriter
    brief = """1. Hook — opening shot (2s)
2. Proof — testimonial moment (3s)
3. CTA — call to action (2s)"""
    ctx = AgentContext(brief=brief)
    Director().run(ctx)
    res = Screenwriter().run(ctx)
    slugs = [s["slug"] for s in res.outputs["scenes"]]
    assert slugs == ["hook", "proof", "cta"]


def test_storyboard_expands_scenes_into_shots():
    from app.agents.director import Director
    from app.agents.screenwriter import Screenwriter
    from app.agents.storyboard import Storyboard
    ctx = AgentContext(brief="hook problem promise proof cta")
    Director().run(ctx)
    Screenwriter().run(ctx)
    res = Storyboard().run(ctx)
    shots = res.outputs["shots"]
    assert len(shots) >= 5
    assert all("framing" in s and "lens" in s and "motion" in s for s in shots)


def test_reference_selector_scores_overlap():
    from app.agents.director import Director
    from app.agents.reference_selector import ReferenceSelector
    refs = [
        {"id": "a", "tags": ["shopify", "ecommerce", "lifestyle"]},
        {"id": "b", "tags": ["gaming", "rgb"]},
        {"id": "c", "tags": ["shopify", "founder"]},
    ]
    ctx = AgentContext(brief="Shopify ad for ecommerce founders", references=refs)
    Director().run(ctx)
    ReferenceSelector().run(ctx)
    chosen = ctx.artifacts["selected_refs"]
    chosen_ids = [r["id"] for r in chosen]
    assert "a" in chosen_ids
    assert "c" in chosen_ids


def test_producer_emits_pipeline():
    """Producer compiles upstream artifacts into a Phase A pipeline."""
    brief = "An edgy reel for shopify founders"
    refs = [{"id": "r1", "tags": ["shopify"]}]
    result = run_studio(brief, references=refs)
    pipe = result["artifacts"]["pipeline"]
    assert any(n["type"] == "trigger" for n in pipe["nodes"])
    assert any(n["type"] == "generate" for n in pipe["nodes"])
    assert any(n["type"] == "cost_guard" for n in pipe["nodes"])
    # every generate node must have an incoming edge from a model and a prompt
    g_nodes = [n for n in pipe["nodes"] if n["type"] == "generate"]
    incoming = {(e["target"], e.get("target_port") or e.get("targetHandle") or "flow")
                for e in pipe["edges"]}
    for g in g_nodes:
        assert any(t == g["id"] for t, _ in incoming)


def test_run_studio_returns_full_log():
    result = run_studio("Simple test brief")
    names = [entry["agent"] for entry in result["log"]]
    assert "director" in names
    assert "producer" in names


def test_run_studio_requires_brief():
    with pytest.raises(StudioError):
        run_studio("")


def test_qc_is_noop_when_no_provider():
    from app.agents.qc import QC
    ctx = AgentContext(brief="anything")
    res = QC().run(ctx)
    assert res.outputs["qc"]["judged"] is False


def test_asset_forge_handles_missing_image_jobs(monkeypatch):
    """When image_jobs.create_image_job raises, forge should not crash the run."""
    import app.image_jobs as image_jobs_mod

    def boom(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(image_jobs_mod, "create_image_job", boom)
    brief = "Anything"
    result = run_studio(brief)
    assert result["artifacts"].get("forged_refs") == []
