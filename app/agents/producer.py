"""app/agents/producer.py. Topological scheduler for the Studio run.

The producer takes the artifacts produced by upstream agents
(treatment, scenes, shots, selected_refs, forged_refs) and emits a
Pipeline (Phase A) that, when executed, generates the actual media.

It also enforces a budget cap (`treatment['budget_usd']`) via the
existing cost guard. The producer does NOT run the pipeline itself.
The SPA / orchestrator does that with `pipelines.run_pipeline`.
"""

from __future__ import annotations

from typing import Any

from .base import Agent, AgentContext, AgentResult


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in (s or "x")).strip("_")[:32] or "x"


class Producer(Agent):
    name = "producer"
    inputs = ("shots",)
    outputs = ("pipeline",)
    description = "Compile the artifacts into a runnable Pipeline."

    def run(self, ctx: AgentContext) -> AgentResult:
        self._require(ctx, "shots")
        treatment = ctx.artifacts.get("treatment", {})
        shots = ctx.artifacts["shots"]
        budget = float(treatment.get("budget_usd", 25.0) or 25.0)
        selected_refs = ctx.artifacts.get("selected_refs") or []
        forged_refs = ctx.artifacts.get("forged_refs") or []
        brand_id = int(ctx.brand.get("id") or 0) if ctx.brand else 0

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        def add(node: dict[str, Any]) -> str:
            nodes.append(node)
            return node["id"]

        trigger = add({"id": "trigger", "type": "trigger", "params": {"mode": "manual"}})
        brand_node = ""
        if brand_id > 0 or ctx.brand:
            brand_node = add({"id": "brand", "type": "brand",
                              "params": {"brand_id": brand_id}})
            edges.append({"source": trigger, "target": brand_node})

        # Reference node. Combines selected + forged refs into one list.
        ref_node = ""
        ref_ids: list[str] = []
        for r in selected_refs:
            rid = r.get("id") if isinstance(r, dict) else None
            if rid:
                ref_ids.append(rid)
        if ref_ids or forged_refs:
            ref_node = add({"id": "refs", "type": "reference",
                            "params": {"mode": "ids", "ids": ref_ids}})
            if brand_node:
                edges.append({"source": brand_node, "target": ref_node})
            else:
                edges.append({"source": trigger, "target": ref_node})

        # Cost guard wraps every generate node so the run auto-halts on
        # overspend without the user babysitting it.
        guard_node = ""
        if budget > 0:
            guard_node = add({"id": "cost_guard", "type": "cost_guard",
                              "params": {"max_usd": budget}})
            if ref_node:
                edges.append({"source": ref_node, "target": guard_node})
            elif brand_node:
                edges.append({"source": brand_node, "target": guard_node})
            else:
                edges.append({"source": trigger, "target": guard_node})

        # One generate per shot. Shots share the brand + guard nodes.
        prev: str = guard_node or ref_node or brand_node or trigger
        for shot in shots:
            sid = _slug(shot.get("id", "shot"))
            prompt_node = add({"id": f"prompt_{sid}", "type": "prompt",
                               "params": {"mode": "inline",
                                          "body": _shot_prompt(shot, treatment)}})
            model_node = add({"id": f"model_{sid}", "type": "model",
                              "params": {"model_id": "minimax/h3"}})
            gen_node = add({"id": f"gen_{sid}", "type": "generate",
                            "params": {"duration": int(shot.get("duration_s", 6)),
                                       "resolution": "768p"}})
            edges.append({"source": prev, "target": prompt_node})
            edges.append({"source": prompt_node, "target": gen_node})
            edges.append({"source": model_node, "target": gen_node})
            edges.append({"source": guard_node or prev, "target": model_node})
            prev = gen_node

        pipeline = {
            "name": f"studio:{treatment.get('audience', 'campaign')}",
            "description": treatment.get("promise", ""),
            "nodes": nodes,
            "edges": edges,
            "max_workers": 2,
            "enabled": True,
        }
        ctx.artifacts["pipeline"] = pipeline
        ctx.record(self.name, f"compiled pipeline with {len(nodes)} nodes")
        return AgentResult(outputs={"pipeline": pipeline})


def _shot_prompt(shot: dict[str, Any], treatment: dict[str, Any]) -> str:
    parts = [
        f"{shot.get('framing', '')} shot,".strip(),
        f"{shot.get('lens', '')} lens,".strip(),
        f"{shot.get('motion', '')} motion.".strip(),
        shot.get("description", ""),
        f"Tone: {treatment.get('tone', '')}.",
        f"Audience: {treatment.get('audience', '')}.",
    ]
    return " ".join(p for p in parts if p)
