"""app/marketing/analytics.py. Phase F.6 lightweight event store.

Records every marketing-relevant event (opens, clicks, sends, replies,
purchases). The SPA / Analytics page queries `aggregate()` for charts.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from .. import db as app_db


VALID_KINDS = (
    "email_sent", "email_open", "email_click", "email_unsubscribe",
    "sms_sent", "sms_click",
    "page_view", "form_submit",
    "social_publish", "social_click",
    "purchase",
)


@dataclass
class Event:
    id: int | None
    kind: str
    ref: str
    value_num: float = 0.0
    metadata: dict[str, Any] | None = None
    created_at: float = 0.0


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def record(kind: str, ref: str = "", value_num: float = 0.0,
           metadata: dict[str, Any] | None = None) -> int:
    if kind not in VALID_KINDS:
        raise ValueError(f"invalid event kind: {kind}")
    now = time.time()
    md = json.dumps(metadata or {}, default=str)
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO analytics_events
               (kind, ref, value_num, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (kind, ref, float(value_num), md, now),
        )
    return int(cur.lastrowid)


def recent_events(kind: str | None = None, limit: int = 100) -> list[Event]:
    sql = "SELECT * FROM analytics_events"
    params: list[Any] = []
    if kind:
        sql += " WHERE kind = ?"
        params.append(kind)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_event(r) for r in rows]


def aggregate(since: float, *, kind: str | None = None) -> dict[str, Any]:
    """Group counts by event kind for the requested window."""
    sql = "SELECT kind, COUNT(*) AS n, COALESCE(SUM(value_num), 0) AS sum "
    sql += "FROM analytics_events WHERE created_at >= ?"
    params: list[Any] = [float(since)]
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " GROUP BY kind"
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    out = {k: {"count": 0, "sum": 0.0} for k in VALID_KINDS}
    for row in rows:
        out[row["kind"]] = {"count": int(row["n"]), "sum": float(row["sum"])}
    return out


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=int(row["id"]),
        kind=row["kind"],
        ref=row["ref"] or "",
        value_num=float(row["value_num"]),
        metadata=json.loads(row["metadata_json"] or "{}"),
        created_at=float(row["created_at"]),
    )
