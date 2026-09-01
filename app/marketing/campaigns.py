"""app/marketing/campaigns.py. Phase F.2 campaign store.

Campaigns are drafts until status flips to `scheduled` or `sent`. The
body lives as both `body_html` and `body_text` so SMTP clients without
HTML support still get something readable.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Any

from .. import db as app_db


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


@dataclass
class Campaign:
    id: int | None
    name: str
    subject: str = ""
    channel: str = "email"
    status: str = "draft"
    audience_query: str = ""
    send_at: float | None = None
    body_html: str = ""
    body_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


VALID_STATUSES = ("draft", "scheduled", "sending", "sent", "paused", "failed")
VALID_CHANNELS = ("email", "sms", "push")


def create_campaign(camp: Campaign) -> int:
    if camp.status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {camp.status}")
    if camp.channel not in VALID_CHANNELS:
        raise ValueError(f"invalid channel: {camp.channel}")
    now = time.time()
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO campaigns
               (name, subject, channel, status, audience_query, send_at,
                body_html, body_text, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (camp.name, camp.subject, camp.channel, camp.status,
             camp.audience_query, camp.send_at, camp.body_html, camp.body_text,
             now, now),
        )
    return int(cur.lastrowid)


def update_campaign(cid: int, **patch) -> bool:
    if not patch:
        return True
    allowed = {"name", "subject", "channel", "status", "audience_query",
               "send_at", "body_html", "body_text"}
    patch = {k: v for k, v in patch.items() if k in allowed}
    if "status" in patch and patch["status"] not in VALID_STATUSES:
        raise ValueError("invalid status")
    if "channel" in patch and patch["channel"] not in VALID_CHANNELS:
        raise ValueError("invalid channel")
    if not patch:
        return True
    patch["updated_at"] = time.time()
    sets = ", ".join(f"{k} = ?" for k in patch)
    args = list(patch.values()) + [cid]
    with _conn() as c:
        cur = c.execute(f"UPDATE campaigns SET {sets} WHERE id = ?", args)
    return cur.rowcount > 0


def delete_campaign(cid: int) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM campaigns WHERE id = ?", (cid,))
    return cur.rowcount > 0


def get_campaign(cid: int) -> Campaign | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM campaigns WHERE id = ?", (cid,)).fetchone()
    return _row_to_campaign(row) if row else None


def list_campaigns(*, status: str | None = None) -> list[Campaign]:
    sql = "SELECT * FROM campaigns"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT 500"
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_campaign(r) for r in rows]


def _row_to_campaign(row: sqlite3.Row) -> Campaign:
    return Campaign(
        id=int(row["id"]),
        name=row["name"],
        subject=row["subject"] or "",
        channel=row["channel"],
        status=row["status"],
        audience_query=row["audience_query"] or "",
        send_at=row["send_at"],
        body_html=row["body_html"] or "",
        body_text=row["body_text"] or "",
    )
