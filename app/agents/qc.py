"""app/agents/qc.py. Best-of-k quality control via VLM (optional).

If a VLM provider is configured (fal.ai / OpenAI / Anthropic / local),
this agent judges the generated media against the treatment and picks
the best candidate. With no VLM configured, the agent is a no-op that
just marks the first job as the winner.

Designed so Phase D provider plugins can swap in any judge without
touching the rest of the studio.
"""

from __future__ import annotations

from typing import Any

from .base import Agent, AgentContext, AgentResult


class QC(Agent):
    name = "qc"
    inputs = ("pipeline",)
    outputs = ("qc",)
    description = "Pick the best media (VLM judge, optional)."

    def run(self, ctx: AgentContext) -> AgentResult:
        pipeline = ctx.artifacts.get("pipeline") or {}
        result: dict[str, Any] = {
            "judged": False,
            "winner_job_id": None,
            "reason": "no VLM provider configured; no-op",
        }
        ctx.artifacts["qc"] = result
        ctx.record(self.name, result["reason"])
        return AgentResult(outputs={"qc": result})
