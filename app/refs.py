"""app/refs.py — reference library backed by SQLite.

A "reference" is a file in `references/uploads/`. The DB only stores
metadata that the filesystem can't: tag associations, plus auto-registration
so files dropped into the directory show up in the UI.

Vocabulary:
    reference_id  -> str (the filename, used as a stable id)
    tag           -> str, normalised (lowercased, dashed), max 32 chars

Tags are a flat vocabulary — no hierarchy, no color codes in v1. A tag
becomes available the first time it's used.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Iterable

from app import db as app_db

# Importing the upload dir from the server keeps a single source of truth.
# Tests monkeypatch app.server.REFERENCES_UPLOAD_DIR, so we go through that
# module at call time rather than capturing the value at import time.
from app import server as srv  # noqa: E402  (deferred import for test patching)


_TAG_RE = re.compile(r"[^a-z0-9\-]+")


def _normalise_tag(name: str) -> str:
    """Lowercase, ASCII-only, dash-separated. Falsy input returns ''."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name.strip().lower())
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Replace runs of disallowed chars with a single dash, then collapse
    # any run of dashes that the substitution introduced, then trim.
    cleaned = _TAG_RE.sub("-", ascii_only)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned[:32]


def upload_dir() -> Path:
    """Resolve the upload dir lazily so tests can monkeypatch it."""
    return srv.REFERENCES_UPLOAD_DIR


def _conn() -> sqlite3.Connection:
    return app_db.get_conn()


# ---------- scan + auto-register ----------

def _ensure_file_registered(filename: str) -> None:
    """Insert a row into reference_tags for a file that has no entries yet.

    We don't store a `references` table — the file IS the record. A file
    with no tags just has zero rows in `reference_tags`. This helper inserts
    a sentinel by writing nothing (no-op) — but it's the hook where future
    metadata (notes, dimensions) would land. Kept for symmetry.
    """
    return None


def _list_disk_files() -> list[Path]:
    d = upload_dir()
    if not d.exists():
        return []
    return sorted([p for p in d.iterdir() if p.is_file()], reverse=True)


def list_refs(tag: str | None = None) -> list[dict]:
    """Return all references with their tag lists. Optionally filter by tag."""
    files = _list_disk_files()
    out: list[dict] = []
    conn = _conn()
    for path in files:
        _ensure_file_registered(path.name)
        ext = path.suffix.lower().lstrip(".")
        size_kb = round(path.stat().st_size / 1024, 1)
        tags = get_tags(path.name)
        if tag and tag not in tags:
            continue
        out.append(
            {
                "id": path.name,
                "name": path.name,
                "ext": ext,
                "size_kb": size_kb,
                "tags": tags,
                "rel_url": f"/references/file/{path.name}",
            }
        )
    return out


# ---------- tags ----------

def all_tags() -> list[dict]:
    """Return all known tags with usage counts."""
    conn = _conn()
    rows = conn.execute(
        """
        SELECT t.name, COUNT(rt.reference_id) AS count
        FROM tags t
        LEFT JOIN reference_tags rt ON rt.tag_id = t.id
        GROUP BY t.id
        ORDER BY count DESC, t.name ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_tags(filename: str) -> list[str]:
    """Return sorted tag list for a reference."""
    conn = _conn()
    rows = conn.execute(
        """
        SELECT t.name FROM tags t
        JOIN reference_tags rt ON rt.tag_id = t.id
        WHERE rt.reference_id = ?
        ORDER BY t.name ASC
        """,
        (filename,),
    ).fetchall()
    return [r["name"] for r in rows]


def _tag_id(conn: sqlite3.Connection, name: str) -> int:
    """Insert a tag if missing, return its id."""
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO tags(name) VALUES (?)", (name,))
    return cur.lastrowid


def set_tags(filename: str, tag_names: Iterable[str]) -> list[str]:
    """Replace the tag set on a reference. Returns the new normalised list."""
    normalised = []
    seen = set()
    for raw in tag_names:
        n = _normalise_tag(raw)
        if n and n not in seen:
            seen.add(n)
            normalised.append(n)

    conn = _conn()
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM reference_tags WHERE reference_id = ?", (filename,))
        for name in normalised:
            tid = _tag_id(conn, name)
            conn.execute(
                "INSERT OR IGNORE INTO reference_tags(reference_id, tag_id) VALUES (?, ?)",
                (filename, tid),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return sorted(normalised)


def add_tag_to(filename: str, tag_name: str) -> list[str]:
    """Add a single tag (no-op if already present)."""
    n = _normalise_tag(tag_name)
    if not n:
        return get_tags(filename)
    current = set(get_tags(filename))
    if n in current:
        return sorted(current)
    return set_tags(filename, sorted(current | {n}))


def remove_tag_from(filename: str, tag_name: str) -> list[str]:
    """Remove a single tag."""
    current = set(get_tags(filename))
    current.discard(tag_name)
    return set_tags(filename, sorted(current))


def delete_tag_everywhere(tag_name: str) -> int:
    """Remove a tag from the vocabulary entirely. Returns rows deleted."""
    conn = _conn()
    cur = conn.execute("DELETE FROM tags WHERE name = ?", (tag_name,))
    return cur.rowcount


# ---------- safety helpers ----------

def resolve_to_path(filename: str) -> Path | None:
    """Resolve a reference filename to an absolute path on disk,
    returning None if it's missing or escapes the upload dir.

    This is the single source of truth for path-traversal guards.
    """
    if not filename or "/" in filename or "\\" in filename:
        return None
    d = upload_dir()
    candidate = (d / filename).resolve()
    if d not in candidate.parents and candidate != d:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def normalise_tag(name: str) -> str:
    """Public helper for templates/forms that need to validate input."""
    return _normalise_tag(name)