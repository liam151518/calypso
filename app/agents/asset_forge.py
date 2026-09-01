"""app/agents/asset_forge.py. Mints brand-new references from the brief.

Calls the existing image_jobs pipeline (Phase 0 image generator) to create
references that match the brand's tone and palette. Outputs are saved to
the reference library via `app/refs.py` so future runs can reuse them.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .base import Agent, AgentContext, AgentResult


class AssetForge(Agent):
    name = "asset_forge"
    inputs = ("treatment", "selected_refs")
    outputs = ("forged_refs",)
    description = "Mint brand-new references that match tone + palette."

    def __init__(self, *, n: int = 2):
        # Number of forged references to produce. Capped by max_workers / cost.
        self.n = max(1, min(3, int(n)))

    def run(self, ctx: AgentContext) -> AgentResult:
        self._require(ctx, "treatment")
        treatment = ctx.artifacts["treatment"]
        # Lazy imports. Asset forge may not be wired in the most stripped
        # build (e.g. CI smoke tests). If image_jobs is missing, we just
        # return an empty forge and let the producer handle it.
        try:
            from .. import image_jobs
            from .. import refs as refs_mod
        except Exception as exc:  # noqa: BLE001
            ctx.record(self.name, f"image_jobs unavailable: {exc}; skipping forge")
            ctx.artifacts["forged_refs"] = []
            return AgentResult(outputs={"forged_refs": []})

        brand = ctx.brand or {}
        tone = treatment.get("tone", "")
        promise = treatment.get("promise", "")
        prompt = (
            f"{brand.get('name', '')} brand reference: {tone} tone. "
            f"{promise}. Cinematic lighting, editorial composition."
        ).strip()
        forged: list[dict[str, Any]] = []
        for i in range(self.n):
            try:
                job = image_jobs.create_image_job(
                    prompt=prompt,
                    model="flux-pro/v1.1",
                    aspect_ratio="16:9",
                    num_images=1,
                )
                image_jobs.start_image_job(job)
                # We don't block. Record the job id and move on.
                forged.append({"job_id": job.job_id, "prompt": prompt})
                ctx.spent_usd = float(ctx.spent_usd or 0.0) + float(job.cost_usd or 0.0)
            except Exception as exc:  # noqa: BLE001
                ctx.record(self.name, f"forge #{i+1} failed: {exc}")
        ctx.artifacts["forged_refs"] = forged
        ctx.record(self.name, f"queued {len(forged)} forged refs")
        return AgentResult(outputs={"forged_refs": forged})
