"""Copywriter — Phase F agent 3. Suggests text for each text layer.

Heuristic-first (deterministic, no network). When `model="llm"` is set
in the AgentContext we delegate to `app.captions._llm_variants` for
LLM-generated copy; otherwise we generate from the brief + product +
brand + tone.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, AgentContext, AgentResult


class Copywriter(Agent):
    name = "copywriter"
    inputs = ("tone",)
    outputs = ("layer_copy",)
    description = "Suggest copy for each text layer of a template."

    def run(self, ctx: AgentContext) -> AgentResult:
        director = ctx.artifacts.get("director") or {}
        tone = director.get("tone") or "casual"
        product = (ctx.references or [{}])[0]
        brand = ctx.brand or {}
        # Only suggest copy for templates that have text layers.
        candidates = (ctx.artifacts.get("template_selector") or {}).get("candidates") or []
        layer_copy: dict[str, list[dict[str, Any]]] = {}
        for c in candidates[:3]:
            template = c.get("template") or {}
            template_id = template.get("id")
            if template_id is None:
                continue
            suggestions: list[dict[str, Any]] = []
            for layer in template.get("layers") or []:
                if layer.get("type") != "text":
                    continue
                layer_id = layer.get("id") or layer.get("name") or "text"
                variants = _suggest_for_layer(
                    layer=layer,
                    product=product,
                    brand=brand,
                    tone=tone,
                )
                suggestions.append({
                    "layer_id": layer_id,
                    "variants": variants,
                })
            layer_copy[str(template_id)] = suggestions
        ctx.record(self.name, f"drafted copy for {len(layer_copy)} templates")
        return AgentResult(outputs={"layer_copy": layer_copy})


def _suggest_for_layer(
    *,
    layer: dict,
    product: dict,
    brand: dict,
    tone: str,
) -> list[str]:
    placeholders = _extract_placeholders(layer.get("text") or "")
    if not placeholders:
        # Fall back to a tone-flavored headline.
        return _tone_lines(tone, product, brand)
    # We always emit one variant per placeholder-set; the SPA lets the user
    # accept or override.
    line = _tone_lines(tone, product, brand)[0]
    return [line]


def _extract_placeholders(text: str) -> list[str]:
    import re
    return re.findall(r"\{[a-zA-Z0-9_.]+\}", text)


def _tone_lines(tone: str, product: dict, brand: dict) -> list[str]:
    name = product.get("name") or "this drop"
    voice = brand.get("voice") or brand.get("voice_tone") or "casual"
    pool = {
        "bold": [
            f"{name}. No apologies.",
            f"This is {name}. Don't blink.",
            f"Built loud. {name}.",
        ],
        "minimal": [
            f"{name}.",
            f"{name}. Quietly iconic.",
            f"Less, but {name}.",
        ],
        "playful": [
            f"hi, {name} here!",
            f"{name} just dropped \u2728",
            f"tiny ad for {name}",
        ],
        "luxury": [
            f"{name}. Crafted, considered.",
            f"An object of {name}.",
            f"The {name} edit.",
        ],
        "casual": [
            f"Hey, {name} is here",
            f"Just dropped: {name}",
            f"{name} — thoughts?",
        ],
        "cinematic": [
            f"Enter the world of {name}.",
            f"{name}. A story worth telling.",
            f"Behind {name}.",
        ],
    }
    return pool.get(tone, pool.get(voice, pool["casual"]))


__all__ = ["Copywriter"]