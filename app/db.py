"""app/db.py. SQLite layer for structured app data.

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

    # ---- Phase A: Pipeline / Funnel builder ----
    """
    CREATE TABLE IF NOT EXISTS pipelines (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        description TEXT,
        nodes_json  TEXT NOT NULL DEFAULT '[]',
        edges_json  TEXT NOT NULL DEFAULT '[]',
        max_workers INTEGER NOT NULL DEFAULT 2,
        enabled     INTEGER NOT NULL DEFAULT 1,
        created_at  REAL NOT NULL,
        updated_at  REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        pipeline_id  INTEGER NOT NULL,
        status       TEXT NOT NULL DEFAULT 'queued',
        log_json     TEXT NOT NULL DEFAULT '[]',
        started_at   REAL,
        finished_at  REAL,
        spent_usd    REAL NOT NULL DEFAULT 0,
        error        TEXT,
        triggered_by TEXT,
        FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE
    )
    """,
    # ---- Phase F: Contacts ----
    """
    CREATE TABLE IF NOT EXISTS contacts (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        email           TEXT NOT NULL UNIQUE,
        first_name      TEXT,
        last_name       TEXT,
        phone           TEXT,
        tags_json       TEXT NOT NULL DEFAULT '[]',
        source          TEXT,
        consent_marketing INTEGER NOT NULL DEFAULT 0,
        consent_at      REAL,
        unsubscribed_at REAL,
        custom_json     TEXT NOT NULL DEFAULT '{}',
        created_at      REAL NOT NULL,
        updated_at      REAL NOT NULL
    )
    """,
    # ---- Phase F: Campaigns ----
    """
    CREATE TABLE IF NOT EXISTS campaigns (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        subject     TEXT,
        channel     TEXT NOT NULL DEFAULT 'email',
        status      TEXT NOT NULL DEFAULT 'draft',
        audience_query TEXT,
        send_at     REAL,
        body_html   TEXT,
        body_text   TEXT,
        created_at  REAL NOT NULL,
        updated_at  REAL NOT NULL
    )
    """,
    # ---- Phase F: Landing pages ----
    """
    CREATE TABLE IF NOT EXISTS landing_pages (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        slug        TEXT NOT NULL UNIQUE,
        title       TEXT NOT NULL,
        body_html   TEXT NOT NULL DEFAULT '',
        form_schema TEXT NOT NULL DEFAULT '{}',
        consent_text TEXT,
        published   INTEGER NOT NULL DEFAULT 0,
        created_at  REAL NOT NULL,
        updated_at  REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS landing_submissions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        page_id     INTEGER NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at  REAL NOT NULL,
        FOREIGN KEY (page_id) REFERENCES landing_pages(id) ON DELETE CASCADE
    )
    """,
    # ---- Phase F: Social posts ----
    """
    CREATE TABLE IF NOT EXISTS social_posts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        platform      TEXT NOT NULL,
        account       TEXT,
        body          TEXT NOT NULL,
        media_url     TEXT,
        scheduled_at  REAL,
        published_at  REAL,
        status        TEXT NOT NULL DEFAULT 'draft',
        external_id   TEXT,
        error         TEXT,
        created_at    REAL NOT NULL,
        updated_at    REAL NOT NULL
    )
    """,
    # ---- Phase F: Analytics events ----
    """
    CREATE TABLE IF NOT EXISTS analytics_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        kind        TEXT NOT NULL,
        ref         TEXT,
        value_num   REAL NOT NULL DEFAULT 0,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at  REAL NOT NULL
    )
    """,
    # ---- Phase F: Scheduled jobs (queue) ----
    """
    CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        kind        TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        run_at      REAL NOT NULL,
        status      TEXT NOT NULL DEFAULT 'queued',
        last_error  TEXT,
        created_at  REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline ON pipeline_runs(pipeline_id)",
    "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status)",
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