"""app/refinement.py. Refinement Studio API for editing generated outputs.

A "version" is a snapshot of (layers_json, filter_settings) tied to a file
on disk. Versions never overwrite the canonical output — they fork it.
``promote_version`` flips the canonical output's ``file_path`` to the
version's file so it becomes the "live" render.

Endpoints exposed by the API (see app/server.py for the wiring):
    POST   /api/outputs/<id>/versions            — create new version
    GET    /api/outputs/<id>/versions            — list versions
    POST   /api/outputs/<id>/versions/<vid>/promote
    DELETE /api/outputs/<id>/versions/<vid>
    POST   /api/outputs/<id>/layers/<idx>/regenerate
    POST   /api/outputs/<id>/upscale
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import db as app_db


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _enrich_rel_url(ver: dict[str, Any]) -> dict[str, Any]:
    """Attach ``rel_url`` to a version row when its file lives under the
    outputs directory. Mirrors the helper used for the canonical output."""
    from .outputs import rel_url_for_path  # local import to avoid cycle
    rel = rel_url_for_path(ver.get("file_path"))
    if rel is not None:
        ver["rel_url"] = rel
    else:
        ver.setdefault("rel_url", None)
    return ver


# ---- versions -----------------------------------------------------------


def create_version(
    output_id: int,
    *,
    layers_json: list[dict] | None,
    filter_settings: dict | None,
    file_path: str,
    thumbnail_path: str | None = None,
    notes: str | None = None,
    cost_usd: float = 0.0,
) -> dict[str, Any]:
    """Persist a new version row. Returns the inserted row."""
    now = time.time()
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO output_versions (
                output_id, layers_json, filter_settings,
                file_path, thumbnail_path, notes,
                cost_usd, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(output_id),
                json.dumps(layers_json or []),
                json.dumps(filter_settings or {}),
                file_path,
                thumbnail_path,
                notes or "",
                float(cost_usd),
                now,
            ),
        )
        vid = int(cur.lastrowid)
        row = c.execute(
            "SELECT * FROM output_versions WHERE id = ?", (vid,)
        ).fetchone()
    return _enrich_rel_url(_row_to_dict(row))


def list_versions(output_id: int) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM output_versions WHERE output_id = ? "
            "ORDER BY created_at DESC",
            (int(output_id),),
        ).fetchall()
    return [_enrich_rel_url(_row_to_dict(r)) for r in rows]


def get_version(version_id: int) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM output_versions WHERE id = ?", (int(version_id),)
        ).fetchone()
    if not row:
        return None
    return _enrich_rel_url(_row_to_dict(row))


def delete_version(version_id: int) -> bool:
    """Remove a version. Returns True if anything was deleted."""
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM output_versions WHERE id = ?", (int(version_id),)
        )
    return cur.rowcount > 0


def promote_version(version_id: int) -> bool:
    """Flip the canonical output's file_path to this version's file.

    The original output row stays; we just overwrite its file_path. The
    previous file_path is *not* automatically archived — callers should
    create a version of the original first if they need history.
    """
    ver = get_version(version_id)
    if not ver:
        return False
    with _conn() as c:
        cur = c.execute(
            "UPDATE outputs SET file_path = ? WHERE id = ?",
            (ver["file_path"], int(ver["output_id"])),
        )
    return cur.rowcount > 0


__all__ = [
    "create_version",
    "list_versions",
    "get_version",
    "delete_version",
    "promote_version",
    "regenerate_layer",
    "upscale_output",
]


# ---- per-layer regeneration --------------------------------------------


def regenerate_layer(
    output_id: int,
    layer_index: int,
    *,
    prompt: str | None = None,
    seed: int | None = None,
    model: str | None = None,
    text_content: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Regenerate one layer of an existing output.

    Behaviour depends on the layer type:
      * ai_background / ai_image — re-renders with new prompt/seed/model
      * text                      — replaces `config.content` with `text_content`
      * image                     — caller must have uploaded + set the path
                                   via `layer["config"]["src"]`; we don't
                                   fabricate a cutout here.

    Returns a dict with the new version row + the layer that was mutated.
    Raises ValueError when the output or layer index is invalid.
    """
    from . import compositor, outputs as outputs_mod

    out = outputs_mod.get_output(output_id)
    if out is None:
        raise ValueError(f"output {output_id} not found")
    layers = list(out.get("layers") or [])
    if layer_index < 0 or layer_index >= len(layers):
        raise ValueError(
            f"layer index {layer_index} out of range (have {len(layers)} layers)"
        )
    layer = dict(layers[layer_index])  # shallow copy
    cfg = dict(layer.get("config") or {})
    ltype = str(layer.get("type") or "")

    mutated = False
    if ltype in ("ai_background", "ai_image"):
        if prompt is not None:
            cfg["prompt"] = prompt
            mutated = True
        if seed is not None:
            cfg["seed"] = int(seed)
            mutated = True
        if model is not None:
            cfg["model"] = model
            mutated = True
    elif ltype == "text":
        if text_content is not None:
            cfg["content"] = text_content
            mutated = True
    else:
        # Image / product / shape — no-op from this endpoint.
        raise ValueError(
            f"layer type {ltype!r} is not regeneratable; "
            "use the upload + replace path"
        )

    if not mutated:
        raise ValueError("no changes specified; pass at least one of "
                         "prompt/seed/model/text_content")

    layer["config"] = cfg
    layers[layer_index] = layer

    # Re-render via the compositor with the patched layers.
    template_id = out.get("template_id")
    if not template_id:
        raise ValueError("output has no template_id; cannot regenerate")
    product_id = out.get("product_id")
    filter_name = (out.get("filter") or {}).get("filter_name")
    intensity = (out.get("filter") or {}).get("intensity", 1.0)

    result = compositor.render(
        template_id=int(template_id),
        product_id=int(product_id) if product_id else None,
        layer_overrides={"layers": layers},
        filter_name=filter_name,
        intensity=float(intensity or 1.0),
        brand_id=out.get("brand_id"),
        cache_hit_only=False,
    )

    # Persist as a new version.
    ver = create_version(
        output_id,
        layers_json=layers,
        filter_settings=out.get("filter") or {},
        file_path=result.file_path,
        notes=notes or f"regenerated layer {layer_index} ({ltype})",
        cost_usd=result.cost_usd,
    )
    return {"version": ver, "layer": layer, "render": result}


# ---- upscale ------------------------------------------------------------


def upscale_output(
    output_id: int,
    *,
    scale: int = 4,
    model: str = "realesrgan",
    face_enhance: bool = False,
    notes: str | None = None,
) -> dict[str, Any]:
    """Upscale the canonical file of an output. Records the result as a
    new version so the original is preserved.

    Raises ValueError when the output doesn't exist.
    """
    from . import upscale as upscale_mod
    from . import outputs as outputs_mod

    out = outputs_mod.get_output(output_id)
    if not out:
        raise ValueError(f"output {output_id} not found")
    file_path = out.get("file_path")
    if not file_path or not Path(str(file_path)).exists():
        raise ValueError(f"output {output_id} has no file on disk at {file_path!r}")

    res = upscale_mod.upscale(
        str(file_path),
        scale=scale,
        model=model,
        face_enhance=face_enhance,
    )
    ver = create_version(
        output_id,
        layers_json=out.get("layers") or [],
        filter_settings=out.get("filter") or {},
        file_path=res.file_path,
        notes=notes or f"upscale x{scale} ({res.model_used})",
        cost_usd=res.cost_usd,
    )
    return {"version": ver, "upscale": res}
