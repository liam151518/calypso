"""app/agents/reference_selector.py. Picks references from the library.

v1 uses simple tag-overlap scoring (no embeddings required, works
offline). Optional embeddings hook via sentence-transformers when the
optional dependency is installed (Phase D provider pattern: the embedder
is just another agent).
"""

from __future__ import annotations

import re
from typing import Any

from .base import Agent, AgentContext, AgentResult


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"\w+", text or "") if len(w) > 2}


def _ref_tags(ref: dict[str, Any]) -> set[str]:
    raw = ref.get("tags") or []
    if isinstance(raw, str):
        raw = [t.strip() for t in raw.split(",") if t.strip()]
    return {t.lower() for t in raw}


def _ref_id(ref: dict[str, Any]) -> str:
    return ref.get("id") or ref.get("filename") or ref.get("path") or ""


class ReferenceSelector(Agent):
    name = "reference_selector"
    inputs = ("treatment",)
    outputs = ("selected_refs",)
    description = "Pick references from the library by tag-overlap scoring."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._require(ctx, "treatment")
        brief_tokens = _tokens(ctx.brief)
        treatment = ctx.artifacts["treatment"]
        treatment_tokens = _tokens(" ".join([
            treatment.get("audience", ""),
            treatment.get("tone", ""),
            treatment.get("format", ""),
            treatment.get("promise", ""),
        ]))
        scored: list[tuple[int, dict[str, Any]]] = []
        for ref in ctx.references:
            tags = _ref_tags(ref)
            score = len(brief_tokens & tags) * 2 + len(treatment_tokens & tags)
            if score > 0:
                scored.append((score, ref))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [r for _, r in scored[:5]]
        if not selected and ctx.references:
            selected = ctx.references[:3]  # fall back to first three
        ctx.artifacts["selected_refs"] = [
            {"id": _ref_id(r), "tags": sorted(_ref_tags(r)), "score": s}
            for s, r in [(s, r) for s, r in scored[:5]]
        ] or ctx.artifacts.get("selected_refs", [])
        ctx.record(self.name, f"selected {len(selected)} refs")
        return AgentResult(outputs={"selected_refs": selected})
