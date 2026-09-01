"""app.config_io. Phase G.3 — config import/export.

A single JSON document covers everything *configuration*:

    {
        "version": 1,
        "brands":            [...],
        "products":          [...],
        "templates":         [... custom templates only ...],
        "presets":           [...],
        "filter_presets":    [...],
        "automation_rules":  [...]
    }

We deliberately omit `outputs` (rendered history) and `captions`
(transient suggestions) so the export is portable and free of bloat.

Import is idempotent — names that collide with existing rows are
overwritten by default, callers can pass `merge=False` to get an error
on collisions.
"""

from __future__ import annotations

import json
from typing import Any

from app import db as app_db


SCHEMA_VERSION = 1


def export_config() -> dict:
    """Serialize the full config to a JSON-safe dict."""
    conn = app_db.get_conn()
    brands = [
        dict(r) for r in conn.execute("SELECT * FROM brands").fetchall()
    ]
    products = [
        dict(r) for r in conn.execute("SELECT * FROM products").fetchall()
    ]
    templates = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM templates WHERE is_custom = 1"
        ).fetchall()
    ]
    presets = [
        dict(r) for r in conn.execute("SELECT * FROM presets").fetchall()
    ]
    filter_presets = [
        dict(r) for r in conn.execute("SELECT * FROM filter_presets").fetchall()
    ]
    automation_rules = [
        dict(r)
        for r in conn.execute("SELECT * FROM automation_rules").fetchall()
    ]

    def jsonify(items):
        return [json.loads(json.dumps(i, default=str)) for i in items]

    return {
        "version": SCHEMA_VERSION,
        "brands": jsonify(brands),
        "products": jsonify(products),
        "templates": jsonify(templates),
        "presets": jsonify(presets),
        "filter_presets": jsonify(filter_presets),
        "automation_rules": jsonify(automation_rules),
    }


def import_config(doc: dict, *, merge: bool = True) -> dict:
    """Restore a previously exported config into the current DB.

    With `merge=True` (default), rows whose name conflicts are replaced
    via `INSERT OR REPLACE`. With `merge=False`, name conflicts raise
    `ValueError`.
    """
    if not isinstance(doc, dict):
        raise ValueError("config must be a JSON object")
    if doc.get("version") not in (SCHEMA_VERSION, None, 1):
        raise ValueError(
            f"unsupported config version {doc.get('version')!r}"
        )

    counts: dict[str, int] = {}
    conn = app_db.get_conn()
    for section in (
        "brands",
        "products",
        "templates",
        "presets",
        "filter_presets",
        "automation_rules",
    ):
        rows = doc.get(section) or []
        if not isinstance(rows, list):
            raise ValueError(f"{section} must be a list")
        if not rows:
            counts[section] = 0
            continue
        # Restrict to columns that actually exist on the table; protects
        # against exports from older/different schemas.
        existing_cols = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({section})").fetchall()
        }
        candidate_cols = [c for c in rows[0].keys() if c in existing_cols]
        if "id" in candidate_cols:
            candidate_cols.remove("id")
        cols = candidate_cols
        # Backfill required defaults that the export might have omitted.
        required = _required_defaults(section, existing_cols)
        # Always include required columns even if the row omits them —
        # this lets clients send partial config without violating
        # NOT NULL constraints.
        for col in required:
            if col not in cols and col in existing_cols:
                cols.append(col)
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        # With merge=True we use INSERT OR REPLACE so name collisions
        # silently overwrite the existing row. Without merge, we keep
        # the strict semantics and error out.
        verb = "INSERT OR REPLACE" if merge else "INSERT"
        sql = f"{verb} INTO {section} ({col_list}) VALUES ({placeholders})"
        n = 0
        for row in rows:
            values = [row.get(c) for c in cols]
            for col, default in required.items():
                if col in cols and (values[cols.index(col)] is None
                                     or values[cols.index(col)] == ""):
                    values[cols.index(col)] = default()
            if not merge:
                if _row_exists(conn, section, row):
                    raise ValueError(
                        f"{section} row with name {row.get('name')!r} "
                        "already exists"
                    )
            conn.execute(sql, values)
            n += 1
        counts[section] = n
    conn.commit()
    return counts


def _required_defaults(section: str, existing: set[str]) -> dict[str, callable]:
    import time
    now = time.time
    defaults: dict[str, callable] = {}
    if section == "brands":
        for col in ("created_at", "updated_at"):
            if col in existing:
                defaults[col] = now
    if section == "products":
        for col in ("created_at", "updated_at"):
            if col in existing:
                defaults[col] = now
    if section == "templates":
        for col in ("created_at",):
            if col in existing:
                defaults[col] = now
    if section == "presets":
        for col in ("created_at",):
            if col in existing:
                defaults[col] = now
    if section == "automation_rules":
        for col in ("created_at",):
            if col in existing:
                defaults[col] = now
    if section == "filter_presets":
        for col in ("created_at",):
            if col in existing:
                defaults[col] = now
    return defaults


def _row_exists(conn, table: str, row: dict) -> bool:
    name = row.get("name")
    if not name:
        return False
    cur = conn.execute(f"SELECT 1 FROM {table} WHERE name = ? LIMIT 1",
                       (name,))
    return cur.fetchone() is not None


__all__ = ["SCHEMA_VERSION", "export_config", "import_config"]