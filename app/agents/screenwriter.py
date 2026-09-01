"""app/agents/screenwriter.py. Treatment to scene list.

Splits the brief into a small, ordered list of scenes. Each scene has a
slug, a 1-2 sentence description, and a duration estimate. The producer
turns each scene into one or more shots.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Agent, AgentContext, AgentResult

# Heuristic "beats" every brand spot benefits from.
DEFAULT_BEATS = [
    ("hook", "Stop the scroll with a single bold visual.", 2),
    ("problem", "Name the pain the audience is already feeling.", 3),
    ("promise", "Show the product / brand delivering on the promise.", 3),
    ("proof", "Quick credibility beat: a stat, a quote, a reference.", 3),
    ("cta", "Direct call to action, single beat.", 2),
]


class Screenwriter(Agent):
    name = "screenwriter"
    inputs = ("treatment",)
    outputs = ("scenes",)
    description = "Treatment to ordered list of scenes with durations."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._require(ctx, "treatment")
        treatment = ctx.artifacts["treatment"]
        brief = ctx.brief or treatment.get("promise", "")
        # If the user wrote explicit beats in the brief, prefer them.
        explicit = self._parse_explicit_beats(brief)
        beats = explicit if explicit else DEFAULT_BEATS
        scenes: list[dict[str, Any]] = []
        for i, (slug, template, dur) in enumerate(beats, start=1):
            scenes.append({
                "index": i,
                "slug": slug,
                "description": template,
                "duration_s": int(dur),
                "tone": treatment.get("tone"),
            })
        ctx.artifacts["scenes"] = scenes
        ctx.record(self.name, f"{len(scenes)} scenes")
        return AgentResult(outputs={"scenes": scenes})

    @staticmethod
    def _parse_explicit_beats(text: str) -> list[tuple[str, str, int]] | None:
        """Recognise a `beat list` like:
            1. Hook: opening visual (2s)
            2. Problem: name the pain (3s)
        If anything recognisable is found, return it. Otherwise None."""
        out: list[tuple[str, str, int]] = []
        for line in text.splitlines():
            m = re.match(r"\s*\d+\.\s+([\w\- ]+)\s*[\-—:]\s*(.+?)(?:\((\d+)\s*s\))?\s*$", line)
            if m:
                slug = m.group(1).strip().lower().replace(" ", "_")
                desc = m.group(2).strip()
                dur = int(m.group(3)) if m.group(3) else 3
                out.append((slug, desc, dur))
        return out or None
