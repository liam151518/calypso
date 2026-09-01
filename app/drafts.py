"""app/drafts.py. Prompt-draft library.

A draft is a named piece of prompt copy that the user wants to keep
for re-use. Stored in SQLite, not the filesystem, because the data is
short, structured, and queried often.

Lifecycle:
    - User clicks "Save as draft" on Generate → save_draft(name, body, category)
    - User clicks a draft in the picker → get_draft(id) → loaded into the prompt box
    - User toggles the star → toggle_favorite(id)
    - User searches "damascus" → list_drafts(query="damascus")

Categories auto-populate: anything used as a category by an existing draft
appears in `categories()`.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Iterable

from app import db as app_db


def _conn() -> sqlite3.Connection:
    return app_db.get_conn()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["is_favorite"] = bool(d.get("is_favorite", 0))
    return d


# ---------- CRUD ----------

def list_drafts(
    query: str | None = None,
    category: str | None = None,
    favorites_only: bool = False,
    limit: int = 200,
) -> list[dict]:
    """Return drafts, newest first. Filters are AND-combined."""
    sql = "SELECT * FROM drafts WHERE 1=1"
    params: list = []
    if favorites_only:
        sql += " AND is_favorite = 1"
    if category:
        sql += " AND category = ?"
        params.append(category)
    if query:
        like = f"%{query}%"
        sql += " AND (name LIKE ? OR body LIKE ?)"
        params.extend([like, like])
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    conn = _conn()
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_draft(draft_id: int | str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    return _row_to_dict(row) if row else None


def save_draft(
    name: str,
    body: str,
    category: str | None = None,
    draft_id: int | None = None,
    is_favorite: bool = False,
) -> dict:
    """Create or update a draft. Returns the saved row as a dict."""
    name = (name or "").strip()
    body = body or ""
    category = (category or "").strip() or None
    if not name:
        raise ValueError("Draft name is required")
    if not body:
        raise ValueError("Draft body is required")

    now = time.time()
    conn = _conn()
    if draft_id is None:
        cur = conn.execute(
            """
            INSERT INTO drafts(name, body, category, is_favorite, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, body, category, int(is_favorite), now, now),
        )
        return get_draft(cur.lastrowid) or {}
    # Update path. Keep created_at, bump updated_at.
    conn.execute(
        """
        UPDATE drafts
        SET name = ?, body = ?, category = ?, is_favorite = ?, updated_at = ?
        WHERE id = ?
        """,
        (name, body, category, int(is_favorite), now, draft_id),
    )
    return get_draft(draft_id) or {}


def delete_draft(draft_id: int | str) -> bool:
    conn = _conn()
    cur = conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
    return cur.rowcount > 0


def toggle_favorite(draft_id: int | str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT is_favorite FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    if not row:
        return None
    new_val = 0 if row["is_favorite"] else 1
    conn.execute(
        "UPDATE drafts SET is_favorite = ?, updated_at = ? WHERE id = ?",
        (new_val, time.time(), draft_id),
    )
    return get_draft(draft_id)


# ---------- facets ----------

def categories() -> list[dict]:
    """Return distinct categories with usage counts, descending."""
    conn = _conn()
    rows = conn.execute(
        """
        SELECT category, COUNT(*) AS count
        FROM drafts
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY count DESC, category ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def count() -> int:
    conn = _conn()
    row = conn.execute("SELECT COUNT(*) AS n FROM drafts").fetchone()
    return int(row["n"])


def favorites() -> list[dict]:
    return list_drafts(favorites_only=True)