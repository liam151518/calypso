"""app/pipeline_nodes.py. Concrete runners for every pipeline node type.

Each node type wraps existing Calypso modules so the Phase A pipeline
executor (`app/pipelines.py`) doesn't duplicate business logic. The
contract for a runner:

    run(ctx, params, inputs) -> dict

`ctx` is a dict the executor populates with shared context:
    - `pipeline_id`   int
    - `run_id`        int
    - `log(event)`    callable(str, str) -> None
    - `spent`         dict that runners update with 'usd' additions

`params` are the validated node params.
`inputs` is a dict of upstream outputs keyed by their declared name in
`app/node_schema.NODE_SCHEMAS[...]['outputs']` (plus `'flow'`).

Runners must be **side-effect safe**: they should never raise for
expected inputs (return an empty result instead); only raise for
*programmer errors* (schema mismatch, missing module).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from . import brand as brand_mod
from . import drafts as drafts_mod
from . import image_jobs
from . import jobs
from . import models as models_mod
from . import refs as refs_mod

log = logging.getLogger(__name__)


# --- helpers --------------------------------------------------------------


def _resolve_brand_id(params: dict[str, Any]) -> int:
    """0 means "active brand"."""
    bid = int(params.get("brand_id") or 0)
    if bid <= 0:
        active = brand_mod.get_active_brand()
        if active is not None:
            bid = int(active["id"])
    return bid


# --- runners --------------------------------------------------------------


def run_trigger(ctx: dict, params: dict, inputs: dict) -> dict:
    """Start of every pipeline."""
    ctx["log"]("trigger", f"mode={params.get('mode', 'manual')}")
    return {"flow": True, "mode": params.get("mode", "manual")}


def run_brand(ctx: dict, params: dict, inputs: dict) -> dict:
    """Pull brand context."""
    bid = _resolve_brand_id(params)
    prof = brand_mod.get_brand(bid) if bid > 0 else None
    ctx["log"]("brand", f"id={bid}")
    return {"brand": prof or {}}


def run_reference(ctx: dict, params: dict, inputs: dict) -> dict:
    """Resolve a reference set by id or by tag."""
    mode = params.get("mode", "tag")
    limit = int(params.get("limit", 8) or 8)
    if mode == "ids":
        ids = list(params.get("ids") or [])
        items = []
        for rid in ids:
            ref = refs_mod.resolve_to_path(rid)
            if ref is not None:
                items.append({"id": rid, "path": str(ref)})
    else:
        tag = (params.get("tag") or "").strip()
        if tag:
            refs = refs_mod.list_refs(tag=tag)
        else:
            refs = refs_mod.list_refs()
        items = [{"id": r["filename"], "path": r["path"]} for r in refs[:limit]]
    ctx["log"]("reference", f"mode={mode} count={len(items)}")
    return {"refs": items}


def run_prompt(ctx: dict, params: dict, inputs: dict) -> dict:
    """Pick a prompt draft or write inline."""
    mode = params.get("mode", "draft")
    if mode == "inline":
        body = (params.get("body") or "").strip()
        ctx["log"]("prompt", "inline")
        return {"prompt": body}
    draft_id = int(params.get("draft_id") or 0)
    draft = drafts_mod.get_draft(draft_id) if draft_id > 0 else None
    body = draft["body"] if draft else ""
    ctx["log"]("prompt", f"draft_id={draft_id}")
    return {"prompt": body}


def run_model(ctx: dict, params: dict, inputs: dict) -> dict:
    """Pick a model from the registry."""
    model_id = (params.get("model_id") or models_mod.default_video_model_id()).strip()
    spec = models_mod.get_model(model_id) or models_mod.get_model(models_mod.default_video_model_id())
    ctx["log"]("model", f"id={model_id}")
    return {"model": spec}


def run_cost_guard(ctx: dict, params: dict, inputs: dict) -> dict:
    """Stop the run if estimated cost is too high. We don't fail. We just
    set `flow` to False so downstream nodes can no-op."""
    max_usd = float(params.get("max_usd", 5.0) or 5.0)
    est = float(inputs.get("cost_estimate", 0.0) or 0.0)
    proceed = est <= max_usd
    ctx["log"]("cost_guard", f"est=${est:.3f} cap=${max_usd:.3f} proceed={proceed}")
    return {"flow": proceed, "cost_estimate": est}


def run_generate(ctx: dict, params: dict, inputs: dict) -> dict:
    """Submit a video job."""
    prompt_text = inputs.get("prompt") or ""
    model = inputs.get("model") or {}
    if isinstance(model, dict):
        model_id = (
            model.get("id")
            or model.get("model_id")
            or models_mod.default_video_model_id()
        )
    else:
        # ModelSpec dataclass
        model_id = getattr(model, "id", None) or getattr(model, "model_id", None) or models_mod.default_video_model_id()
    refs = inputs.get("refs") or []
    ref_ids = [r.get("id") for r in refs if isinstance(r, dict) and r.get("id")]
    brand_ctx = inputs.get("brand") or {}
    body = prompt_text
    if brand_ctx and brand_ctx.get("name"):
        body = f"[Brand: {brand_ctx['name']}]\n{body}"
    duration = int(params.get("duration", 8) or 8)
    resolution = str(params.get("resolution", "768p") or "768p")

    job = jobs.create_job(
        prompt=body,
        model=model_id,
        duration=duration,
        resolution=resolution,
        ref_ids=ref_ids,
        brand_id=int(brand_ctx.get("id") or 0) or None,
    )
    ctx["log"]("generate", f"job_id={job.job_id} model={model_id}")
    return {"video_job": job.to_dict()}


def run_image(ctx: dict, params: dict, inputs: dict) -> dict:
    """Submit an image job."""
    prompt_text = inputs.get("prompt") or ""
    model = inputs.get("model") or {}
    if isinstance(model, dict):
        model_id = (
            model.get("id")
            or model.get("model_id")
            or models_mod.default_image_model_id()
        )
    else:
        model_id = getattr(model, "id", None) or getattr(model, "model_id", None) or models_mod.default_image_model_id()
    refs = inputs.get("ref_ids") or inputs.get("refs") or []
    ref_id = refs[0] if refs else None
    job = image_jobs.create_image_job(
        prompt=prompt_text,
        model=model_id,
        aspect_ratio=str(params.get("aspect_ratio", "1:1") or "1:1"),
        num_images=int(params.get("num_images", 1) or 1),
        reference=ref_id,
    )
    ctx["log"]("image", f"job_id={job.job_id} model={model_id}")
    return {"image_job": job.to_dict()}


def run_combine(ctx: dict, params: dict, inputs: dict) -> dict:
    """Combine upstream outputs. v1 is a logical operation only. The SPA
    shows a single combined card pointing at the latest video_job."""
    upstream = inputs.get("video_job") or inputs.get("combined") or {}
    ctx["log"]("combine", f"mode={params.get('mode', 'concat')} upstream={upstream.get('id', 'none')}")
    return {"combined": upstream}


def run_export(ctx: dict, params: dict, inputs: dict) -> dict:
    """Persist the produced media. Outputs are already on disk. We just
    surface their public URLs."""
    upstream = (
        inputs.get("video_job")
        or inputs.get("image_job")
        or inputs.get("combined")
        or {}
    )
    url = upstream.get("output_url") or upstream.get("video_url") or ""
    ctx["log"]("export", f"destination={params.get('destination', 'outputs')} url={bool(url)}")
    return {"exported_url": url}


NODE_RUNNERS: dict[str, Callable[[dict, dict, dict], dict]] = {
    "trigger": run_trigger,
    "brand": run_brand,
    "reference": run_reference,
    "prompt": run_prompt,
    "model": run_model,
    "cost_guard": run_cost_guard,
    "generate": run_generate,
    "image": run_image,
    "combine": run_combine,
    "export": run_export,
}


def runner_for(node_type: str) -> Callable[[dict, dict, dict], dict] | None:
    return NODE_RUNNERS.get(node_type)
