"""app.one_shot. Phase D.3 — turn a natural-language brief into a video.

    one_shot(brief, *, template_id=None, product_id, brand, duration_s=30)
        -> app.video_compositor.RenderResult

The pipeline is:

  1. `parse_brief(brief)` extracts intent keywords
     (`unboxing`, `review`, `hype`, `lifestyle`, `tutorial`) so we can pick
     the right UGC template.
  2. If `template_id` is None, we look up the best-matching UGC template
     from `templates/builtin/ugc/`.
  3. We derive per-scene prompts from the brief + product + brand.
  4. We defer real video generation to `app.jobs` when a video backend is
     available; otherwise we fall back to a quick static composite via
     `app.video_compositor.quick_clip`.
  5. Progress is exposed via `events.publish` so the SPA's WebSocket layer
     can show updates.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from app import db as app_db
from app import video_compositor as vc


KEYWORD_TO_TEMPLATE = {
    "unboxing": "unboxing",
    "review": "review",
    "hype": "launch_hype",
    "lifestyle": "lifestyle",
    "tutorial": "tutorial",
    "how to": "tutorial",
    "first look": "unboxing",
    "verdict": "review",
}


@dataclass
class BriefPlan:
    template_name: str
    scenes: list[dict]
    prompts: list[str]
    duration_s: float


def parse_brief(brief: str) -> BriefPlan:
    """Classify the brief and produce a scene-by-scene prompt plan."""
    text = (brief or "").lower()
    template_name = "unboxing"  # safe default
    for kw, name in KEYWORD_TO_TEMPLATE.items():
        if kw in text:
            template_name = name
            break
    template = vc.load_ugc_template(template_name)
    scenes = template.get("scenes") or []
    prompts: list[str] = []
    for scene in scenes:
        prompts.append(_derive_scene_prompt(scene, brief))
    duration_s = sum(float(scene.get("duration_s") or 0) for scene in scenes)
    return BriefPlan(
        template_name=template_name,
        scenes=scenes,
        prompts=prompts,
        duration_s=duration_s,
    )


def _derive_scene_prompt(scene: dict, brief: str) -> str:
    """Build a single scene prompt. Kept simple — the heavy lifting is in the
    video backend; for fallback mode the prompt is logged, not used."""
    kind = scene.get("kind") or scene.get("id") or "scene"
    return f"{kind}: {brief}"


def one_shot(
    brief: str,
    *,
    template_id: int | None = None,
    product_id: int,
    brand: dict,
    duration_s: int = 30,
) -> vc.RenderResult:
    """Turn a brief into a renderable video result."""
    started = time.monotonic()
    plan = parse_brief(brief)
    _publish_progress("brief_parsed", {"template": plan.template_name,
                                        "scenes": len(plan.scenes)})
    # Resolve a template id: explicit > matched > first UGC template.
    resolved_id: int | None = template_id
    if resolved_id is None:
        resolved_id = _find_template_id(plan.template_name)
    if resolved_id is None:
        # Hard fallback: render an arbitrary static template via quick_clip.
        first = vc.list_ugc_templates()
        if not first:
            raise RuntimeError("no UGC templates available")
        resolved_id = _find_template_id(first[0])
    if resolved_id is None:
        raise RuntimeError("could not resolve template_id for one_shot")

    brand_id = brand.get("id") if isinstance(brand, dict) else None
    _publish_progress("rendering", {"template_id": resolved_id, "duration_s": duration_s})
    try:
        result = vc.render_video(
            resolved_id,
            product_id=product_id,
            brand_id=brand_id,
            audio_track=None,
        )
    except Exception as exc:
        _publish_progress("fallback_quick_clip", {"reason": str(exc)})
        result = vc.quick_clip(
            template_id=resolved_id,
            product_id=product_id,
            brand_id=brand_id,
            duration_s=duration_s,
        )
    _publish_progress("done", {"output_id": result.output_id,
                                "elapsed": round(time.monotonic() - started, 3)})
    return result


def _find_template_id(name: str) -> int | None:
    conn = app_db.get_conn()
    row = conn.execute(
        "SELECT id FROM templates WHERE name = ? ORDER BY id LIMIT 1",
        (f"UGC {name.replace('_', ' ').title()}",),
    ).fetchone()
    if row:
        return int(row["id"])
    # Fallback by partial match.
    row = conn.execute(
        "SELECT id FROM templates WHERE LOWER(name) LIKE ? ORDER BY id LIMIT 1",
        (f"%{name.replace('_', ' ')}%",),
    ).fetchone()
    if row:
        return int(row["id"])
    return None


def _publish_progress(event: str, payload: dict[str, Any]) -> None:
    """Best-effort progress publish. Tests stub this."""
    try:
        from app import events

        events.publish(event, payload)
    except Exception:  # noqa: BLE001
        # Events layer isn't always available — fall back silently.
        pass


__all__ = ["parse_brief", "one_shot", "BriefPlan", "KEYWORD_TO_TEMPLATE"]