"""app/utils/validators.py. JSON-schema validation for brand-poster artifacts.

Mirrors the TypeScript interfaces from spec §4.1 (Template / Layer / LayerConfig).
Both `app/templates.py` (CRUD) and `web/src/lib/types.ts` should stay in sync with
this module — see `docs/templates.md` for the hand-mirrored types.

The schemas here are deliberately strict at the shape level (required keys,
enum-like literals, percent-bounds on x/y/w/h/opacity). Business rules like
"brand_locks cannot contain layer ids that don't exist" are enforced by
`app/templates.validate_template` so the error message can include the bad id.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


LAYER_TYPES = (
    "ai_background",
    "ai_image",
    "product_cutout",
    "text",
    "image",
    "shape",
    "video_background",
)

ASPECT_RATIOS = ("1:1", "4:5", "9:16", "16:9")
SUPPORTED_TEMPLATE_CATEGORIES = (
    "product",
    "lifestyle",
    "announcement",
    "sale",
    "ugc",
    "minimal",
)


# ---- per-layer-type config schemas ----

_BACKGROUND_CONFIG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["prompt"],
    "properties": {
        "prompt": {"type": "string", "minLength": 1, "maxLength": 4000},
        "negative_prompt": {"type": "string", "maxLength": 4000},
        "model": {"type": "string", "maxLength": 120},
        "seed": {"type": "integer", "minimum": 0, "maximum": 2_147_483_647},
    },
}

_PRODUCT_CONFIG = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "slot": {
            "type": "string",
            "enum": ["center", "left", "right", "top", "bottom", "custom"],
        },
        "auto_cutout": {"type": "boolean"},
        "shadow": {"type": "boolean"},
        "shadow_color": {"type": "string", "pattern": "^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
        "shadow_blur": {"type": "number", "minimum": 0, "maximum": 200},
        "shadow_offset_x": {"type": "number", "minimum": -200, "maximum": 200},
        "shadow_offset_y": {"type": "number", "minimum": -200, "maximum": 200},
        "max_width_percent": {"type": "number", "minimum": 1, "maximum": 100},
        "max_height_percent": {"type": "number", "minimum": 1, "maximum": 100},
    },
}

_TEXT_CONFIG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["content", "font_family", "color"],
    "properties": {
        "content": {"type": "string", "maxLength": 4000},
        "font_family": {"type": "string", "maxLength": 200},
        "font_size": {"type": "number", "minimum": 4, "maximum": 400},
        "color": {"type": "string", "pattern": "^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
        "background_color": {"type": "string", "pattern": "^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
        "padding": {"type": "number", "minimum": 0, "maximum": 200},
        "border_radius": {"type": "number", "minimum": 0, "maximum": 200},
        "text_align": {"type": "string", "enum": ["left", "center", "right"]},
        "text_transform": {"type": "string", "enum": ["none", "uppercase", "lowercase", "capitalize"]},
        "letter_spacing": {"type": "number", "minimum": -10, "maximum": 50},
        "line_height": {"type": "number", "minimum": 0.5, "maximum": 5},
        "font_weight": {"type": "string", "enum": ["normal", "bold", "light"]},
        "text_shadow": {
            "type": "object",
            "additionalProperties": False,
            "required": ["color", "blur", "offset_x", "offset_y"],
            "properties": {
                "color": {"type": "string", "pattern": "^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
                "blur": {"type": "number", "minimum": 0, "maximum": 200},
                "offset_x": {"type": "number", "minimum": -200, "maximum": 200},
                "offset_y": {"type": "number", "minimum": -200, "maximum": 200},
            },
        },
    },
}

_IMAGE_CONFIG = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "src": {"type": "string", "maxLength": 4096},
        "object_fit": {"type": "string", "enum": ["cover", "contain", "fill"]},
        "border_radius": {"type": "number", "minimum": 0, "maximum": 200},
        "border_width": {"type": "number", "minimum": 0, "maximum": 200},
        "border_color": {"type": "string", "pattern": "^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
    },
}

_SHAPE_CONFIG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["shape_type"],
    "properties": {
        "shape_type": {"type": "string", "enum": ["rectangle", "circle", "line"]},
        "fill_color": {"type": "string", "pattern": "^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
        "stroke_color": {"type": "string", "pattern": "^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
        "stroke_width": {"type": "number", "minimum": 0, "maximum": 200},
    },
}

_VIDEO_CONFIG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["prompt", "model", "duration", "loop"],
    "properties": {
        "prompt": {"type": "string", "minLength": 1, "maxLength": 4000},
        "model": {"type": "string", "enum": ["fal_video", "minimax_h3", "comfyui"]},
        "duration": {"type": "number", "minimum": 1, "maximum": 120},
        "loop": {"type": "boolean"},
    },
}


_LAYER_SCHEMAS = {
    "ai_background": _BACKGROUND_CONFIG,
    "ai_image": _BACKGROUND_CONFIG,
    "product_cutout": _PRODUCT_CONFIG,
    "text": _TEXT_CONFIG,
    "image": _IMAGE_CONFIG,
    "shape": _SHAPE_CONFIG,
    "video_background": _VIDEO_CONFIG,
}


_LAYER_BASE = {
    "type": "object",
    "required": ["id", "type", "name"],
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string", "minLength": 1, "maxLength": 64},
        "type": {"type": "string", "enum": list(LAYER_TYPES)},
        "name": {"type": "string", "maxLength": 200},
        "visible": {"type": "boolean"},
        "locked": {"type": "boolean"},
        "blend_mode": {
            "type": "string",
            "enum": ["normal", "multiply", "screen", "overlay", "soft_light"],
        },
        "opacity": {"type": "number", "minimum": 0, "maximum": 1},
        "x": {"type": "number", "minimum": 0, "maximum": 100},
        "y": {"type": "number", "minimum": 0, "maximum": 100},
        "width": {"type": "number", "minimum": 0, "maximum": 100},
        "height": {"type": "number", "minimum": 0, "maximum": 100},
        "rotation": {"type": "number", "minimum": -360, "maximum": 360},
        "config": {"type": "object"},
    },
}


TEMPLATE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["name", "aspect_ratio", "canvas", "layers"],
    "additionalProperties": False,
    "properties": {
        "id": {"type": ["string", "integer"]},
        "name": {"type": "string", "minLength": 1, "maxLength": 200},
        "category": {"type": "string", "enum": list(SUPPORTED_TEMPLATE_CATEGORIES)},
        "aspect_ratio": {"type": "string", "enum": list(ASPECT_RATIOS)},
        "canvas": {
            "type": "object",
            "required": ["width", "height"],
            "additionalProperties": False,
            "properties": {
                "width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "height": {"type": "integer", "minimum": 64, "maximum": 8192},
            },
        },
        "safe_zones": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "top": {"type": "number", "minimum": 0, "maximum": 100},
                "bottom": {"type": "number", "minimum": 0, "maximum": 100},
                "left": {"type": "number", "minimum": 0, "maximum": 100},
                "right": {"type": "number", "minimum": 0, "maximum": 100},
            },
        },
        "layers": {
            "type": "array",
            "items": _LAYER_BASE,
            "maxItems": 64,
        },
        "brand_locks": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 64},
        },
        "default_filter": {"type": "string", "maxLength": 64},
        "ai_prompt_template": {"type": "string", "maxLength": 4000},
    },
}


class TemplateError(ValueError):
    """Raised when a template fails shape validation OR brand-coherence checks."""


# ---- public validators ----


def _format_errors(errors: list[dict]) -> str:
    """Compact jsonschema error list."""
    parts = []
    for err in errors:
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        parts.append(f"{path}: {err.message}")
    return "; ".join(parts)


def validate_template(t: Any) -> dict:
    """Strict-validate a template dict. Returns the (possibly coerced) template.

    Raises TemplateError listing every schema violation found.
    """
    if not isinstance(t, dict):
        raise TemplateError("template must be a JSON object")
    validator = Draft202012Validator(
        TEMPLATE_SCHEMA, format_checker=FormatChecker()
    )
    errors = sorted(validator.iter_errors(t), key=lambda e: list(e.absolute_path))
    if errors:
        raise TemplateError(_format_errors(errors))

    # Per-layer-type config checks (jsonschema handles shape; we narrow to type).
    type_errs: list[str] = []
    layer_ids: set[str] = set()
    for idx, layer in enumerate(t.get("layers") or []):
        lid = layer.get("id")
        if lid in layer_ids:
            type_errs.append(f"layers[{idx}].id: duplicate id {lid!r}")
        layer_ids.add(lid)
        ltype = layer.get("type")
        schema = _LAYER_SCHEMAS.get(ltype)
        if schema is None:
            type_errs.append(f"layers[{idx}].type: unknown layer type {ltype!r}")
            continue
        cfg = layer.get("config") or {}
        if not isinstance(cfg, dict):
            type_errs.append(f"layers[{idx}].config: must be an object")
            continue
        sub_v = Draft202012Validator(schema, format_checker=FormatChecker())
        for err in sorted(sub_v.iter_errors(cfg), key=lambda e: list(e.absolute_path)):
            type_errs.append(f"layers[{idx}].config" + (
                "/" + "/".join(str(p) for p in err.absolute_path)
                if err.absolute_path else ""
            ) + f": {err.message}")

    # brand_locks must reference valid layer ids.
    brand_locks = set(t.get("brand_locks") or [])
    unknown_locks = brand_locks - {l.get("id") for l in (t.get("layers") or [])}
    for unknown in sorted(unknown_locks):
        type_errs.append(f"brand_locks: unknown layer id {unknown!r}")

    # aspect_ratio should match canvas.
    a = t.get("aspect_ratio")
    cw = (t.get("canvas") or {}).get("width")
    ch = (t.get("canvas") or {}).get("height")
    if a and cw and ch:
        expected = {"1:1": 1.0, "4:5": 0.8, "9:16": 0.5625, "16:9": 1.7777777}.get(a)
        if expected is not None:
            actual = cw / ch
            if abs(actual - expected) > 0.05:
                type_errs.append(
                    f"aspect_ratio {a!r} does not match canvas {cw}x{ch} "
                    f"(ratio {actual:.4f}, expected {expected:.4f})"
                )

    if type_errs:
        raise TemplateError("; ".join(type_errs))
    return t


def coerce_template(t: Any) -> dict:
    """Light coercion: fill missing optionals with defaults; drop `None` on
    fields that the schema rejects (e.g. `category`, `default_filter`).

    Does NOT validate — call `validate_template` afterwards.

    Video-template fields (`scenes`, `transitions`, `format`, etc.) are only
    stripped when the template is an image template (no `scenes`). Video
    templates keep those fields so callers can still see them.
    """
    if not isinstance(t, dict):
        raise TemplateError("template must be a JSON object")
    out = dict(t)
    out.setdefault("layers", [])
    out.setdefault("brand_locks", [])
    out.setdefault("aspect_ratio", "4:5")
    out.setdefault("canvas", {"width": 1080, "height": 1350})
    # Row-only fields the image schema doesn't accept. If the template is a
    # video template we keep `scenes`/`transitions` etc. so the caller can
    # still persist them via the dedicated columns.
    image_only_drop = ("canvas_w", "canvas_h")
    video_only_drop: tuple[str, ...] = ("audio_track", "duration_s", "fps", "format")
    for k in image_only_drop:
        out.pop(k, None)
    if not out.get("scenes"):
        # Image template — strip everything else video-specific too.
        for k in video_only_drop + ("scenes", "transitions"):
            out.pop(k, None)
    # Drop None fields that would fail enum/type validation.
    for k in ("category", "default_filter", "ai_prompt_template"):
        if out.get(k) is None:
            out.pop(k, None)
    for layer in out["layers"]:
        if isinstance(layer, dict):
            layer.setdefault("visible", True)
            layer.setdefault("locked", False)
    return out
