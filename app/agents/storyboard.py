"""app/agents/storyboard.py. Scene list to shot list with cinematography.

Each scene becomes one or more shots with framing, lens, and motion notes.
The producer turns shots into actual prompts via the prompt_builder.
"""

from __future__ import annotations

from typing import Any

from .base import Agent, AgentContext, AgentResult


# Simple deterministic mapping: slug → default camera setup.
_DEFAULT_CAMERA = {
    "hook": ("medium", "35mm", "push-in"),
    "problem": ("wide", "24mm", "static"),
    "promise": ("medium close-up", "50mm", "slow dolly"),
    "proof": ("close-up", "85mm", "static"),
    "cta": ("medium", "35mm", "static"),
}


class Storyboard(Agent):
    name = "storyboard"
    inputs = ("scenes",)
    outputs = ("shots",)
    description = "Scenes → shot list (framing, lens, motion)."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._require(ctx, "scenes")
        shots: list[dict[str, Any]] = []
        shot_idx = 0
        for scene in ctx.artifacts["scenes"]:
            duration = int(scene.get("duration_s", 3) or 3)
            # 1 shot per 3s of scene is a good default.
            n_shots = max(1, duration // 3 + (1 if duration % 3 else 0))
            slug = scene.get("slug", "")
            framing, lens, motion = _DEFAULT_CAMERA.get(
                slug, ("medium", "35mm", "static"),
            )
            for i in range(n_shots):
                shot_idx += 1
                shots.append({
                    "id": f"shot_{shot_idx:02d}",
                    "scene_index": scene["index"],
                    "framing": framing,
                    "lens": lens,
                    "motion": motion,
                    "duration_s": max(2, duration // n_shots),
                    "description": scene.get("description", ""),
                    "tone": scene.get("tone"),
                })
        ctx.artifacts["shots"] = shots
        ctx.record(self.name, f"{len(shots)} shots across "
                    f"{len(ctx.artifacts['scenes'])} scenes")
        return AgentResult(outputs={"shots": shots})
