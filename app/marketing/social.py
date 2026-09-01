"""app/marketing/social.py. Phase F.5 social posts (multi-platform).

The actual posting is done by Phase D channel extensions (X, TikTok,
Meta, etc.). This module just owns the draft/queue state and the
platform-specific length warnings.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Any

from .. import db as app_db


PLATFORM_LIMITS = {
    "x": 280,
    "twitter": 280,
    "linkedin": 3000,
    "instagram": 2200,
    "tiktok": 2200,
    "facebook": 63206,
    "youtube": 1000,  # title limit
}

VALID_PLATFORMS = tuple(PLATFORM_LIMITS.keys())
VALID_STATUSES = ("draft", "queued", "publishing", "published", "failed")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


@dataclass
class SocialPost:
    id: int | None
    platform: str
    body: str
    account: str = ""
    media_url: str = ""
    scheduled_at: float | None = None
    status: str = "draft"
    external_id: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["char_limit"] = PLATFORM_LIMITS.get(self.platform, 0)
        d["over_limit"] = len(self.body) > d["char_limit"]
        return d


def create_post(post: SocialPost) -> int:
    if post.platform not in VALID_PLATFORMS:
        raise ValueError(f"invalid platform: {post.platform}")
    if post.status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {post.status}")
    now = time.time()
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO social_posts
               (platform, account, body, media_url, scheduled_at, status,
                external_id, error, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (post.platform, post.account, post.body, post.media_url,
             post.scheduled_at, post.status, post.external_id, post.error,
             now, now),
        )
    return int(cur.lastrowid)


def update_post(pid: int, **patch) -> bool:
    if not patch:
        return True
    allowed = {"account", "body", "media_url", "scheduled_at", "status",
               "external_id", "error", "platform"}
    patch = {k: v for k, v in patch.items() if k in allowed}
    if "platform" in patch and patch["platform"] not in VALID_PLATFORMS:
        raise ValueError("invalid platform")
    if "status" in patch and patch["status"] not in VALID_STATUSES:
        raise ValueError("invalid status")
    if not patch:
        return True
    patch["updated_at"] = time.time()
    sets = ", ".join(f"{k} = ?" for k in patch)
    args = list(patch.values()) + [pid]
    with _conn() as c:
        cur = c.execute(f"UPDATE social_posts SET {sets} WHERE id = ?", args)
    return cur.rowcount > 0


def delete_post(pid: int) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM social_posts WHERE id = ?", (pid,))
    return cur.rowcount > 0


def get_post(pid: int) -> SocialPost | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM social_posts WHERE id = ?", (pid,)).fetchone()
    return _row_to_post(row) if row else None


def list_posts(*, platform: str | None = None,
               status: str | None = None) -> list[SocialPost]:
    sql = "SELECT * FROM social_posts"
    params: list[Any] = []
    clauses: list[str] = []
    if platform:
        clauses.append("platform = ?")
        params.append(platform)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC LIMIT 500"
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_post(r) for r in rows]


def _row_to_post(row: sqlite3.Row) -> SocialPost:
    return SocialPost(
        id=int(row["id"]),
        platform=row["platform"],
        account=row["account"] or "",
        body=row["body"],
        media_url=row["media_url"] or "",
        scheduled_at=row["scheduled_at"],
        status=row["status"],
        external_id=row["external_id"] or "",
        error=row["error"] or "",
    )
