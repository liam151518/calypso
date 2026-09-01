"""app/templates.py. Template engine for the brand-poster surface (Phase A).

A template is a JSON layer stack (see spec §4.1). Built-in templates live as
JSON files in `templates/builtin/` and are inserted into the `templates` table
on first boot via `load_builtins()`. Custom templates are user-created and
editable. Built-in templates are read-only unless `force=True`.

Layer composition is handled separately by `app.compositor`. This module is
strictly the data layer: validation, persistence, substitution, and listing.

Jinja substitution covers `{{product.name}}`, `{{product.price}}`, `{{brand.*}}`,
and `{{palette.primary}}` style lookups. Substitution is non-recursive and
silently leaves unknown tokens in place so the operator can see what was missed.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Iterable

from app import db as app_db
from app.utils import (
    ASPECT_RATIOS,
    LAYER_TYPES,
    TemplateError,
    coerce_template,
    validate_template,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILTIN_DIR = PROJECT_ROOT / "templates" / "builtin"
BUILTIN_PREVIEW_DIR = BUILTIN_DIR / "preview"

# {{product.name}}, {{product.price}}, {{brand.tagline}}, {{palette[0]}}, etc.
_SUB_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_\.\[\]0-9]+)\s*\}\}")


# ---------- low-level row helpers ----------

def _row_to_template(row) -> dict:
    d = dict(row)
    for k in ("layers_json", "brand_locks_json", "scenes_json", "transitions_json"):
        if k in d and isinstance(d[k], str):
            try:
                d[k.replace("_json", "")] = json.loads(d[k] or "[]")
            except json.JSONDecodeError:
                d[k.replace("_json", "")] = []
            d.pop(k, None)
    if "audio_track_json" in d:
        raw = d.pop("audio_track_json")
        if raw:
            try:
                d["audio_track"] = json.loads(raw)
            except json.JSONDecodeError:
                d["audio_track"] = None
        else:
            d["audio_track"] = None
    for bool_field in ("is_builtin", "is_custom"):
        if bool_field in d:
            d[bool_field] = bool(d[bool_field])
    return d


def _template_to_columns(t: dict) -> dict:
    """Split a template dict into the columns the `templates` table stores.

    Accepts both shapes — a nested `canvas: {width, height}` (validator shape)
    and flat `canvas_w/canvas_h` fields (row-reader shape). Caller is
    responsible for stripping row-only fields like `brand_id`/`is_builtin`.

    Video-specific fields (`scenes`, `transitions`, `format`, etc.) are
    returned as additional keys but only persist if the column exists in the
    target schema — see `_persist_columns`.
    """
    cw = t.get("canvas_w")
    ch = t.get("canvas_h")
    if (cw is None or ch is None) and isinstance(t.get("canvas"), dict):
        cw = t["canvas"].get("width")
        ch = t["canvas"].get("height")
    return {
        "name": t["name"],
        "category": t.get("category"),
        "aspect_ratio": t.get("aspect_ratio", "4:5"),
        "canvas_w": int(cw),
        "canvas_h": int(ch),
        "layers_json": json.dumps(t.get("layers") or []),
        "brand_locks_json": json.dumps(t.get("brand_locks") or []),
        "default_filter": t.get("default_filter"),
        "ai_prompt_template": t.get("ai_prompt_template"),
        "preview_path": t.get("preview_path"),
        "scenes_json": json.dumps(t.get("scenes") or []),
        "transitions_json": json.dumps(t.get("transitions") or []),
        "audio_track_json": (
            json.dumps(t["audio_track"]) if t.get("audio_track") else None
        ),
        "duration_s": int(t.get("duration_s") or 0),
        "fps": int(t.get("fps") or 30),
        "format": t.get("format") or ("video" if t.get("scenes") else "image"),
    }


def _persist_columns(cols: dict) -> dict:
    """Filter a `_template_to_columns` result down to columns that actually
    exist on the current `templates` table. This keeps the call sites
    identical whether the migration has run or not — older schemas
    (without the Phase D video columns) silently ignore the extras.
    """
    target = app_db.get_conn()
    existing = {
        row[1]
        for row in target.execute("PRAGMA table_info(templates)").fetchall()
    }
    return {k: v for k, v in cols.items() if k in existing}


def _strip_row_only_fields(t: dict) -> dict:
    """Drop columns that exist on the `templates` row but aren't in the schema
    (so the validator accepts the dict when round-tripping)."""
    return {k: v for k, v in t.items() if k not in {
        "id", "brand_id", "is_builtin", "is_custom",
        "parent_template_id", "created_at", "preview_path",
        "scenes_json", "transitions_json", "audio_track_json",
        "duration_s", "fps", "format",
    }}


# ---------- CRUD ----------

def validate(t: Any) -> dict:
    """Public schema validator re-export."""
    return validate_template(t)


def create_template(t: dict, brand_id: int | None = None) -> int:
    """Validate and insert a new custom template. Returns the new id."""
    t = coerce_template(t)
    if not t.get("scenes"):
        # Only the static (image) path goes through the JSON-schema validator.
        # Video templates carry `scenes` instead of `layers` and bypass that.
        validate_template(t)
    cols = _persist_columns(_template_to_columns(t))
    now = time.time()
    conn = app_db.get_conn()
    columns = ["brand_id"] + list(cols.keys()) + ["is_builtin", "is_custom", "created_at"]
    placeholders = ",".join(["?"] * len(columns))
    values: list[Any] = [brand_id]
    values.extend(cols[k] for k in cols.keys())
    values.extend([0, 1, now])
    cur = conn.execute(
        f"INSERT INTO templates({','.join(columns)}) VALUES ({placeholders})",
        tuple(values),
    )
    return int(cur.lastrowid)


def update_template(template_id: int, patch: dict, *, force: bool = False) -> bool:
    """Partial update. Refuses to touch built-in templates unless `force=True`."""
    conn = app_db.get_conn()
    row = conn.execute(
        "SELECT is_builtin FROM templates WHERE id = ?", (template_id,)
    ).fetchone()
    if row is None:
        return False
    if bool(row["is_builtin"]) and not force:
        raise TemplateError("built-in templates are read-only (use force=True to override)")

    existing = get_template(template_id)
    if existing is None:
        return False
    # Reconstruct a validator-shaped dict from the row (which has canvas_w/h flat).
    merged = {**existing, **patch}
    if "canvas_w" in merged or "canvas_h" in merged:
        merged.setdefault("canvas", {"width": merged.get("canvas_w", 1080),
                                      "height": merged.get("canvas_h", 1350)})
    merged = _strip_row_only_fields(merged)
    if "layers" in patch or "brand_locks" in patch or "canvas" in patch or "aspect_ratio" in patch:
        merged = coerce_template(merged)
        if not merged.get("scenes"):
            validate_template(merged)
    cols = _persist_columns(_template_to_columns(merged))
    set_clauses = ", ".join(f"{k} = ?" for k in cols.keys())
    values = list(cols.values()) + [template_id]
    conn.execute(
        f"UPDATE templates SET {set_clauses} WHERE id = ?",
        tuple(values),
    )
    return True


def delete_template(template_id: int, *, force: bool = False) -> bool:
    """Delete a template (refuses on built-in unless `force=True`)."""
    conn = app_db.get_conn()
    row = conn.execute(
        "SELECT is_builtin FROM templates WHERE id = ?", (template_id,)
    ).fetchone()
    if row is None:
        return False
    if bool(row["is_builtin"]) and not force:
        raise TemplateError("built-in templates are read-only (use force=True to override)")
    cur = conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    return cur.rowcount > 0


def get_template(template_id: int) -> dict | None:
    conn = app_db.get_conn()
    # Read whatever columns exist; new video columns are picked up if present.
    cols = [
        row[1]
        for row in conn.execute("PRAGMA table_info(templates)").fetchall()
    ]
    quoted = ", ".join(f'"{c}"' for c in cols)
    row = conn.execute(
        f"SELECT {quoted} FROM templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(zip(cols, row))
    return _row_to_template(d)


def list_templates(
    *,
    brand_id: int | None = None,
    category: str | None = None,
    include_builtin: bool = True,
) -> list[dict]:
    conn = app_db.get_conn()
    cols = [
        row[1]
        for row in conn.execute("PRAGMA table_info(templates)").fetchall()
    ]
    quoted = ", ".join(f'"{c}"' for c in cols)
    sql = f"SELECT {quoted} FROM templates WHERE 1=1"
    params: list[Any] = []
    if brand_id is not None:
        sql += " AND (brand_id = ?"
        if include_builtin:
            sql += " OR is_builtin = 1 OR brand_id IS NULL"
        sql += ")"
        params.append(brand_id)
    else:
        if not include_builtin:
            sql += " AND is_builtin = 0"
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY is_builtin DESC, name ASC"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_template(dict(zip(cols, row))) for row in rows]


def duplicate_template(template_id: int, new_name: str, brand_id: int | None = None) -> int:
    """Make a user-editable copy of any template (including built-ins)."""
    src = get_template(template_id)
    if src is None:
        raise TemplateError(f"no template with id={template_id}")
    # Strip row-only fields before re-validating.
    clean = _strip_row_only_fields(src)
    clean = coerce_template(clean)
    clean["name"] = new_name.strip() or f"{src.get('name', 'Template')} copy"
    if "canvas_w" not in clean:
        clean["canvas"] = {
            "width": src.get("canvas_w", 1080),
            "height": src.get("canvas_h", 1350),
        }
    new_id = create_template(clean, brand_id=brand_id)
    # Record lineage in the row (not part of the schema).
    conn = app_db.get_conn()
    conn.execute(
        "UPDATE templates SET parent_template_id = ? WHERE id = ?",
        (template_id, new_id),
    )
    return new_id


# ---------- substitution ----------

def _resolve_token(token: str, product: dict | None, brand: dict | None) -> str:
    """Resolve a single substitution token like `brand.colors.primary`.

    Supports simple dotted paths and `palette[N]` integer indexing.
    Unknown tokens return '' so the substitution is visible-but-empty
    (operator can see what was missed without crashing render).
    """
    parts = token.split(".")
    cur: Any = None
    if parts[0] == "product":
        cur = product or {}
        parts = parts[1:]
    elif parts[0] == "brand":
        cur = brand or {}
        parts = parts[1:]
    else:
        return ""
    for p in parts:
        if cur is None:
            return ""
        m = re.match(r"^([a-zA-Z0-9_]+)(?:\[(\d+)\])?$", p)
        if not m:
            return ""
        key, idx = m.group(1), m.group(2)
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return ""
        if idx is not None and isinstance(cur, list):
            try:
                cur = cur[int(idx)]
            except IndexError:
                return ""
    return "" if cur is None else str(cur)


def render_substitutions(
    text: str,
    *,
    product: dict | None = None,
    brand: dict | None = None,
) -> str:
    """Replace `{{token}}` substitutions in `text`. Returns the new string."""
    if not text:
        return text
    return _SUB_RE.sub(
        lambda m: _resolve_token(m.group(1), product, brand), text
    )


def substitute_template(t: dict, *, product: dict | None, brand: dict | None) -> dict:
    """Return a deep-copied template dict with every `{{...}}` replaced in
    layer config strings. Numeric and boolean config values are not touched.
    """
    import copy
    out = copy.deepcopy(t)

    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            return render_substitutions(node, product=product, brand=brand)
        return node

    for layer in out.get("layers") or []:
        cfg = layer.get("config")
        if isinstance(cfg, dict):
            layer["config"] = walk(cfg)
    return out


# ---------- built-in loader ----------

def load_builtins() -> int:
    """Idempotently insert every JSON file in `templates/builtin/*.json` into
    the `templates` table. Returns the number of templates newly inserted.

    Already-existing built-ins (matched by slug derived from filename) are left
    alone so user-customized built-ins (force=True) are preserved across boots.
    """
    if not BUILTIN_DIR.exists():
        return 0
    inserted = 0
    for path in sorted(BUILTIN_DIR.glob("*.json")):
        slug = path.stem
        existing = _find_by_slug(slug)
        if existing is not None:
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise TemplateError(f"built-in template {slug!r} is not valid JSON: {exc}") from exc
        # Built-in JSONs may not have id; the file name IS the slug.
        data.setdefault("name", slug.replace("_", " ").title())
        data.setdefault("category", "product")
        # Built-ins reference the static file-system preview.
        preview = BUILTIN_PREVIEW_DIR / f"{slug}.png"
        if preview.exists():
            data["preview_path"] = str(preview)
        # Persist; mark as built-in.
        cols = _template_to_columns(data)
        now = time.time()
        app_db.get_conn().execute(
            """
            INSERT INTO templates(
                brand_id, name, category, aspect_ratio, canvas_w, canvas_h,
                layers_json, brand_locks_json, default_filter,
                ai_prompt_template, preview_path,
                is_builtin, is_custom, created_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
            """,
            (
                cols["name"], cols["category"], cols["aspect_ratio"],
                cols["canvas_w"], cols["canvas_h"],
                cols["layers_json"], cols["brand_locks_json"],
                cols["default_filter"], cols["ai_prompt_template"],
                cols["preview_path"], now,
            ),
        )
        inserted += 1
    return inserted


def _find_by_slug(slug: str) -> dict | None:
    conn = app_db.get_conn()
    # We use the slug match against the name normalised lower + spaces.
    pretty = slug.replace("_", " ").title()
    row = conn.execute(
        "SELECT id FROM templates WHERE is_builtin = 1 AND lower(name) = lower(?) LIMIT 1",
        (pretty,),
    ).fetchone()
    return {"id": row["id"]} if row else None


def collect_supported_layer_types() -> tuple[str, ...]:
    return LAYER_TYPES


def collect_supported_aspect_ratios() -> tuple[str, ...]:
    return ASPECT_RATIOS


__all__ = [
    "TemplateError",
    "ASPECT_RATIOS",
    "LAYER_TYPES",
    "validate",
    "create_template",
    "update_template",
    "delete_template",
    "duplicate_template",
    "get_template",
    "list_templates",
    "render_substitutions",
    "substitute_template",
    "load_builtins",
    "collect_supported_layer_types",
    "collect_supported_aspect_ratios",
]
