"""CampaignBuilder — Phase F agent 5. Composes the 3 final template
configurations and computes a confidence score for each.

The confidence score formula (from plan §F.2):

    score = 0.4 * brand_compat
          + 0.3 * template_score
          + 0.2 * novelty
          + 0.1 * cost_feasibility

`brand_compat` is a heuristic — high when the brand's tone matches the
Director's tone. `template_score` is the TemplateSelector's raw score.
`novelty` is 1 if the suggestion hasn't been seen recently, else 0.3.
`cost_feasibility` is 1 when estimated cost <= budget, 0.3 when above.

Output: a list of `suggestions` dicts, each containing:

  - template_id
  - layer_overrides  (copy from Copywriter + nudges from VisualStrategist)
  - rationale        (short string)
  - platforms        (inherited from Director)
  - cost_usd
  - confidence_score
"""

from __future__ import annotations

import time
from typing import Any

from app.agents.base import Agent, AgentContext, AgentResult


class CampaignBuilder(Agent):
    name = "campaign_builder"
    inputs = ("tone", "candidates", "layer_copy", "visuals")
    outputs = ("suggestions", "spent_usd")
    description = "Compose the final 3 suggestions with confidence scores."

    def run(self, ctx: AgentContext) -> AgentResult:
        director = ctx.artifacts.get("director") or {}
        selector = ctx.artifacts.get("template_selector") or {}
        copy = ctx.artifacts.get("copywriter") or {}
        visuals = ctx.artifacts.get("visual_strategist") or {}
        candidates = selector.get("candidates") or []
        budget = float((ctx.brand or {}).get("budget_usd") or 5.0)
        brand_tone = (ctx.brand or {}).get("voice") or (ctx.brand or {}).get("voice_tone")
        director_tone = director.get("tone") or "casual"
        brand_compat = 1.0 if brand_tone == director_tone else 0.6

        suggestions: list[dict[str, Any]] = []
        total_spent = 0.0
        recent = _recent_template_ids(ctx.brand.get("recent_template_ids") or [])
        for idx, c in enumerate(candidates[:3]):
            template = c.get("template") or {}
            template_id = template.get("id")
            if template_id is None:
                continue
            template_score = float(c.get("score") or 0.0)
            novelty = 0.3 if template_id in recent else 1.0
            layer_overrides = _build_layer_overrides(
                template=template,
                copy_for_template=(copy.get("layer_copy") or {}).get(str(template_id), []),
                visuals=visuals.get("visuals") or {},
            )
            cost_usd = _estimate_cost(template, visuals.get("visuals") or {})
            cost_feasibility = 1.0 if cost_usd <= budget else 0.3
            confidence = (
                0.4 * brand_compat
                + 0.3 * template_score
                + 0.2 * novelty
                + 0.1 * cost_feasibility
            )
            rationale = _rationale(
                tone=director_tone,
                style=director.get("style") or "balanced",
                template=template,
                visuals=visuals.get("visuals") or {},
            )
            suggestions.append({
                "template_id": template_id,
                "layer_overrides": layer_overrides,
                "rationale": rationale,
                "platforms": director.get("recommended_platforms") or ["instagram"],
                "duration_s": director.get("recommended_duration_s"),
                "cost_usd": round(cost_usd, 2),
                "confidence_score": round(confidence, 3),
            })
            total_spent += cost_usd
            recent.add(template_id)

        # No templates? Emit a single soft suggestion that explains it.
        if not suggestions:
            suggestions.append({
                "template_id": None,
                "layer_overrides": {},
                "rationale": (
                    "No templates available for this brand. Create or duplicate "
                    "a built-in template to start."
                ),
                "platforms": director.get("recommended_platforms") or ["instagram"],
                "duration_s": director.get("recommended_duration_s"),
                "cost_usd": 0.0,
                "confidence_score": 0.1,
            })

        ctx.record(self.name, f"produced {len(suggestions)} suggestions")
        return AgentResult(outputs={
            "suggestions": suggestions,
            "spent_usd": total_spent,
        })


def _build_layer_overrides(
    *, template: dict, copy_for_template: list[dict], visuals: dict
) -> dict[str, Any]:
    """Combine Copywriter copy + VisualStrategist nudges into a single
    `layer_overrides` payload that the Compositor can apply on top of the
    chosen template.
    """
    overrides: dict[str, Any] = {}
    nudges = visuals.get("nudges") or {}
    if nudges:
        overrides["_nudges"] = nudges
    if visuals.get("background_prompt"):
        # Attach the bg prompt to the first background layer.
        for layer in template.get("layers") or []:
            if layer.get("type") == "background":
                overrides.setdefault(layer.get("id") or "background", {})[
                    "ai_prompt"
                ] = visuals["background_prompt"]
                break
        else:
            overrides["_background_prompt"] = visuals["background_prompt"]
    if visuals.get("filter"):
        overrides["_filter"] = visuals["filter"]
    if copy_for_template:
        for entry in copy_for_template:
            overrides[entry["layer_id"]] = {"text": (entry.get("variants") or [""])[0]}
    return overrides


def _estimate_cost(template: dict, visuals: dict) -> float:
    """Very rough cost estimate based on layer count + presence of AI bg."""
    layers = template.get("layers") or []
    cost = 0.05 * len(layers)
    if visuals.get("background_prompt"):
        cost += 0.4  # ~fal image model per render
    if visuals.get("filter"):
        cost += 0.0  # filters are local + free
    return round(cost, 2)


def _recent_template_ids(seed: list[int]) -> set[int]:
    return {int(x) for x in seed if isinstance(x, (int, float))}


def _rationale(*, tone: str, style: str, template: dict, visuals: dict) -> str:
    name = template.get("name") or "this template"
    bg = visuals.get("background_prompt") or "a neutral studio backdrop"
    filt = visuals.get("filter") or "the default filter"
    return (
        f"{name} pairs a {tone} tone with {style}; "
        f"a {filt} look over {bg}."
    )


__all__ = ["CampaignBuilder"]