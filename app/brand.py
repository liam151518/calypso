"""app/brand.py. Brand profiles + active brand pointer.

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
import re
import sqlite3
import time
from typing import Iterable

from app import db as app_db


ACTIVE_BRAND_KEY = "active_brand_id"


# ---------- colour helpers ----------

def _normalise_hex(c: str) -> str:
    """Accept 'ff6a1f', '#FF6A1F', or 'rgb(255,106,31)'. Return '#rrggbb'."""
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
    # Phase A.7: DNA v2 fields. All optional; passed through to brands table.
    fonts: dict | str | None = None,
    logo_path: str | None = None,
    watermark_path: str | None = None,
    voice_tone: str | None = None,
    banned_words: list[str] | str | None = None,
    emoji_policy: str | None = None,
    default_filter: str | None = None,
    default_aspect_ratio: str | None = None,
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Brand name is required")
    parsed_palette = parse_palette(palette or [])
    palette_json = json.dumps(parsed_palette)

    # DNA v2 helpers
    if isinstance(fonts, str):
        try:
            fonts_obj = json.loads(fonts)
        except json.JSONDecodeError:
            fonts_obj = {}
    else:
        fonts_obj = dict(fonts or {})
    if isinstance(banned_words, str):
        banned_words_list = [w.strip().lower() for w in re.split(r"[,;\n]", banned_words) if w.strip()]
    else:
        banned_words_list = [str(w).strip().lower() for w in (banned_words or []) if str(w).strip()]
    fonts_json = json.dumps(fonts_obj)
    banned_words_json = json.dumps(banned_words_list)

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

    # Write through to the new `brands` table (Phase A.7). The brands row is
    # keyed by name; we keep it in sync with brand_profiles so the spec's
    # DNA v2 fields are usable while brand_profiles stays for back-compat.
    _upsert_brands_v2(
        brand_id=int(brand_id),
        name=name,
        tagline=tagline,
        audience=audience,
        palette=parsed_palette,
        typography=typography,
        voice=voice,
        do_examples=do_examples,
        dont_examples=dont_examples,
        style_guide=style_guide,
        fonts_json=fonts_json,
        logo_path=logo_path,
        watermark_path=watermark_path,
        voice_tone=voice_tone,
        banned_words_json=banned_words_json,
        emoji_policy=emoji_policy,
        default_filter=default_filter,
        default_aspect_ratio=default_aspect_ratio,
        brand_profile_id=int(brand_id),
        now=now,
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
    block, so reading the original prompt is unambiguous.
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


# ---- Phase A.7: Brand DNA v2 ----

def _row_to_brand_v2(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for key, default in (
        ("palette", []),
        ("fonts", {}),
        ("banned_words", []),
    ):
        try:
            d[key] = json.loads(d.pop(f"{key}_json", default) or json.dumps(default))
        except json.JSONDecodeError:
            d[key] = default
    for k in ("is_builtin", "is_active"):
        if k in d:
            d[k] = bool(d[k])
    return d


def _upsert_brands_v2(
    *,
    brand_id: int,
    name: str,
    tagline: str,
    audience: str,
    palette: list[str],
    typography: str,
    voice: str,
    do_examples: str,
    dont_examples: str,
    style_guide: str,
    fonts_json: str,
    logo_path: str | None,
    watermark_path: str | None,
    voice_tone: str | None,
    banned_words_json: str,
    emoji_policy: str | None,
    default_filter: str | None,
    default_aspect_ratio: str | None,
    brand_profile_id: int,
    now: float,
) -> None:
    """Insert/update the new `brands` row for back-compat. Pure side effect."""
    conn = app_db.get_conn()
    palette_json = json.dumps(palette)
    # Match by brand_profile_id if we have it (so re-saving the old row
    # updates the new row), else by name (so two rows never exist).
    row = conn.execute(
        "SELECT id FROM brands WHERE brand_profile_id = ? LIMIT 1",
        (brand_profile_id,),
    ).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT id FROM brands WHERE lower(name) = lower(?) LIMIT 1",
            (name,),
        ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO brands(
                name, tagline, audience, palette_json, typography,
                voice, voice_tone, do_examples, dont_examples, style_guide,
                fonts_json, logo_path, watermark_path,
                banned_words_json, emoji_policy,
                default_filter, default_aspect_ratio,
                brand_profile_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name, tagline, audience, palette_json, typography,
                voice, voice_tone, do_examples, dont_examples, style_guide,
                fonts_json, logo_path, watermark_path,
                banned_words_json, emoji_policy,
                default_filter, default_aspect_ratio,
                brand_profile_id, now, now,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE brands SET
                    name = ?, tagline = ?, audience = ?, palette_json = ?,
                    typography = ?, voice = ?, voice_tone = ?,
                    do_examples = ?, dont_examples = ?, style_guide = ?,
                    fonts_json = ?, logo_path = ?, watermark_path = ?,
                    banned_words_json = ?, emoji_policy = ?,
                    default_filter = ?, default_aspect_ratio = ?,
                    brand_profile_id = ?, updated_at = ?
                WHERE id = ?
            """,
            (
                name, tagline, audience, palette_json, typography,
                voice, voice_tone, do_examples, dont_examples, style_guide,
                fonts_json, logo_path, watermark_path,
                banned_words_json, emoji_policy,
                default_filter, default_aspect_ratio,
                brand_profile_id, now, row["id"],
            ),
        )


def get_brand_v2(brand_id: int | None) -> dict | None:
    """Read from the new `brands` table (Phase A.7 shape)."""
    if brand_id is None:
        return None
    conn = app_db.get_conn()
    row = conn.execute(
        """
        SELECT id, name, tagline, audience, palette_json, typography,
               voice, voice_tone, do_examples, dont_examples, style_guide,
               fonts_json, logo_path, watermark_path,
               banned_words_json, emoji_policy,
               default_filter, default_aspect_ratio,
               brand_profile_id, created_at, updated_at
        FROM brands WHERE id = ?
        """,
        (brand_id,),
    ).fetchone()
    return _row_to_brand_v2(row)


def get_active_brand_v2() -> dict | None:
    raw = _setting_get(ACTIVE_BRAND_KEY)
    if not raw:
        return None
    return get_brand_v2(int(raw))


def list_brands_v2() -> list[dict]:
    conn = app_db.get_conn()
    rows = conn.execute(
        "SELECT id, name, tagline, audience, palette_json, typography, "
        "voice, voice_tone, do_examples, dont_examples, style_guide, "
        "fonts_json, logo_path, watermark_path, "
        "banned_words_json, emoji_policy, "
        "default_filter, default_aspect_ratio, "
        "brand_profile_id, created_at, updated_at "
        "FROM brands ORDER BY updated_at DESC"
    ).fetchall()
    return [_row_to_brand_v2(r) for r in rows]


def load_font(brand: dict | None, role: str) -> str | None:
    """Resolve the brand-supplied font filename for the given role.

    Brand fonts live under `brand/fonts/`. Returns the bare filename or None
    if the brand doesn't supply a font for the role.
    """
    if not brand:
        return None
    fonts = brand.get("fonts") or {}
    if not isinstance(fonts, dict):
        return None
    return fonts.get(role) or fonts.get("default")


def _split_words(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"\w+", text or "")]


def enforce_prompt(prompt: str, brand: dict | None) -> str:
    """Strip banned words; append voice tone + audience tag. Pure function."""
    if not brand:
        return prompt
    banned = set(brand.get("banned_words") or [])
    if banned:
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(w) for w in banned) + r")\b",
            flags=re.IGNORECASE,
        )
        prompt = pattern.sub("[redacted]", prompt)
    extras: list[str] = []
    voice_tone = brand.get("voice_tone")
    if voice_tone:
        extras.append(f"[tone: {voice_tone}]")
    audience = brand.get("audience")
    if audience:
        extras.append(f"[audience: {audience}]")
    if extras:
        prompt = (prompt or "").rstrip() + "\n" + " ".join(extras)
    return prompt


def enforce_layers(layers: list[dict], brand: dict | None) -> list[dict]:
    """Lock brand-locked layers and replace their text config content with
    brand-approved tone words. Returns a new list (does not mutate input).
    """
    if not brand:
        return layers
    palette = brand.get("palette") or []
    primary = palette[0] if palette else "#ff6a1f"
    out = []
    for layer in layers:
        if not isinstance(layer, dict):
            out.append(layer)
            continue
        if layer.get("id") in (brand.get("brand_locks") or []):
            layer = {**layer, "locked": True}
        cfg = layer.get("config") if isinstance(layer.get("config"), dict) else {}
        if layer.get("type") == "text" and cfg:
            new_cfg = dict(cfg)
            new_cfg["color"] = cfg.get("color") or primary
            layer = {**layer, "config": new_cfg}
        out.append(layer)
    return out


__all__ = [
    "ACTIVE_BRAND_KEY",
    "list_brands",
    "get_brand",
    "save_brand",
    "delete_brand",
    "get_active_brand",
    "set_active_brand",
    "clear_active_brand",
    "compose_prompt",
    "parse_palette",
    "list_brands_v2",
    "get_brand_v2",
    "get_active_brand_v2",
    "load_font",
    "enforce_prompt",
    "enforce_layers",
]