"""app.presets. Phase G.1 — brand-poster preset CRUD + apply.

A preset freezes a "winning" template + filter + product filter + caption
template + schedule so the user can re-run a known-good combination
without rebuilding it. The Compositor renders each preset against a
list of product ids and writes one row per render into `outputs`.

The `batch_apply` variant returns a dict so the SPA can show progress
without polling. It does **not** write to the scheduler queue — Phase G.8
chains those via automation rules + telegram approval.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app import db as app_db
from app import templates as tpl_mod
from app import products as products_mod
from app import compositor as compositor_mod


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create(
    brand_id: int | None,
    *,
    name: str,
    description: str | None = None,
    template_id: int | None = None,
    layers: list[dict] | None = None,
    filter_name: str | None = None,
    caption_template: str | None = None,
    schedule_settings: dict | None = None,
    product_filter: dict | None = None,
) -> int:
    if not name.strip():
        raise ValueError("preset name required")
    conn = app_db.get_conn()
    cur = conn.execute(
        """INSERT INTO presets(brand_id, name, description, template_id,
                                layers_json, filter, caption_template,
                                schedule_settings_json, product_filter_json,
                                created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            brand_id,
            name.strip(),
            description,
            template_id,
            json.dumps(layers or []),
            filter_name,
            caption_template,
            json.dumps(schedule_settings or {}),
            json.dumps(product_filter or {}),
            time.time(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def get(preset_id: int) -> dict | None:
    conn = app_db.get_conn()
    row = conn.execute(
        "SELECT * FROM presets WHERE id = ?", (preset_id,)
    ).fetchone()
    return _row(row) if row else None


def list_for_brand(brand_id: int | None) -> list[dict]:
    conn = app_db.get_conn()
    if brand_id is None:
        rows = conn.execute(
            "SELECT * FROM presets ORDER BY created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM presets WHERE brand_id = ? "
            "ORDER BY created_at DESC",
            (brand_id,),
        ).fetchall()
    return [_row(r) for r in rows]


def update(preset_id: int, **fields) -> dict | None:
    """Update a preset in place. Whitelisted columns only."""
    allowed = {
        "name", "description", "template_id", "filter", "caption_template",
    }
    json_fields = {
        "layers": "layers_json",
        "schedule_settings": "schedule_settings_json",
        "product_filter": "product_filter_json",
    }
    sets: list[str] = []
    values: list[Any] = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            values.append(v)
        elif k in json_fields:
            sets.append(f"{json_fields[k]} = ?")
            values.append(json.dumps(v or ({} if k != "layers" else [])))
    if not sets:
        return get(preset_id)
    values.append(preset_id)
    conn = app_db.get_conn()
    conn.execute(f"UPDATE presets SET {', '.join(sets)} WHERE id = ?", values)
    conn.commit()
    return get(preset_id)


def delete(preset_id: int) -> bool:
    conn = app_db.get_conn()
    cur = conn.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _products_matching(product_filter: dict, brand_id: int | None) -> list[dict]:
    """Resolve which products this preset should render against.

    The product_filter shape is intentionally tiny:
        {"category": "shoes", "tag": "limited"}
    Missing filters mean "all products in this brand" (or all products
    if brand_id is also None).
    """
    pool = products_mod.list_products(brand_id=brand_id)
    if not product_filter:
        return pool
    cat = (product_filter.get("category") or "").strip().lower()
    tag = (product_filter.get("tag") or "").strip().lower()
    out = []
    for p in pool:
        if cat and (p.get("category") or "").lower() != cat:
            continue
        if tag:
            tags = [t.lower() for t in (p.get("tags") or [])]
            if tag not in tags:
                continue
        out.append(p)
    return out


def apply(preset_id: int, product_ids: list[int]) -> list[int]:
    """Render this preset against each product id. Returns output ids.

    Layer overrides from the preset are layered onto the preset's
    template before rendering.
    """
    preset = get(preset_id)
    if preset is None:
        raise ValueError(f"preset {preset_id} not found")
    template_id = preset.get("template_id")
    if not template_id:
        return []
    template = tpl_mod.get_template(int(template_id))
    if template is None:
        return []
    layers_overrides = preset.get("layers") or []
    if layers_overrides:
        template = _apply_layer_overrides(template, layers_overrides)

    output_ids: list[int] = []
    for pid in product_ids:
        product = products_mod.get_product(int(pid))
        if product is None:
            continue
        result = compositor_mod.render(
            int(template_id),
            product_id=int(pid),
            brand_id=preset.get("brand_id"),
            filter_name=preset.get("filter"),
            template_override=template,
        )
        output_ids.append(result.output_id)
    return output_ids


def batch_apply(preset_id: int, product_ids: list[int]) -> dict:
    """Like `apply`, but returns a summary dict suitable for the SPA."""
    try:
        ids = apply(preset_id, product_ids)
    except ValueError as exc:
        return {"scheduled": 0, "queued": 0, "errors": [str(exc)]}
    return {
        "scheduled": 0,
        "queued": len(ids),
        "output_ids": ids,
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_layer_overrides(template: dict, overrides: list[dict]) -> dict:
    """Merge a list of {id, ...} overrides onto template.layers by id.

    Overrides don't replace the whole layer — they patch individual
    properties (text, x/y, opacity, color).
    """
    layers = [dict(layer) for layer in template.get("layers") or []]
    by_id = {str(o.get("id")): o for o in overrides if o.get("id") is not None}
    for layer in layers:
        if str(layer.get("id")) in by_id:
            layer.update(by_id[str(layer["id"])])
    return {**template, "layers": layers}


def _row(row) -> dict:
    d = dict(row)
    for k_in, k_out in (
        ("layers_json", "layers"),
        ("schedule_settings_json", "schedule_settings"),
        ("product_filter_json", "product_filter"),
    ):
        raw = d.get(k_in)
        if isinstance(raw, str):
            try:
                d[k_out] = json.loads(raw)
            except json.JSONDecodeError:
                d[k_out] = [] if k_out == "layers" else {}
        d.pop(k_in, None)
    return d


__all__ = [
    "create",
    "get",
    "list_for_brand",
    "update",
    "delete",
    "apply",
    "batch_apply",
]