"""app/skills_store.py. SQLite-backed persistence for user skills.

Backs the higher-level :mod:`app.skills` API. Owns the ``user_skills``
table and exposes a small set of helpers used by both the runtime and the
HTTP API.

Schema:

    CREATE TABLE user_skills (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        slug            TEXT NOT NULL UNIQUE,
        name            TEXT NOT NULL DEFAULT '',
        enabled         INTEGER NOT NULL DEFAULT 1,
        content_md      TEXT NOT NULL DEFAULT '',
        post_process_re TEXT,
        description     TEXT NOT NULL DEFAULT '',
        tags_json       TEXT NOT NULL DEFAULT '[]',
        builtin         INTEGER NOT NULL DEFAULT 0,
        created_at      REAL NOT NULL,
        updated_at      REAL NOT NULL
    );

A ``slug`` uniquely identifies a skill; built-in slugs (``ugc_video``,
``image_ad``, ``prompt_enhancement``, ``caption_optimizer``) are stored
with ``builtin=1`` so we can detect override-only rows.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import db as app_db


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def ensure_table() -> None:
    """Create the ``user_skills`` table + index if absent. Idempotent."""
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS user_skills (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                slug            TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL DEFAULT '',
                enabled         INTEGER NOT NULL DEFAULT 1,
                content_md      TEXT NOT NULL DEFAULT '',
                post_process_re TEXT,
                description     TEXT NOT NULL DEFAULT '',
                tags_json       TEXT NOT NULL DEFAULT '[]',
                builtin         INTEGER NOT NULL DEFAULT 0,
                created_at      REAL NOT NULL,
                updated_at      REAL NOT NULL
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_skills_slug "
            "ON user_skills(slug)"
        )


@dataclass
class UserSkill:
    slug: str
    name: str = ""
    enabled: bool = True
    content_md: str = ""
    post_process_re: str | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)
    builtin: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "enabled": self.enabled,
            "content_md": self.content_md,
            "post_process_re": self.post_process_re,
            "description": self.description,
            "tags": list(self.tags),
            "builtin": self.builtin,
        }


def _row_to_skill(row: sqlite3.Row) -> UserSkill:
    tags_json = row["tags_json"] or "[]"
    try:
        tags = json.loads(tags_json)
    except json.JSONDecodeError:
        tags = []
    if not isinstance(tags, list):
        tags = []
    return UserSkill(
        slug=row["slug"],
        name=row["name"] or "",
        enabled=bool(row["enabled"]),
        content_md=row["content_md"] or "",
        post_process_re=row["post_process_re"],
        description=row["description"] or "",
        tags=[str(t) for t in tags],
        builtin=bool(row["builtin"]),
    )


# ---- CRUD ---------------------------------------------------------------


def user_skills() -> list[UserSkill]:
    ensure_table()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM user_skills ORDER BY builtin DESC, slug ASC"
        ).fetchall()
    return [_row_to_skill(r) for r in rows]


def get_user_skill(slug: str) -> UserSkill | None:
    ensure_table()
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM user_skills WHERE slug = ?", (slug,)
        ).fetchone()
    if not row:
        return None
    return _row_to_skill(row)


def upsert_user_skill(*, slug: str, name: str = "",
                      enabled: bool = True, content_md: str = "",
                      post_process_re: str | None = None,
                      description: str = "",
                      tags: Iterable[str] | None = None,
                      builtin: bool = False) -> UserSkill:
    """Insert or update a row. ``builtin`` is sticky — once True it stays True."""
    ensure_table()
    now = time.time()
    tags_list = list(tags or [])
    with _conn() as c:
        row = c.execute(
            "SELECT id, builtin FROM user_skills WHERE slug = ?", (slug,)
        ).fetchone()
        if row is None:
            c.execute(
                """INSERT INTO user_skills (
                    slug, name, enabled, content_md, post_process_re,
                    description, tags_json, builtin, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    slug, name, int(bool(enabled)), content_md,
                    post_process_re, description,
                    json.dumps(tags_list), int(bool(builtin)), now, now,
                ),
            )
        else:
            sticky_builtin = bool(row["builtin"]) or bool(builtin)
            c.execute(
                """UPDATE user_skills SET
                    name = ?,
                    enabled = ?,
                    content_md = ?,
                    post_process_re = ?,
                    description = ?,
                    tags_json = ?,
                    builtin = ?,
                    updated_at = ?
                  WHERE slug = ?""",
                (
                    name, int(bool(enabled)), content_md,
                    post_process_re, description,
                    json.dumps(tags_list), int(sticky_builtin), now,
                    slug,
                ),
            )
        row = c.execute(
            "SELECT * FROM user_skills WHERE slug = ?", (slug,)
        ).fetchone()
    assert row is not None
    return _row_to_skill(row)


def upsert_user_skill_from_file(slug: str, path: Path) -> str:
    """Read a markdown file and upsert. Preserves the existing ``enabled``
    flag if a row already exists. Returns ``"added"``, ``"updated"``, or
    ``"unchanged"``."""
    from .skills import _parse_md, _coerce_enabled

    ensure_table()
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_md(text)
    name = fm.get("name") or slug.replace("_", " ").title()
    description = fm.get("description", "")
    tags_raw = fm.get("tags", [])
    tags = tags_raw if isinstance(tags_raw, list) else []
    post_re = fm.get("post_process_re")
    with _conn() as c:
        row = c.execute(
            "SELECT id, enabled FROM user_skills WHERE slug = ?", (slug,)
        ).fetchone()
        if row is None:
            enabled = _coerce_enabled(fm.get("enabled"))
            now = time.time()
            c.execute(
                """INSERT INTO user_skills (
                    slug, name, enabled, content_md, post_process_re,
                    description, tags_json, builtin, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    slug, name, int(enabled), body.strip(), post_re,
                    description, json.dumps(tags), now, now,
                ),
            )
            return "added"
        # Preserve enabled; only refresh content.
        now = time.time()
        c.execute(
            """UPDATE user_skills SET
                name = ?,
                content_md = ?,
                post_process_re = ?,
                description = ?,
                tags_json = ?,
                updated_at = ?
              WHERE slug = ?""",
            (
                name, body.strip(), post_re, description,
                json.dumps(tags), now, slug,
            ),
        )
        return "updated"


def set_enabled(slug: str, enabled: bool) -> bool:
    ensure_table()
    with _conn() as c:
        cur = c.execute(
            "UPDATE user_skills SET enabled = ?, updated_at = ? WHERE slug = ?",
            (int(bool(enabled)), time.time(), slug),
        )
    return cur.rowcount > 0


def delete_user_skill(slug: str) -> bool:
    ensure_table()
    with _conn() as c:
        cur = c.execute("DELETE FROM user_skills WHERE slug = ?", (slug,))
    return cur.rowcount > 0


def ensure_builtin_seeded() -> None:
    """Make sure every built-in slug has a DB row so the UI can toggle it
    without writing a markdown file first. Idempotent."""
    from .skills import BUILTIN_SLUGS, _BUILTINS_DIR
    ensure_table()
    now = time.time()
    with _conn() as c:
        for slug in BUILTIN_SLUGS:
            row = c.execute(
                "SELECT id FROM user_skills WHERE slug = ?", (slug,)
            ).fetchone()
            if row is not None:
                continue
            path = _BUILTINS_DIR / f"{slug}.md"
            content = path.read_text(encoding="utf-8") if path.exists() else ""
            c.execute(
                """INSERT INTO user_skills (
                    slug, name, enabled, content_md, builtin,
                    created_at, updated_at
                ) VALUES (?, ?, 1, ?, 1, ?, ?)""",
                (
                    slug,
                    slug.replace("_", " ").title(),
                    content,
                    now, now,
                ),
            )
