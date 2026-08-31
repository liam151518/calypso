"""app/brand.py — brand profiles + active brand pointer.

A brand profile is a bundle of stylistic context that is prepended to every
Generate submit so the model gets the same vocabulary the user has locked in.
Profiles live in SQLite; the "active brand" pointer is also stored there so
there's exactly one source of truth.

The brand system is intentionally light: no hierarchy, no inheritance, no
versioning. If the user needs two flavours of the same brand, they make two
profiles and switch.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Iterable

from app import db as app_db


ACTIVE_BRAND_KEY = "active_brand_id"


# ---------- colour helpers ----------

def _normalise_hex(c: str) -> str:
    """Accept 'ff6a1f', '#FF6A1F', or 'rgb(255,106,31)' — return '#rrggbb'."""
    c = (c or "").strip()
    if not c:
        return ""
    if c.startswith("#"):
        c = c[1:]
    # Handle 'rgb(r, g, b)' defensively.
    if c.lower().startswith("rgb"):
        try:
            inside = c[c.find("(") + 1 : c.find(")")]
        except ValueError:
            return ""
        nums = [s for s in inside.replace(",", " ").split() if s]
        try:
            r, g, b = [int(float(n)) for n in nums[:3]]
        except (ValueError, TypeError):
            return ""
        return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"
    if len(c) == 3 and all(ch in "0123456789abcdef" for ch in c.lower()):
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6 or any(ch not in "0123456789abcdef" for ch in c.lower()):
        return ""
    return f"#{c.lower()}"


def parse_palette(raw: str | Iterable[str] | None) -> list[str]:
    """Parse a palette from many input shapes: JSON, comma-separated, or iterable.
    Returns a de-duplicated list of normalised #rrggbb strings (max 12)."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        s = raw.strip()
        # Single rgb() string passes through directly.
        if s.lower().startswith("rgb"):
            n = _normalise_hex(s)
            return [n] if n else []
        if s.startswith("["):
            try:
                raw = json.loads(s)
            except json.JSONDecodeError:
                raw = [p.strip() for p in s.replace("\n", ",").split(",")]
        else:
            raw = [p.strip() for p in s.replace("\n", ",").split(",")]
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        n = _normalise_hex(str(item))
        if n and n not in seen:
            seen.add(n)
            out.append(n)
            if len(out) >= 12:
                break
    return out


# ---------- settings (key/value) ----------

def _setting_get(key: str) -> str | None:
    conn = app_db.get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _setting_set(key: str, value: str | None) -> None:
    conn = app_db.get_conn()
    if value is None or value == "":
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        return
    conn.execute(
        """
        INSERT INTO settings(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


# ---------- brand CRUD ----------

def _row_to_brand(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["palette"] = json.loads(d.get("palette_json") or "[]")
    except json.JSONDecodeError:
        d["palette"] = []
    d.pop("palette_json", None)
    return d


def list_brands() -> list[dict]:
    conn = app_db.get_conn()
    rows = conn.execute(
        "SELECT * FROM brand_profiles ORDER BY updated_at DESC"
    ).fetchall()
    return [_row_to_brand(r) for r in rows]


def get_brand(brand_id: int | str | None) -> dict | None:
    if brand_id is None or brand_id == "":
        return None
    conn = app_db.get_conn()
    row = conn.execute(
        "SELECT * FROM brand_profiles WHERE id = ?", (brand_id,)
    ).fetchone()
    return _row_to_brand(row) if row else None


def save_brand(
    name: str,
    tagline: str = "",
    audience: str = "",
    palette: list[str] | str | None = None,
    typography: str = "",
    voice: str = "",
    do_examples: str = "",
    dont_examples: str = "",
    style_guide: str = "",
    brand_id: int | None = None,
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Brand name is required")
    parsed_palette = parse_palette(palette or [])
    palette_json = json.dumps(parsed_palette)

    now = time.time()
    conn = app_db.get_conn()
    if brand_id is None:
        cur = conn.execute(
            """
            INSERT INTO brand_profiles(
                name, tagline, audience, palette_json, typography,
                voice, do_examples, dont_examples, style_guide,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name, tagline, audience, palette_json, typography,
                voice, do_examples, dont_examples, style_guide,
                now, now,
            ),
        )
        brand_id = cur.lastrowid
    else:
        conn.execute(
            """
            UPDATE brand_profiles SET
                name = ?, tagline = ?, audience = ?, palette_json = ?,
                typography = ?, voice = ?, do_examples = ?, dont_examples = ?,
                style_guide = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name, tagline, audience, palette_json, typography,
                voice, do_examples, dont_examples, style_guide,
                now, brand_id,
            ),
        )
    return get_brand(brand_id) or {}


def delete_brand(brand_id: int | str) -> bool:
    conn = app_db.get_conn()
    cur = conn.execute("DELETE FROM brand_profiles WHERE id = ?", (brand_id,))
    if cur.rowcount and str(_setting_get(ACTIVE_BRAND_KEY)) == str(brand_id):
        _setting_set(ACTIVE_BRAND_KEY, None)
    return cur.rowcount > 0


# ---------- active brand ----------

def get_active_brand() -> dict | None:
    """Return the active brand profile, or None if no active brand is set."""
    raw = _setting_get(ACTIVE_BRAND_KEY)
    if not raw:
        return None
    return get_brand(raw)


def set_active_brand(brand_id: int | str | None) -> None:
    """Activate a brand, or clear the active brand if id is None/empty."""
    if brand_id is None or brand_id == "":
        _setting_set(ACTIVE_BRAND_KEY, None)
        return
    brand = get_brand(brand_id)
    if brand is None:
        raise ValueError(f"No brand with id={brand_id!r}")
    _setting_set(ACTIVE_BRAND_KEY, str(brand["id"]))


def clear_active_brand() -> None:
    _setting_set(ACTIVE_BRAND_KEY, None)


# ---------- compose ----------

def compose_prompt(prompt: str, brand_id: int | str | None = None) -> str:
    """Prepend a brand block to the user prompt. If no brand is active,
    the user prompt is returned unchanged.

    The user prompt is always preserved verbatim at the bottom of the
    block — so reading the original prompt is unambiguous.
    """
    brand = get_brand(brand_id) if brand_id is not None else get_active_brand()
    if brand is None:
        return prompt

    parts: list[str] = []
    parts.append("[BRAND]")
    parts.append(f"Name: {brand['name']}")
    if brand.get("tagline"):
        parts.append(f"Tagline: {brand['tagline']}")
    if brand.get("audience"):
        parts.append(f"Audience: {brand['audience']}")
    palette = brand.get("palette") or []
    if palette:
        parts.append("Palette: " + ", ".join(palette))
    if brand.get("typography"):
        parts.append(f"Typography: {brand['typography']}")
    if brand.get("voice"):
        parts.append(f"Voice: {brand['voice']}")
    if brand.get("do_examples"):
        parts.append("Do: " + " ; ".join(_lines(brand["do_examples"])))
    if brand.get("dont_examples"):
        parts.append("Don't: " + " ; ".join(_lines(brand["dont_examples"])))
    parts.append("[/BRAND]")

    if brand.get("style_guide"):
        parts.append("[STYLE GUIDE]")
        parts.append(brand["style_guide"].strip())
        parts.append("[/STYLE GUIDE]")

    parts.append("[PROMPT]")
    parts.append((prompt or "").strip())
    parts.append("[/PROMPT]")

    return "\n".join(parts)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]