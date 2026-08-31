"""app/db.py — SQLite layer for structured app data.

Calypso's structured data (reference tags, prompt drafts, brand profiles,
job-prompt linkage, the "active brand" pointer) lives in a single SQLite
file at `.calypso/calypso.db`. Migrations are applied on first connect.

This module is intentionally tiny: a connection factory, a tiny migrator,
and the schema as SQL strings. Domain logic lives in app/refs.py,
app/drafts.py, app/brand.py.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CALYPSO_DIR = PROJECT_ROOT / ".calypso"
DB_PATH = CALYPSO_DIR / "calypso.db"

# Thread-local connection so the Flask app (and pytest) can share one DB
# without contending on the sqlite3 connection itself.
_local = threading.local()


SCHEMA: list[str] = [
    # ---- tags + reference associations ----
    """
    CREATE TABLE IF NOT EXISTS tags (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reference_tags (
        reference_id TEXT NOT NULL,
        tag_id       INTEGER NOT NULL,
        PRIMARY KEY (reference_id, tag_id),
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_reference_tags_tag ON reference_tags(tag_id)",

    # ---- prompt drafts ----
    """
    CREATE TABLE IF NOT EXISTS drafts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        body        TEXT NOT NULL,
        category    TEXT,
        is_favorite INTEGER NOT NULL DEFAULT 0,
        created_at  REAL NOT NULL,
        updated_at  REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_drafts_category ON drafts(category)",
    "CREATE INDEX IF NOT EXISTS idx_drafts_favorite ON drafts(is_favorite)",

    # ---- brand profiles ----
    """
    CREATE TABLE IF NOT EXISTS brand_profiles (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT NOT NULL UNIQUE,
        tagline      TEXT,
        audience     TEXT,
        palette_json TEXT NOT NULL DEFAULT '[]',
        typography   TEXT,
        voice        TEXT,
        do_examples  TEXT,
        dont_examples TEXT,
        style_guide  TEXT,
        created_at   REAL NOT NULL,
        updated_at   REAL NOT NULL
    )
    """,

    # ---- key/value settings (single-row pointers like active_brand_id) ----
    """
    CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )
    """,

    # ---- job prompt linkage (so Outputs can re-derive a prompt) ----
    """
    CREATE TABLE IF NOT EXISTS job_links (
        job_id       TEXT PRIMARY KEY,
        prompt_body  TEXT NOT NULL,
        draft_id     INTEGER,
        brand_id     INTEGER,
        ref_ids_json TEXT NOT NULL DEFAULT '[]',
        created_at   REAL NOT NULL,
        FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE SET NULL,
        FOREIGN KEY (brand_id) REFERENCES brand_profiles(id) ON DELETE SET NULL
    )
    """,
]


def init_db(path: Path | None = None) -> Path:
    """Ensure DB file + parent dir exist and migrations have run. Idempotent."""
    target = path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    return target


def get_conn(path: Path | None = None) -> sqlite3.Connection:
    """Return a thread-local connection, creating + migrating the file if needed."""
    target = path or DB_PATH
    cache_attr = f"conn_{target}"
    cached = getattr(_local, cache_attr, None)
    if cached is not None:
        return cached
    init_db(target)
    conn = sqlite3.connect(str(target), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    setattr(_local, cache_attr, conn)
    return conn


def reset_for_tests(path: Path) -> None:
    """Drop cached connections pointing at `path` (used by tests)."""
    cache_attr = f"conn_{path}"
    if hasattr(_local, cache_attr):
        conn = getattr(_local, cache_attr)
        try:
            conn.close()
        except Exception:
            pass
        delattr(_local, cache_attr)