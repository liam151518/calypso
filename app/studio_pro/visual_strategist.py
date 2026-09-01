"""VisualStrategist — Phase F agent 4. Picks background prompt + filter +
small layout tweaks (x/y nudges) based on the Director's tone.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, AgentContext, AgentResult


FILTER_BY_TONE: dict[str, str] = {
    "bold": "neon",
    "minimal": "minimal",
    "playful": "bright",
    "luxury": "vintage",
    "casual": "bright",
    "cinematic": "moody",
}


LAYOUT_NUDGES: dict[str, dict[str, float]] = {
    "bold": {"headline_y_shift": -0.05, "product_scale": 0.05},
    "minimal": {"headline_y_shift": 0.0, "product_scale": -0.05},
    "playful": {"headline_y_shift": 0.02, "product_scale": 0.05},
    "luxury": {"headline_y_shift": -0.02, "product_scale": 0.0},
    "casual": {"headline_y_shift": 0.0, "product_scale": 0.0},
    "cinematic": {"headline_y_shift": -0.03, "product_scale": 0.02},
}


class VisualStrategist(Agent):
    name = "visual_strategist"
    inputs = ("tone",)
    outputs = ("visuals",)
    description = "Background prompt + filter + layout nudges."

    def run(self, ctx: AgentContext) -> AgentResult:
        director = ctx.artifacts.get("director") or {}
        tone = director.get("tone") or "casual"
        product = (ctx.references or [{}])[0]
        bg_prompt = _background_prompt(tone, product)
        filter_name = FILTER_BY_TONE.get(tone, "bright")
        nudges = dict(LAYOUT_NUDGES.get(tone, {}))
        ctx.record(self.name, f"filter={filter_name}; bg='{bg_prompt}'")
        return AgentResult(outputs={
            "visuals": {
                "background_prompt": bg_prompt,
                "filter": filter_name,
                "nudges": nudges,
            }
        })


def _background_prompt(tone: str, product: dict) -> str:
    name = product.get("name") or "product"
    return {
        "bold": f"high-contrast editorial scene with {name}, neon rim light",
        "minimal": f"soft beige studio backdrop, {name} centered, negative space",
        "playful": f"pastel cloudscape with {name} floating in soft daylight",
        "luxury": f"marble pedestal with {name}, warm candlelight, editorial photography",
        "casual": f"bright indoor studio, {name} on a wooden tabletop",
        "cinematic": f"sunset cinematic backdrop with {name} in silhouette",
    }.get(tone, f"studio shot of {name}")


__all__ = ["VisualStrategist"]