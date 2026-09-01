"""app/agents/director.py. Turns a brief into a brand treatment.

Pure offline implementation: no LLM calls required. Builds a structured
treatment (audience, tone, CTA, budget, format) by combining the brief
text with the active brand profile (if any) and a small set of heuristics.

For users who *do* want an LLM-backed Director, plug a Provider into the
agent pipeline (Phase D). The interface is intentionally tiny so this
swap is a one-liner.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Agent, AgentContext, AgentResult


class Director(Agent):
    name = "director"
    inputs = ()
    outputs = ("treatment",)
    description = "Brand brief to treatment (tone, audience, CTA, budget)."

    # Cheap intent classifier. Recognises common phrases so the treatment
    # actually reflects what the user wrote.
    _AUDIENCE_HINTS = {
        "founder": "early-stage founders",
        "creator": "content creators",
        "shopify": "Shopify merchants",
        "ecommerce": "ecommerce operators",
        "saas": "B2B SaaS teams",
        "agency": "agency owners",
        "indie": "indie hackers",
        "student": "students",
        "parent": "parents",
        "gamer": "gamers",
    }
    _TONE_HINTS = {
        "playful": "playful",
        "edgy": "edgy",
        "premium": "premium",
        "minimal": "minimal",
        "bold": "bold",
        "warm": "warm",
        "cinematic": "cinematic",
    }
    _FORMAT_HINTS = {
        "reel": "vertical 9:16 short",
        "tiktok": "vertical 9:16 short",
        "youtube": "16:9 long-form",
        "ad": "6s vertical ad",
        "story": "9:16 story",
        "carousel": "1:1 carousel",
    }

    def run(self, ctx: AgentContext) -> AgentResult:
        text = (ctx.brief or "").strip()
        lower = text.lower()

        audience = self._match(lower, self._AUDIENCE_HINTS) or "small-business owners"
        tone = self._match(lower, self._TONE_HINTS) or "confident"
        fmt = self._match(lower, self._FORMAT_HINTS) or "16:9 hero spot"
        budget = 25.0 if "small" in lower or "test" in lower else 75.0

        cta = self._extract_cta(text) or "Learn more"
        promise = self._short(text, max_words=18) or "An on-brand creative in minutes."
        risks: list[str] = []
        if "hate" in lower or "controversial" in lower:
            risks.append("tone could read as negative. Soften copy.")

        treatment: dict[str, Any] = {
            "audience": audience,
            "tone": tone,
            "format": fmt,
            "budget_usd": budget,
            "promise": promise,
            "cta": cta,
            "risks": risks,
            "brand_used": ctx.brand.get("name") if ctx.brand else None,
        }
        ctx.artifacts["treatment"] = treatment
        ctx.record(self.name, f"audience={audience} tone={tone} format={fmt}")
        return AgentResult(outputs={"treatment": treatment})

    @staticmethod
    def _match(text: str, table: dict[str, str]) -> str | None:
        for needle, label in table.items():
            if re.search(rf"\b{re.escape(needle)}\b", text):
                return label
        return None

    @staticmethod
    def _extract_cta(text: str) -> str | None:
        # Look for "cta: …" or "call to action: …" markers.
        m = re.search(r"(?:cta|call to action)[:\s]+([^.!\n]+)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip(".")[:60]
        return None

    @staticmethod
    def _short(text: str, max_words: int) -> str:
        words = re.findall(r"\w+", text)
        return " ".join(words[:max_words])
