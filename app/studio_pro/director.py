"""Director — Phase F agent 1. Creative treatment for brand posters.

Outputs:
- `tone`: short tone descriptor (e.g. "bold", "minimal", "playful")
- `style`: visual style descriptor (e.g. "high-contrast flat-lay")
- `palette_shift`: small dict of color adjustments to apply on top of brand
- `recommended_platforms`: list[str]
- `recommended_duration_s`: int | None
- `audience`: cleaned-up audience description

The Director does not pick templates or write copy — those are downstream
agents' jobs. We deliberately keep the upstream agent small and reliable.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, AgentContext, AgentResult


KEYWORD_TONE_MAP: dict[str, tuple[str, str]] = {
    "hype": ("bold", "high-contrast streetwear"),
    "luxury": ("luxury", "muted, editorial-grade"),
    "minimal": ("minimal", "flat negative-space"),
    "playful": ("playful", "soft pastels, bouncy type"),
    "tutorial": ("casual", "step-by-step infographic"),
    "review": ("bold", "split-screen verdict"),
    "lifestyle": ("cinematic", "warm ambient lighting"),
    "streetwear": ("bold", "high-contrast streetwear"),
    "fashion": ("luxury", "editorial-grade portrait"),
    "fitness": ("bold", "high-energy motion blur"),
    "food": ("playful", "warm macro still life"),
    "tech": ("minimal", "cool-tone UI screenshot"),
    "beauty": ("luxury", "soft-focus editorial"),
}


PLATFORM_HINTS: dict[str, list[str]] = {
    "tiktok": ["tiktok"],
    "reel": ["instagram", "facebook"],
    "story": ["instagram", "tiktok"],
    "feed": ["instagram", "facebook"],
    "thumbnail": ["youtube"],
    "linkedin": ["linkedin"],
    "twitter": ["x"],
    "x.com": ["x"],
    "reddit": ["reddit"],
}


class Director(Agent):
    name = "director"
    inputs = ()
    outputs = ("tone", "style", "palette_shift", "recommended_platforms",
               "recommended_duration_s", "audience")
    description = "Creative treatment (tone, style, palette, platforms)."

    def run(self, ctx: AgentContext) -> AgentResult:
        text = (ctx.brief or "").lower()
        tone, style = _pick_tone(text)
        platforms = _pick_platforms(text, ctx.brand.get("default_platforms"))
        duration_s = _pick_duration(text)
        audience = _extract_audience(text)
        palette_shift = _palette_shift_for(tone)
        ctx.record(self.name, f"tone={tone}; style={style}; platforms={platforms}")
        return AgentResult(
            outputs={
                "tone": tone,
                "style": style,
                "palette_shift": palette_shift,
                "recommended_platforms": platforms,
                "recommended_duration_s": duration_s,
                "audience": audience,
            }
        )


def _pick_tone(text: str) -> tuple[str, str]:
    for keyword, (tone, style) in KEYWORD_TONE_MAP.items():
        if keyword in text:
            return tone, style
    return "casual", "balanced editorial"


def _pick_platforms(text: str, default: list[str] | None) -> list[str]:
    found: list[str] = []
    for needle, plats in PLATFORM_HINTS.items():
        if needle in text and not any(p in found for p in plats):
            found.extend(plats)
    if not found:
        return list(default) if default else ["instagram"]
    return found


def _pick_duration(text: str) -> int | None:
    # Look for "30s", "15 sec", "1 minute".
    import re
    m = re.search(r"(\d+)\s*(s|sec|secs|second|seconds|m|min|minute|minutes)\b", text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit.startswith("m"):
        return n * 60
    return n


def _extract_audience(text: str) -> str | None:
    import re
    m = re.search(r"for\s+([a-z0-9 ,\-]{4,60})", text)
    if m:
        return m.group(1).strip().rstrip(",.")
    return None


def _palette_shift_for(tone: str) -> dict[str, Any]:
    return {
        "warmth": {"bold": 0.1, "luxury": -0.05, "minimal": -0.1,
                    "playful": 0.2, "casual": 0.0, "cinematic": 0.05}.get(tone, 0.0),
        "saturation": {"bold": 0.2, "luxury": -0.1, "minimal": -0.2,
                        "playful": 0.15, "casual": 0.0, "cinematic": -0.05}.get(tone, 0.0),
    }


__all__ = ["Director"]