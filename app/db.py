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
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

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

    # ---- Phase G+: Brand DNA v2 (parallel to brand_profiles; new write path) ----
    # Keeps brand_profiles intact for back-compat; app.brand writes through.
    """
    CREATE TABLE IF NOT EXISTS brands (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        name                 TEXT NOT NULL UNIQUE,
        tagline              TEXT,
        audience             TEXT,
        palette_json         TEXT NOT NULL DEFAULT '[]',
        typography           TEXT,
        fonts_json           TEXT NOT NULL DEFAULT '{}',
        voice                TEXT,
        voice_tone           TEXT,
        banned_words_json    TEXT NOT NULL DEFAULT '[]',
        emoji_policy         TEXT,
        do_examples          TEXT,
        dont_examples        TEXT,
        style_guide          TEXT,
        logo_path            TEXT,
        watermark_path       TEXT,
        default_filter       TEXT,
        default_aspect_ratio TEXT,
        brand_profile_id     INTEGER,
        created_at           REAL NOT NULL,
        updated_at           REAL NOT NULL
    )
    """,

    # ---- Phase A: Product catalog + variants ----
    """
    CREATE TABLE IF NOT EXISTS products (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_id      INTEGER,
        name          TEXT NOT NULL,
        price         REAL,
        category      TEXT,
        collection    TEXT,
        description   TEXT,
        image_path    TEXT,
        cutout_path   TEXT,
        tags_json     TEXT NOT NULL DEFAULT '[]',
        launch_date   TEXT,
        created_at    REAL NOT NULL,
        updated_at    REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand_id)",

    """
    CREATE TABLE IF NOT EXISTS product_variants (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id   INTEGER NOT NULL,
        variant_name TEXT NOT NULL,
        sku          TEXT,
        price_delta  REAL NOT NULL DEFAULT 0,
        image_path   TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_product_variants_product ON product_variants(product_id)",

    # ---- Phase A: Templates (JSON layer stacks) ----
    """
    CREATE TABLE IF NOT EXISTS templates (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_id            INTEGER,
        name                TEXT NOT NULL,
        category            TEXT,
        aspect_ratio        TEXT NOT NULL DEFAULT '4:5',
        canvas_w            INTEGER NOT NULL DEFAULT 1080,
        canvas_h            INTEGER NOT NULL DEFAULT 1350,
        layers_json         TEXT NOT NULL DEFAULT '[]',
        scenes_json         TEXT NOT NULL DEFAULT '[]',
        transitions_json    TEXT NOT NULL DEFAULT '[]',
        audio_track_json    TEXT,
        duration_s          INTEGER NOT NULL DEFAULT 0,
        fps                 INTEGER NOT NULL DEFAULT 30,
        format              TEXT NOT NULL DEFAULT 'image',
        brand_locks_json    TEXT NOT NULL DEFAULT '[]',
        default_filter      TEXT,
        ai_prompt_template  TEXT,
        preview_path        TEXT,
        is_builtin          INTEGER NOT NULL DEFAULT 0,
        is_custom           INTEGER NOT NULL DEFAULT 1,
        parent_template_id  INTEGER,
        created_at          REAL NOT NULL,
        FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
        FOREIGN KEY (parent_template_id) REFERENCES templates(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_templates_brand ON templates(brand_id)",
    "CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category)",

    # ---- Phase G: Presets ----
    """
    CREATE TABLE IF NOT EXISTS presets (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_id                INTEGER,
        name                    TEXT NOT NULL,
        description             TEXT,
        template_id             INTEGER,
        layers_json             TEXT NOT NULL DEFAULT '[]',
        filter                  TEXT,
        caption_template        TEXT,
        schedule_settings_json  TEXT NOT NULL DEFAULT '{}',
        product_filter_json     TEXT NOT NULL DEFAULT '{}',
        created_at              REAL NOT NULL,
        FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
        FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_presets_brand ON presets(brand_id)",

    # ---- Phase A: Outputs (rendered brand-poster images/videos) ----
    """
    CREATE TABLE IF NOT EXISTS outputs (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_id            INTEGER,
        product_id          INTEGER,
        template_id         INTEGER,
        preset_id           INTEGER,
        type                TEXT NOT NULL DEFAULT 'image',
        file_path           TEXT NOT NULL,
        aspect_ratio        TEXT,
        file_size_bytes     INTEGER,
        filter_applied      TEXT,
        caption             TEXT,
        hashtags            TEXT,
        first_comment       TEXT,
        alt_text            TEXT,
        platform            TEXT,
        status              TEXT NOT NULL DEFAULT 'draft',
        scheduled_at        REAL,
        published_at        REAL,
        external_id         TEXT,
        external_url        TEXT,
        auto_approve        INTEGER NOT NULL DEFAULT 1,
        engagement_stats_json TEXT NOT NULL DEFAULT '{}',
        cost_usd            REAL NOT NULL DEFAULT 0,
        created_at          REAL NOT NULL,
        FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
        FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL,
        FOREIGN KEY (preset_id) REFERENCES presets(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_outputs_status_scheduled ON outputs(status, scheduled_at)",
    "CREATE INDEX IF NOT EXISTS idx_outputs_brand_created ON outputs(brand_id, created_at DESC)",

    # ---- Phase G: Automation rules ----
    """
    CREATE TABLE IF NOT EXISTS automation_rules (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_id        INTEGER,
        name            TEXT NOT NULL,
        trigger         TEXT NOT NULL,
        conditions_json TEXT NOT NULL DEFAULT '[]',
        action_json     TEXT NOT NULL DEFAULT '{}',
        is_active       INTEGER NOT NULL DEFAULT 1,
        last_run        REAL,
        created_at      REAL NOT NULL,
        FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_automation_rules_active ON automation_rules(is_active)",

    # ---- Phase C: Caption history ----
    """
    CREATE TABLE IF NOT EXISTS captions (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        output_id     INTEGER,
        variant_index INTEGER NOT NULL,
        content       TEXT NOT NULL,
        hashtags      TEXT,
        first_comment TEXT,
        alt_text      TEXT,
        is_selected   INTEGER NOT NULL DEFAULT 0,
        cache_key     TEXT,
        expires_at    REAL,
        brand_id      INTEGER,
        template_id   INTEGER,
        product_id    INTEGER,
        platform      TEXT,
        created_at    REAL NOT NULL,
        FOREIGN KEY (output_id) REFERENCES outputs(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_captions_output ON captions(output_id)",
    # NOTE: idx_captions_cache_key is created by the migration block
    # below after the cache_key column has been added to legacy DBs.

    # ---- Phase A: Filter presets (built-in + user) ----
    """
    CREATE TABLE IF NOT EXISTS filter_presets (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_id    INTEGER,
        name        TEXT NOT NULL,
        settings_json TEXT NOT NULL DEFAULT '{}',
        is_builtin  INTEGER NOT NULL DEFAULT 0,
        created_at  REAL NOT NULL,
        FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_filter_presets_brand_name ON filter_presets(IFNULL(brand_id, 0), name)",

    # ---- Phase F: Studio Pro suggestions ----
    """
    CREATE TABLE IF NOT EXISTS studio_suggestions (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_id          INTEGER,
        brief             TEXT NOT NULL,
        product_id        INTEGER,
        platform          TEXT,
        suggestion_json   TEXT NOT NULL DEFAULT '[]',
        confidence_score  REAL,
        was_accepted      INTEGER,
        log_json          TEXT NOT NULL DEFAULT '[]',
        created_at        REAL NOT NULL,
        FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_studio_suggestions_brand_created ON studio_suggestions(brand_id, created_at DESC)",
]


def init_db(path: Path | None = None) -> Path:
    """Ensure DB file + parent dir exist and migrations have run. Idempotent."""
    target = path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)
        # Idempotent column migrations for the templates table.
        _existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(templates)").fetchall()
        }
        if "scenes_json" not in _existing_cols:
            conn.execute(
                "ALTER TABLE templates ADD COLUMN scenes_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "transitions_json" not in _existing_cols:
            conn.execute(
                "ALTER TABLE templates ADD COLUMN transitions_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "audio_track_json" not in _existing_cols:
            conn.execute(
                "ALTER TABLE templates ADD COLUMN audio_track_json TEXT"
            )
        if "duration_s" not in _existing_cols:
            conn.execute(
                "ALTER TABLE templates ADD COLUMN duration_s INTEGER NOT NULL DEFAULT 0"
            )
        if "fps" not in _existing_cols:
            conn.execute(
                "ALTER TABLE templates ADD COLUMN fps INTEGER NOT NULL DEFAULT 30"
            )
        if "format" not in _existing_cols:
            conn.execute(
                "ALTER TABLE templates ADD COLUMN format TEXT NOT NULL DEFAULT 'image'"
            )
        # Phase F — Studio Pro: track suggestion runs and rationale.
        _ss_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(studio_suggestions)").fetchall()
        }
        if "run_id" not in _ss_cols:
            conn.execute("ALTER TABLE studio_suggestions ADD COLUMN run_id TEXT")
        if "template_id" not in _ss_cols:
            conn.execute("ALTER TABLE studio_suggestions ADD COLUMN template_id INTEGER")
        if "layer_overrides_json" not in _ss_cols:
            conn.execute(
                "ALTER TABLE studio_suggestions ADD COLUMN layer_overrides_json TEXT"
            )
        if "rationale_json" not in _ss_cols:
            conn.execute(
                "ALTER TABLE studio_suggestions ADD COLUMN rationale_json TEXT"
            )
        if "cost_usd" not in _ss_cols:
            conn.execute(
                "ALTER TABLE studio_suggestions ADD COLUMN cost_usd REAL NOT NULL DEFAULT 0"
            )
        if "status" not in _ss_cols:
            conn.execute(
                "ALTER TABLE studio_suggestions ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_studio_suggestions_run "
            "ON studio_suggestions(run_id)"
        )
        # Phase I: Refinement Studio — persist layers + filter settings on outputs.
        _out_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(outputs)").fetchall()
        }
        if "layers_json" not in _out_cols:
            conn.execute(
                "ALTER TABLE outputs ADD COLUMN layers_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "filter_settings" not in _out_cols:
            conn.execute(
                "ALTER TABLE outputs ADD COLUMN filter_settings TEXT NOT NULL DEFAULT '{}'"
            )
        # Phase I: output_versions table for Refinement Studio history.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS output_versions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                output_id       INTEGER NOT NULL,
                layers_json     TEXT NOT NULL DEFAULT '[]',
                filter_settings TEXT NOT NULL DEFAULT '{}',
                file_path       TEXT NOT NULL,
                thumbnail_path  TEXT,
                notes           TEXT,
                cost_usd        REAL NOT NULL DEFAULT 0,
                created_at      REAL NOT NULL,
                FOREIGN KEY (output_id) REFERENCES outputs(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_output_versions_output "
            "ON output_versions(output_id, created_at DESC)"
        )
        # Captions table — cache_key + expires_at were added later.
        _cap_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(captions)").fetchall()
        }
        if "cache_key" not in _cap_cols:
            conn.execute("ALTER TABLE captions ADD COLUMN cache_key TEXT")
        if "expires_at" not in _cap_cols:
            conn.execute(
                "ALTER TABLE captions ADD COLUMN expires_at REAL"
            )
        # Now that the column is guaranteed to exist, create the unique
        # index. The CREATE UNIQUE INDEX IF NOT EXISTS in the SCHEMA list
        # above assumes a fresh DB; for legacy DBs we have to defer this.
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_captions_cache_key "
                "ON captions(cache_key)"
            )
        except Exception:  # noqa: BLE001
            pass
        # Phase I — Skills system: user_skills table for DB-backed toggles.
        conn.execute(
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_skills_slug "
            "ON user_skills(slug)"
        )
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


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context-manager wrapper around :func:`get_conn` for ergonomic `with` blocks.

    The underlying connection is thread-local and pooled by ``get_conn``, so
    callers can use ``with app_db.connect() as c:`` without worrying about
    explicit close calls. The ``with`` block commits on success and rolls
    back on exception via the connection's ``__exit__`` semantics; the
    pooled connection itself is left open.
    """
    conn = get_conn(path)
    try:
        yield conn
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise