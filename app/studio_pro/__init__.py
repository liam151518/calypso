"""app.studio_pro. Phase F — brand-poster multi-agent Studio Pro.

Parallel to the existing `app.agents` (film Studio) module. The two are
siblings, not replacements — the film Studio pipeline (director →
screenwriter → reference_selector → asset_forge → producer → qc → ...)
stays intact. Studio Pro adds a brand-poster–oriented chain:

    Director → TemplateSelector → Copywriter → VisualStrategist →
    CampaignBuilder

Each agent extends `app.agents.base.Agent`. The chain is wired by
`app.studio_pro.run_studio_pro`, which:

  1. Builds an `AgentContext` from the request brief + brand + products.
  2. Runs the agents in order, capturing their outputs into
     `studio_suggestions` (one row per agent) and a final row per
     `CampaignBuilder` result.
  3. Returns a `run_id` the SPA can poll for live progress.

Critical rule (per spec §2.2): Studio Pro agents never write to the
`outputs` table. They output `template_id` + `layer_overrides` JSON only.
The Compositor renders previews on demand.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.agents.base import Agent, AgentContext, AgentResult
from app import db as app_db


@dataclass
class StudioProBrief:
    """The input the user typed into the Studio Pro UI."""

    brief: str
    product_id: int | None = None
    brand_id: int | None = None
    platforms: list[str] = field(default_factory=lambda: ["instagram"])
    budget_usd: float = 5.0
    audience: str | None = None
    duration_s: int | None = None


@dataclass
class StudioProRun:
    """A running Studio Pro session, surfaced as a JSON object to the UI."""

    run_id: str
    brief: StudioProBrief
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    agent_log: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    spent_usd: float = 0.0


def new_run_id() -> str:
    return f"spr_{uuid.uuid4().hex[:12]}"


def register_agent(agent: Agent) -> None:
    """No-op stub kept for API parity with `app.agents.register_agent`.

    Studio Pro agents are stateless and aren't dispatched through the
    orchestrator's name-based registry — `run_studio_pro` calls them
    directly in order. We expose this function so external callers can
    plug in their own agents in the future without code changes.
    """
    return None


def run_studio_pro(
    brief: StudioProBrief,
    *,
    brand: dict | None = None,
    product: dict | None = None,
    templates: list[dict] | None = None,
    pipeline: list[Agent] | None = None,
) -> StudioProRun:
    """Execute the Studio Pro agent chain and return a run descriptor."""
    from app.studio_pro import (
        copywriter,
        campaign_builder,
        director,
        template_selector,
        visual_strategist,
    )

    run = StudioProRun(run_id=new_run_id(), brief=brief)
    ctx = AgentContext(brief=brief.brief, brand=brand or {})
    if product is not None:
        ctx.references = [product]
    pipeline = pipeline or [
        director.Director(),
        template_selector.TemplateSelector(),
        copywriter.Copywriter(),
        visual_strategist.VisualStrategist(),
        campaign_builder.CampaignBuilder(),
    ]
    for agent in pipeline:
        run.agent_log.append({
            "agent": agent.name,
            "started_at": time.time(),
            "status": "running",
        })
        try:
            result = agent.run(ctx)
        except Exception as exc:  # noqa: BLE001
            run.agent_log[-1].update({"status": "error", "error": str(exc)})
            ctx.record(agent.name, f"error: {exc}")
            run.finished_at = time.time()
            return run
        ctx.artifacts[agent.name] = result.outputs
        run.agent_log[-1].update({
            "status": "ok",
            "finished_at": time.time(),
            "outputs": list(result.outputs.keys()),
            "note": result.note,
        })
    builder_outputs = ctx.artifacts.get("campaign_builder") or {}
    run.suggestions = list(builder_outputs.get("suggestions") or [])
    run.spent_usd = float(builder_outputs.get("spent_usd") or 0.0)
    run.finished_at = time.time()
    _persist_run(run, brand=brand, product=product, templates=templates)
    return run


def _persist_run(
    run: StudioProRun,
    *,
    brand: dict | None,
    product: dict | None,
    templates: list[dict] | None,
) -> None:
    """Insert suggestion rows into `studio_suggestions`. We never write
    to `outputs` here — that's the Compositor's job, triggered only when
    the user explicitly accepts a suggestion.
    """
    try:
        conn = app_db.get_conn()
    except Exception:  # noqa: BLE001
        return
    for s in run.suggestions:
        try:
            conn.execute(
                """INSERT INTO studio_suggestions(
                       run_id, brand_id, brief, product_id, template_id,
                       layer_overrides_json, rationale_json,
                       confidence_score, cost_usd, status, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    run.run_id,
                    (brand or {}).get("id"),
                    str(getattr(getattr(run, "brief", None), "brief", "") or ""),
                    (product or {}).get("id"),
                    s.get("template_id"),
                    _json(s.get("layer_overrides")),
                    _json({"why": s.get("rationale"),
                            "platforms": s.get("platforms", [])}),
                    float(s.get("confidence_score") or 0.0),
                    float(s.get("cost_usd") or 0.0),
                    time.time(),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            # Don't let a bad suggestion block the whole run.
            import logging
            logging.getLogger(__name__).warning("studio_pro persist failed: %s", exc)
            continue
    conn.commit()


def _json(value: Any) -> str:
    import json
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return "null"


__all__ = [
    "StudioProBrief",
    "StudioProRun",
    "new_run_id",
    "register_agent",
    "run_studio_pro",
]