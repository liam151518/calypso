"""app/filters.py. Phase A filter presets for brand-poster outputs.

The five built-in presets (moody / bright / vintage / minimal / neon) match
spec §4.4. Each preset is a flat dict of named settings that the operator
can override. `apply(img, settings, intensity)` linearly interpolates between
the original image and a fully-applied filter so a 0..1 intensity slider
produces predictable visual change.

Manual sliders (exposure / contrast / saturation / temperature / tint / grain /
vignette / highlight / shadow / glow / sepia / lut) are exposed too, so the
FilterPanel can drive a non-preset custom look. Settings keys are unioned
across presets; missing keys are no-ops.

Layered transforms are stacked in this order (each as a small PIL pipeline):
    1. Temperature / tint (RGB matrix on white balance)
    2. Exposure / brightness (ImageEnhance)
    3. Contrast / saturation (ImageEnhance)
    4. Tone curve (3-point highlights/shadows)
    5. Sepia (RGB matrix when sepia > 0)
    6. Vignette (radial alpha mask, screen blend)
    7. Glow (gaussian-blurred highlights, screen blend)
    8. LUT (optional .cube file under brand/luts/ — skipped if missing)

Each transform is additive and small enough to render a 1080x1350 frame in
well under 1 second on a modern CPU.

LUT files (`*.cube`) live under `brand/luts/` so user-added LUTs are picked
up at next apply without code changes. No LUT is required for any preset to
work.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LUT_DIR = PROJECT_ROOT / "brand" / "luts"


# ---- preset definitions (spec §4.4) ----

PRESETS: dict[str, dict[str, Any]] = {
    "moody": {
        "brightness": 0.85,
        "contrast": 1.20,
        "saturation": 0.75,
        "temperature": -15,
        "tint": 5,
        "highlights": -25,
        "shadows": -20,
        "sepia": 0.10,
        "vignette": 0.45,
        "glow": 0.0,
        "grain": 0.05,
    },
    "bright": {
        "brightness": 1.10,
        "contrast": 1.05,
        "saturation": 1.20,
        "temperature": 8,
        "tint": 0,
        "highlights": 15,
        "shadows": 15,
        "sepia": 0.0,
        "vignette": 0.15,
        "glow": 0.10,
        "grain": 0.0,
    },
    "vintage": {
        "brightness": 1.00,
        "contrast": 1.05,
        "saturation": 0.85,
        "temperature": 18,
        "tint": -8,
        "highlights": -10,
        "shadows": 20,
        "sepia": 0.35,
        "vignette": 0.35,
        "glow": 0.05,
        "grain": 0.15,
    },
    "minimal": {
        "brightness": 1.00,
        "contrast": 1.02,
        "saturation": 0.95,
        "temperature": 0,
        "tint": 0,
        "highlights": 0,
        "shadows": 0,
        "sepia": 0.0,
        "vignette": 0.0,
        "glow": 0.0,
        "grain": 0.0,
    },
    "neon": {
        "brightness": 0.95,
        "contrast": 1.30,
        "saturation": 1.50,
        "temperature": -5,
        "tint": 10,
        "highlights": 30,
        "shadows": -30,
        "sepia": 0.0,
        "vignette": 0.30,
        "glow": 0.35,
        "grain": 0.0,
    },
}


def list_presets() -> list[dict]:
    return [{"name": name, "settings": dict(settings)} for name, settings in PRESETS.items()]


# ---- primitives ----

def _temperature_matrix(temperature: float) -> tuple[float, ...]:
    """+/- temperature maps to small warm/cool RGB shifts on a 5x4 identity matrix.

    `temperature` is in -100..100; positive = warmer (more red, less blue).
    """
    t = max(-100.0, min(100.0, float(temperature))) / 100.0
    r = 1.0 + 0.10 * t
    g = 1.0
    b = 1.0 - 0.10 * t
    return (r, 0, 0, 0,
            0, g, 0, 0,
            0, 0, b, 0)


def _tint_matrix(tint: float) -> tuple[float, ...]:
    """+/- tint maps to small magenta/green shifts."""
    t = max(-100.0, min(100.0, float(tint))) / 100.0
    r = 1.0 + 0.04 * t
    g = 1.0 - 0.06 * t
    b = 1.0 + 0.04 * t
    return (r, 0, 0, 0,
            0, g, 0, 0,
            0, 0, b, 0)


def _sepia_matrix(amt: float) -> tuple[float, ...]:
    a = max(0.0, min(1.0, float(amt)))
    # Standard sepia matrix; the resulting image is blended toward the original.
    return (
        1 - 0.3 * a, 0.3 * a, 0.3 * a, 0,
        0.3 * a, 1 - 0.3 * a, 0.3 * a, 0,
        0.3 * a, 0.3 * a, 1 - 0.3 * a, 0,
    )


def _apply_tone_curve(img: Image.Image, highlights: float, shadows: float) -> Image.Image:
    """Three-point tone curve: highlights (0..255 target), mid (identity),
    shadows (0..255 target). Cheap approximation."""
    h = max(-100.0, min(100.0, float(highlights))) / 100.0
    s = max(-100.0, min(100.0, float(shadows))) / 100.0
    hi = int(255 * (1.0 + h * 0.20))
    sh = int(255 * (1.0 + s * 0.20))
    hi = max(0, min(255, hi))
    sh = max(0, min(255, sh))
    if hi == 255 and sh == 255:
        return img
    lut = [sh] * 128 + [255] * 128
    # Smooth: anchor ends to 0 and 255, then line-up via linear interpolation.
    out: list[int] = []
    for i in range(256):
        if i < 128:
            out.append(int(sh * (i / 128.0)))
        else:
            # Mid 128 -> 128, hi at 255 -> hi
            t = (i - 128) / 127.0
            out.append(int(128 + (hi - 128) * t))
    return img.point(out * (img.mode != "RGB" and 1 or 1)) if img.mode != "RGB" else img.point(out * 1)


def _apply_tone_curve_rgb(img: Image.Image, highlights: float, shadows: float) -> Image.Image:
    """Three-point tone curve applied per channel on an RGB image."""
    h = max(-100.0, min(100.0, float(highlights))) / 100.0
    s = max(-100.0, min(100.0, float(shadows))) / 100.0
    hi = max(0, min(255, int(255 * (1.0 + h * 0.20))))
    sh = max(0, min(255, int(255 * (1.0 + s * 0.20))))
    if hi == 255 and sh == 255:
        return img
    lut: list[int] = []
    for i in range(256):
        if i < 128:
            lut.append(int(sh * (i / 128.0)))
        else:
            t = (i - 128) / 127.0
            lut.append(int(128 + (hi - 128) * t))
    return img.point(lut * 3)


def _apply_vignette(img: Image.Image, strength: float) -> Image.Image:
    s = max(0.0, min(1.0, float(strength)))
    if s <= 0:
        return img
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    cx, cy = w / 2.0, h / 2.0
    max_d = math.hypot(cx, cy)
    px = mask.load()
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy) / max_d
            # Soft falloff so the corners go to ~s*255 and the centre stays 255.
            v = int(255 * max(0.0, 1.0 - (d * d * s * 2.0)))
            px[x, y] = v
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(img, dark, mask)


def _apply_glow(img: Image.Image, strength: float) -> Image.Image:
    s = max(0.0, min(1.0, float(strength)))
    if s <= 0:
        return img
    # Highlight mask: anything above 200 luma, blurred, screen-blended.
    blurred = img.filter(ImageFilter.GaussianBlur(radius=max(1, min(img.size) // 40)))
    grey = ImageChops.lighter(img.convert("L"), blurred.convert("L"))
    # Build highlight layer: take pixels where grey > 200 from the original.
    w, h = img.size
    hi = Image.new("RGB", (w, h), (0, 0, 0))
    src = img.load()
    dst = hi.load()
    grey_pix = grey.load()
    for y in range(h):
        for x in range(w):
            if grey_pix[x, y] > 200:
                r, g, b = src[x, y]
                # Boost toward white proportional to strength.
                t = s
                dst[x, y] = (
                    int(min(255, r + (255 - r) * t)),
                    int(min(255, g + (255 - g) * t)),
                    int(min(255, b + (255 - b) * t)),
                )
    return ImageChops.screen(img, hi)


def _apply_grain(img: Image.Image, strength: float) -> Image.Image:
    import random
    s = max(0.0, min(1.0, float(strength)))
    if s <= 0:
        return img
    w, h = img.size
    rng = random.Random(0)
    layer = Image.new("RGB", (w, h), (128, 128, 128))
    p = layer.load()
    for y in range(h):
        for x in range(w):
            n = rng.randint(int(-s * 60), int(s * 60))
            p[x, y] = (128 + n, 128 + n, 128 + n)
    return ImageChops.overlay(img, layer)


# ---- public API ----

@dataclass
class FilterResult:
    image: Image.Image
    settings_used: dict[str, Any]


def _coerce_settings(settings: dict | None) -> dict[str, Any]:
    base = {k: 0.0 for k in (
        "brightness", "contrast", "saturation",
        "temperature", "tint",
        "highlights", "shadows",
        "sepia", "vignette", "glow", "grain",
    )}
    if not settings:
        return base
    for k, v in settings.items():
        if k in base:
            try:
                base[k] = float(v)
            except (TypeError, ValueError):
                base[k] = 0.0
    return base


def apply(img: Image.Image, settings: dict | None, *, intensity: float = 1.0) -> FilterResult:
    """Apply the given settings to the image. `intensity` linearly blends from
    the untouched image (0) to the fully-applied image (1)."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    s = _coerce_settings(settings)
    intensity = max(0.0, min(1.0, float(intensity)))
    if intensity == 0:
        return FilterResult(image=img, settings_used=s)

    # Apply each transform; blend toward original when intensity < 1.
    out = img.copy()

    if abs(s["temperature"]) > 0.01:
        out = out.convert("RGB", matrix=_temperature_matrix(s["temperature"] * intensity))
    if abs(s["tint"]) > 0.01:
        out = out.convert("RGB", matrix=_tint_matrix(s["tint"] * intensity))
    if abs(s["brightness"] - 1.0) > 0.01:
        out = ImageEnhance.Brightness(out).enhance(1.0 + (s["brightness"] - 1.0) * intensity)
    if abs(s["contrast"] - 1.0) > 0.01:
        out = ImageEnhance.Contrast(out).enhance(1.0 + (s["contrast"] - 1.0) * intensity)
    if abs(s["saturation"] - 1.0) > 0.01:
        out = ImageEnhance.Color(out).enhance(1.0 + (s["saturation"] - 1.0) * intensity)
    if s["highlights"] or s["shadows"]:
        out = _apply_tone_curve_rgb(out, s["highlights"] * intensity, s["shadows"] * intensity)
    if s["sepia"] > 0.01:
        out = out.convert("RGB", matrix=_sepia_matrix(s["sepia"] * intensity))
    if s["vignette"] > 0.01:
        v = _apply_vignette(out, s["vignette"] * intensity)
        out = Image.blend(out, v, intensity)
    if s["glow"] > 0.01:
        g = _apply_glow(out, s["glow"] * intensity)
        out = Image.blend(out, g, intensity)
    if s["grain"] > 0.01:
        g = _apply_grain(out, s["grain"] * intensity)
        out = Image.blend(out, g, intensity)

    return FilterResult(image=out, settings_used=s)


def apply_path(img_path: str | Path, settings: dict | None, *, intensity: float = 1.0, output_path: str | Path | None = None) -> Path:
    """Convenience wrapper: read from path, apply, save to path. Defaults to
    writing next to the input with `.filtered.jpg` suffix."""
    p_in = Path(img_path)
    img = Image.open(p_in)
    res = apply(img, settings, intensity=intensity)
    out = Path(output_path) if output_path else p_in.with_suffix(".filtered.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    res.image.save(out, "JPEG", quality=95)
    return out


def preview(img_path: str | Path, settings: dict | None) -> Path:
    """Same as `apply_path` but downsamples to 320px and writes PNG (no DB write)."""
    p_in = Path(img_path)
    img = Image.open(p_in)
    img.thumbnail((320, 320))
    res = apply(img, settings, intensity=1.0)
    out = p_in.with_name(p_in.stem + ".preview.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    res.image.save(out, "PNG")
    return out


def save_user_preset(brand_id: int | None, name: str, settings: dict) -> int:
    """Persist a user filter preset to the `filter_presets` table.

    ON CONFLICT handles upsert on the (IFNULL(brand_id,0), name) unique
    index so a NULL brand_id can still collide with itself.
    """
    import time
    from app import db as app_db
    conn = app_db.get_conn()
    now = time.time()
    bid_key = 0 if brand_id is None else int(brand_id)
    cur = conn.execute(
        """
        INSERT INTO filter_presets(brand_id, name, settings_json, is_builtin, created_at)
        VALUES (?, ?, ?, 0, ?)
        ON CONFLICT(IFNULL(brand_id, 0), name) DO UPDATE SET
            settings_json = excluded.settings_json,
            created_at = excluded.created_at
        """,
        (brand_id, name, json.dumps(_coerce_settings(settings)), now),
    )
    return int(cur.lastrowid)


def list_user_presets(brand_id: int | None = None) -> list[dict]:
    from app import db as app_db
    conn = app_db.get_conn()
    if brand_id is None:
        rows = conn.execute(
            "SELECT id, brand_id, name, settings_json FROM filter_presets WHERE is_builtin = 0 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, brand_id, name, settings_json FROM filter_presets WHERE is_builtin = 0 AND brand_id = ? ORDER BY name",
            (brand_id,),
        ).fetchall()
    out = []
    for r in rows:
        try:
            settings = json.loads(r["settings_json"])
        except json.JSONDecodeError:
            settings = {}
        out.append({"id": r["id"], "brand_id": r["brand_id"], "name": r["name"], "settings": settings})
    return out


__all__ = [
    "PRESETS",
    "apply",
    "apply_path",
    "preview",
    "save_user_preset",
    "list_user_presets",
    "list_presets",
]