"""app.outputs. CRUD helpers for the ``outputs`` table.

The Phase A ``app.compositor`` module writes rows here; the Phase C
scheduler reads/writes here when a job is approved + dispatched. This
module is intentionally tiny — most logic lives next to the writer.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from . import db as app_db
from .jobs import OUTPUTS_DIR


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def rel_url_for_path(file_path: str | None) -> str | None:
    """Convert an absolute path under the outputs directory into a served URL.

    Returns ``None`` when the path is missing, not absolute, or not located
    under :data:`app.jobs.OUTPUTS_DIR`. Callers fall back to ``None`` and the
    SPA renders an "No preview" placeholder.
    """
    if not file_path:
        return None
    try:
        p = Path(file_path)
        if p.is_absolute() and str(p).startswith(str(OUTPUTS_DIR)):
            return "/outputs/" + str(p.relative_to(OUTPUTS_DIR))
    except Exception:  # noqa: BLE001
        return None
    return None


def get_output(output_id: int) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM outputs WHERE id = ?", (int(output_id),)).fetchone()
    if not row:
        return None
    out = _deserialize_layers_and_filters(_row_to_dict(row))
    out["rel_url"] = rel_url_for_path(out.get("file_path"))
    return out


def _deserialize_layers_and_filters(out: dict[str, Any]) -> dict[str, Any]:
    """Parse `layers_json` and `filter_settings` columns into Python objects.

    Returns a shallow copy with the parsed fields. Missing or malformed JSON
    becomes empty list/dict so callers can rely on the shape.
    """
    import json
    parsed = dict(out)
    raw_layers = parsed.get("layers_json")
    if raw_layers:
        try:
            parsed["layers"] = json.loads(raw_layers)
        except (TypeError, ValueError):
            parsed["layers"] = []
    else:
        parsed["layers"] = []
    raw_filter = parsed.get("filter_settings")
    if raw_filter:
        try:
            parsed["filter"] = json.loads(raw_filter)
        except (TypeError, ValueError):
            parsed["filter"] = {}
    else:
        parsed["filter"] = {}
    return parsed


def list_outputs(*, brand_id: int | None = None,
                 status: str | None = None,
                 limit: int = 100) -> list[dict[str, Any]]:
    sql = "SELECT * FROM outputs"
    params: list[Any] = []
    clauses: list[str] = []
    if brand_id is not None:
        clauses.append("brand_id = ?")
        params.append(int(brand_id))
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def mark_published(output_id: int, *, platform: str,
                   external_id: str | None = None,
                   url: str | None = None) -> bool:
    with _conn() as c:
        cur = c.execute(
            """UPDATE outputs
               SET status = 'published',
                   published_at = ?,
                   platform = COALESCE(NULLIF(?, ''), platform),
                   external_id = ?,
                   external_url = ?
             WHERE id = ?""",
            (time.time(), platform, external_id or "", url or "",
             int(output_id)),
        )
    return cur.rowcount > 0


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    keys = row.keys()
    return {k: row[k] for k in keys}