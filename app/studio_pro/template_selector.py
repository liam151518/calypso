"""TemplateSelector — Phase F agent 2. Rank templates by tag-match +
brand-compat. Outputs a scored, sorted list of candidate templates.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, AgentContext, AgentResult


CATEGORY_HINTS: dict[str, list[str]] = {
    "hype": ["ugc", "launch", "bold"],
    "luxury": ["lifestyle", "minimal", "cinematic"],
    "minimal": ["minimal", "lifestyle"],
    "playful": ["ugc", "casual"],
    "tutorial": ["tutorial", "ugc"],
    "review": ["ugc", "review"],
    "lifestyle": ["lifestyle", "cinematic"],
    "unboxing": ["ugc", "unboxing"],
}


class TemplateSelector(Agent):
    name = "template_selector"
    inputs = ("tone",)
    outputs = ("candidates",)
    description = "Rank templates by tone + brand compatibility."

    def run(self, ctx: AgentContext) -> AgentResult:
        tone = (ctx.artifacts.get("director") or {}).get("tone") or "casual"
        templates = list(ctx.brand.get("templates") or [])
        # If the caller didn't pass templates, we can fall back to a placeholder
        # list — the next agent (Copywriter) handles missing-template cases.
        if not templates:
            candidates = []
            ctx.record(self.name, "no templates available; using empty list")
            return AgentResult(outputs={"candidates": candidates})

        wanted = CATEGORY_HINTS.get(tone, [])
        scored: list[dict[str, Any]] = []
        for t in templates:
            score = _score_template(t, tone=tone, wanted_categories=wanted)
            scored.append({"template": t, "score": score})
        scored.sort(key=lambda c: c["score"], reverse=True)
        top = scored[:5]
        ctx.record(self.name, f"selected {len(top)} candidate templates")
        return AgentResult(outputs={"candidates": top})


def _score_template(template: dict, *, tone: str, wanted_categories: list[str]) -> float:
    score = 0.0
    category = (template.get("category") or "").lower()
    if category in wanted_categories:
        score += 0.5
    name = (template.get("name") or "").lower()
    if tone in name:
        score += 0.3
    if template.get("brand_id") is None or template.get("is_builtin"):
        # Built-ins and brand-agnostic templates get a small bonus.
        score += 0.1
    layers = template.get("layers") or []
    if any(layer.get("type") == "text" for layer in layers):
        score += 0.1
    return min(1.0, score)


__all__ = ["TemplateSelector"]