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


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def get_output(output_id: int) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM outputs WHERE id = ?", (int(output_id),)).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


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