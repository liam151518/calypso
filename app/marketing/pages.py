"""app/marketing/pages.py. Phase F.3 landing pages and submissions."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Any

from .. import db as app_db


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(app_db.DB_PATH))
    c.row_factory = sqlite3.Row
    return c


@dataclass
class LandingPage:
    id: int | None
    slug: str
    title: str
    body_html: str = ""
    form_schema: dict[str, Any] = None  # type: ignore[assignment]
    consent_text: str = ""
    published: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["form_schema"] = dict(self.form_schema or {})
        return d


def _slugify(s: str) -> str:
    s = _SLUG_RE.sub("-", s.strip().lower()).strip("-")
    return s or "page"


def create_page(page: LandingPage) -> int:
    page.slug = _slugify(page.slug or page.title)
    now = time.time()
    schema = json.dumps(dict(page.form_schema or {}))
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO landing_pages
               (slug, title, body_html, form_schema, consent_text, published,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (page.slug, page.title, page.body_html, schema,
             page.consent_text, 1 if page.published else 0, now, now),
        )
    return int(cur.lastrowid)


def update_page(pid: int, **patch) -> bool:
    if not patch:
        return True
    allowed = {"title", "body_html", "form_schema", "consent_text", "published", "slug"}
    patch = {k: v for k, v in patch.items() if k in allowed}
    if "slug" in patch:
        patch["slug"] = _slugify(patch["slug"])
    if "form_schema" in patch:
        patch["form_schema"] = json.dumps(dict(patch["form_schema"] or {}))
    if "published" in patch:
        patch["published"] = 1 if patch["published"] else 0
    patch["updated_at"] = time.time()
    sets = ", ".join(f"{k} = ?" for k in patch)
    args = list(patch.values()) + [pid]
    with _conn() as c:
        cur = c.execute(f"UPDATE landing_pages SET {sets} WHERE id = ?", args)
    return cur.rowcount > 0


def get_page(pid: int) -> LandingPage | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM landing_pages WHERE id = ?", (pid,)
        ).fetchone()
    return _row_to_page(row) if row else None


def get_page_by_slug(slug: str) -> LandingPage | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM landing_pages WHERE slug = ?", (_slugify(slug),)
        ).fetchone()
    return _row_to_page(row) if row else None


def list_pages(*, published_only: bool = False) -> list[LandingPage]:
    sql = "SELECT * FROM landing_pages"
    if published_only:
        sql += " WHERE published = 1"
    sql += " ORDER BY id DESC LIMIT 500"
    with _conn() as c:
        rows = c.execute(sql).fetchall()
    return [_row_to_page(r) for r in rows]


def delete_page(pid: int) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM landing_pages WHERE id = ?", (pid,))
    return cur.rowcount > 0


def record_submission(pid: int, payload: dict[str, Any]) -> int:
    now = time.time()
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO landing_submissions (page_id, payload_json, created_at)
               VALUES (?, ?, ?)""",
            (pid, json.dumps(payload, default=str), now),
        )
    return int(cur.lastrowid)


def count_submissions(pid: int) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM landing_submissions WHERE page_id = ?",
            (pid,),
        ).fetchone()
    return int(row["n"] or 0)


def _row_to_page(row: sqlite3.Row) -> LandingPage:
    return LandingPage(
        id=int(row["id"]),
        slug=row["slug"],
        title=row["title"],
        body_html=row["body_html"] or "",
        form_schema=json.loads(row["form_schema"] or "{}"),
        consent_text=row["consent_text"] or "",
        published=bool(row["published"]),
    )
