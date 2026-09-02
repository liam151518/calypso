"""app/compositor.py. PIL-based image compositor for the brand-poster surface.

Renders a Template + Product + Brand DNA into a single PNG/JPEG and writes an
`outputs` row. `ai_background` and `ai_image` layers go through the existing
`app.image_jobs` machinery (fal.ai), with a `outputs/cache/` content-hash cache
so identical prompts+models+seeds return instantly. Other layer types are
composed locally with PIL:

    - product_cutout: app.products.get_cutout (rembg)
    - text:          PIL.ImageDraw with bundled fonts
    - image:         paste at percent-based bounding box
    - shape:         rectangle / circle / line drawn into the layer
    - video_background: ignored here (Phase D handles video)

After all layers are composed we apply the filter via app.filters, optionally
substitute a brand-supplied watermark, and export.

Public surface:
    RenderResult(output_id, file_path, cost_usd, cached_background, elapsed_seconds)
    render(template_id, product_id=None, layer_overrides=None,
           filter_name=None, aspect_ratio=None, intensity=1.0) -> RenderResult
    render_batch(preset_id, product_ids) -> list[RenderResult]
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps

from app import db as app_db
from app import filters as filters_mod
from app import products as products_mod
from app import templates as templates_mod


PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = PROJECT_ROOT / "outputs" / "images"
CACHE_DIR = PROJECT_ROOT / "outputs" / "cache"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class RenderResult:
    output_id: int
    file_path: str
    cost_usd: float
    cached_background: bool = False
    elapsed_seconds: float = 0.0


# ---- helpers ----

def _hash_prompt(prompt: str, model: str, seed: int | None = None) -> str:
    h = hashlib.sha1()
    h.update(model.encode())
    h.update(b"\x00")
    h.update(prompt.encode())
    h.update(b"\x00")
    h.update(str(seed or 0).encode())
    return h.hexdigest()[:16]


def _load_font(role: str, size: int, brand: dict | None) -> ImageFont.ImageFont:
    """Resolve a font by role (brand fonts, else bundled fallback).

    Brand-supplied fonts live under `brand/fonts/`. The bundled OFL fallback is
    `Inter` for everything except `mono` which falls back to `JetBrains Mono`.
    """
    font_dir = PROJECT_ROOT / "app" / "static" / "fonts"
    role_to_fallback = {
        "headline": "inter-600.ttf",
        "body": "inter-400.ttf",
        "price": "jetbrains-mono-500.ttf",
        "caption": "inter-500.ttf",
        "mono": "jetbrains-mono-400.ttf",
    }
    family = (brand or {}).get("fonts", {}).get(role) if brand else None
    candidates: list[Path] = []
    if family:
        candidates.append(PROJECT_ROOT / "brand" / "fonts" / family)
    candidates.append(font_dir / role_to_fallback.get(role, "inter-400.ttf"))
    for c in candidates:
        if c.exists():
            try:
                return ImageFont.truetype(str(c), size=int(size))
            except OSError:
                continue
    return ImageFont.load_default()


def _resolve_color(c: Any, default: str = "#ffffff") -> str:
    """Accept `#abc`, `#aabbcc`, `rgb(r,g,b)`, or a brand palette slot."""
    if not c:
        return default
    s = str(c).strip()
    try:
        rgb = ImageColor.getrgb(s)
        return "#%02x%02x%02x" % rgb
    except ValueError:
        return default


def _percent_box(canvas_w: int, canvas_h: int, layer: dict) -> tuple[int, int, int, int]:
    """Convert percent-based x/y/w/h into absolute pixel box."""
    x = int(round(layer.get("x", 0) / 100.0 * canvas_w))
    y = int(round(layer.get("y", 0) / 100.0 * canvas_h))
    w = int(round(layer.get("width", 100) / 100.0 * canvas_w))
    h = int(round(layer.get("height", 100) / 100.0 * canvas_h))
    return x, y, w, h


def _render_ai_background(
    layer: dict, canvas: Image.Image, *, cache_hit_only: bool = False,
) -> tuple[Image.Image, float, bool]:
    """Render an ai_background/ai_image layer. Uses a content-hash cache and
    falls back to a neutral fill if no API key is configured (so tests don't
    blow up)."""
    cfg = layer.get("config") or {}
    prompt = cfg.get("prompt") or ""
    model = cfg.get("model") or "flux-pro/v1.1"
    seed = cfg.get("seed")
    cache_key = _hash_prompt(prompt, model, seed)
    cache_path = CACHE_DIR / f"{cache_key}.png"
    if cache_path.exists():
        try:
            bg = Image.open(cache_path).convert("RGB")
            return bg.resize(canvas.size, Image.LANCZOS), 0.0, True
        except OSError:
            pass
    if cache_hit_only:
        # Caller asked us not to generate; render a neutral fill instead.
        return Image.new("RGB", canvas.size, "#1e1e1e"), 0.0, False

    cost = 0.0
    img: Image.Image | None = None
    try:
        from app import image_jobs
        job = image_jobs.create_image_job(
            prompt=prompt,
            model=model,
            aspect_ratio=f"{canvas.size[0]}:{canvas.size[1]}",
            num_images=1,
        )
        image_jobs.run_image_job(job)
        if job.output_paths:
            img = Image.open(job.output_paths[0]).convert("RGB")
        # Estimate cost from the job's tracker.
        cost = float(job.cost_usd or 0.0)
    except Exception:  # noqa: BLE001
        img = None

    if img is None:
        # Fallback fill (deterministic for tests).
        img = Image.new("RGB", canvas.size, _neutral_fill(prompt))

    img = img.resize(canvas.size, Image.LANCZOS)
    img.save(cache_path, "PNG")
    return img, cost, False


def _neutral_fill(prompt: str) -> str:
    """Hash the prompt to a hex so the fallback fill is reproducible per prompt."""
    h = hashlib.md5(prompt.encode()).hexdigest()
    return f"#{h[:6]}"


def _render_text(layer: dict, canvas: Image.Image, brand: dict | None) -> Image.Image:
    cfg = layer.get("config") or {}
    content = cfg.get("content") or ""
    color = _resolve_color(cfg.get("color"), "#ffffff")
    font_size = int(cfg.get("font_size") or 32)
    role = layer.get("id") or "body"
    if role in ("headline", "title"):
        role = "headline"
    elif role == "price":
        role = "price"
    font = _load_font(role, font_size, brand)
    text = str(content)
    if cfg.get("text_transform") == "uppercase":
        text = text.upper()
    elif cfg.get("text_transform") == "lowercase":
        text = text.lower()
    elif cfg.get("text_transform") == "capitalize":
        text = text.title()

    # Measure so we can honour alignment and optional bg pill.
    tmp = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    bbox = d.textbbox((0, 0), text, font=font, anchor="lt")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(cfg.get("padding") or 0)
    line_height = float(cfg.get("line_height") or 1.2)
    bg_color = cfg.get("background_color")
    box_w = max(tw + pad * 2, 1)
    box_h = int(max(th, 1) * line_height + pad * 2)
    box = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(box)
    if bg_color:
        try:
            draw.rounded_rectangle(
                [(0, 0), (box_w - 1, box_h - 1)],
                radius=int(cfg.get("border_radius") or 0),
                fill=_resolve_color(bg_color),
            )
        except AttributeError:
            draw.rectangle([(0, 0), (box_w - 1, box_h - 1)], fill=_resolve_color(bg_color))
    align = cfg.get("text_align") or "left"
    x_text = pad if align == "left" else (box_w - tw - pad if align == "right" else (box_w - tw) // 2)
    y_text = pad
    text_color = _resolve_color(color)
    if cfg.get("text_shadow"):
        ts = cfg["text_shadow"]
        shadow_color = _resolve_color(ts.get("color", "#000000"))
        sx = int(ts.get("offset_x", 0))
        sy = int(ts.get("offset_y", 0))
        blur = int(ts.get("blur", 0))
        if blur > 0:
            sh = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sh)
            sd.text((x_text + sx, y_text + sy), text, font=font, fill=shadow_color)
            sh = sh.filter(Image.GaussianBlur(radius=blur / 2.0))
            box = Image.alpha_composite(box, sh)
            draw = ImageDraw.Draw(box)
        else:
            draw.text((x_text + sx, y_text + sy), text, font=font, fill=shadow_color)
    draw.text((x_text, y_text), text, font=font, fill=text_color)
    return box


def _render_image(layer: dict, canvas: Image.Image, brand: dict | None) -> Image.Image | None:
    cfg = layer.get("config") or {}
    src = cfg.get("src") or ""
    # Resolve {{brand.logo}} placeholder if present.
    if "{{" in src:
        rendered = templates_mod.render_substitutions(src, brand=brand, product={})
        src = rendered or src
    if not src:
        return None
    p = Path(src)
    if not p.exists():
        p = PROJECT_ROOT / src
    if not p.exists():
        return None
    img = Image.open(p).convert("RGBA")
    fit = cfg.get("object_fit") or "contain"
    # Contain/cover/crop into the percent box.
    box_w, box_h = _box_dims(canvas, layer)
    if fit == "cover":
        img = ImageOps.cover(img, (box_w, box_h))
    elif fit == "contain":
        img.thumbnail((box_w, box_h))
        canvas2 = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        canvas2.paste(img, ((box_w - img.size[0]) // 2, (box_h - img.size[1]) // 2), img)
        img = canvas2
    else:
        img = img.resize((box_w, box_h))
    # Optional rounded corners.
    if cfg.get("border_radius"):
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [(0, 0), img.size], radius=int(cfg["border_radius"]), fill=255
        )
        img.putalpha(mask)
    # Optional border.
    if cfg.get("border_width"):
        d = ImageDraw.Draw(img)
        d.rectangle(
            [(0, 0), (img.size[0] - 1, img.size[1] - 1)],
            outline=_resolve_color(cfg.get("border_color"), "#ffffff"),
            width=int(cfg["border_width"]),
        )
    return img


def _render_shape(layer: dict, canvas: Image.Image) -> Image.Image:
    cfg = layer.get("config") or {}
    shape_type = cfg.get("shape_type") or "rectangle"
    box_w, box_h = _box_dims(canvas, layer)
    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill = _resolve_color(cfg.get("fill_color"), "#ffffff")
    stroke = _resolve_color(cfg.get("stroke_color"), "#000000") if cfg.get("stroke_color") else None
    stroke_w = int(cfg.get("stroke_width") or 0)
    if shape_type == "rectangle":
        d.rectangle([(0, 0), (box_w - 1, box_h - 1)], fill=fill, outline=stroke, width=stroke_w)
    elif shape_type == "circle":
        d.ellipse([(0, 0), (box_w - 1, box_h - 1)], fill=fill, outline=stroke, width=stroke_w)
    elif shape_type == "line":
        d.line([(0, box_h // 2), (box_w - 1, box_h // 2)], fill=fill or stroke or "#ffffff", width=max(stroke_w, 1))
    return img


def _box_dims(canvas: Image.Image, layer: dict) -> tuple[int, int]:
    _, _, bw, bh = _percent_box(canvas.size[0], canvas.size[1], layer)
    return bw, bh


def _render_product_cutout(layer: dict, canvas: Image.Image, product: dict) -> Image.Image | None:
    cfg = layer.get("config") or {}
    pid = product.get("id")
    if pid is None:
        return None
    cutout_path = products_mod.get_cutout(int(pid))
    if not cutout_path:
        return None
    img = Image.open(cutout_path).convert("RGBA")
    # Resize to max_width_percent / max_height_percent of canvas.
    cw, ch = canvas.size
    max_w_pct = float(cfg.get("max_width_percent") or 60.0)
    max_h_pct = float(cfg.get("max_height_percent") or 60.0)
    max_w = int(cw * max_w_pct / 100.0)
    max_h = int(ch * max_h_pct / 100.0)
    iw, ih = img.size
    if iw > max_w or ih > max_h:
        ratio = min(max_w / iw, max_h / ih)
        img = img.resize((max(1, int(iw * ratio)), max(1, int(ih * ratio))), Image.LANCZOS)
    # Optional drop shadow rendered as a separate alpha layer.
    if cfg.get("shadow"):
        blur = int(cfg.get("shadow_blur") or 16)
        ox = int(cfg.get("shadow_offset_x") or 0)
        oy = int(cfg.get("shadow_offset_y") or 0)
        shadow_color = _resolve_color(cfg.get("shadow_color"), "#000000")
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sa = shadow.load()
        r, g, b = ImageColor.getrgb(shadow_color)
        sa_alpha = 120
        for y in range(img.size[1]):
            for x in range(img.size[0]):
                if img.getpixel((x, y))[3] > 0:
                    sa[x, y] = (r, g, b, sa_alpha)
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1, blur / 2.0)))
        # Pad to fit shadow + offset.
        pad = blur + max(abs(ox), abs(oy))
        padded = Image.new("RGBA", (img.size[0] + 2 * pad, img.size[1] + 2 * pad), (0, 0, 0, 0))
        padded.paste(shadow, (pad + ox, pad + oy), shadow)
        padded.paste(img, (pad, pad), img)
        img = padded
        # Subtract the padding offset later when positioning.
        layer = {**layer, "_pad": pad}
    return img


def _position_layer(canvas: Image.Image, layer: dict, rendered: Image.Image) -> None:
    x, y, bw, bh = _percent_box(canvas.size[0], canvas.size[1], layer)
    pad = layer.get("_pad") or 0
    iw, ih = rendered.size
    # Honour align: the spec keeps alignment implicit in x/y/w/h.
    # For product_cutout with shadow, the rendered image is `bw + 2*pad` wide.
    # We want the original product to land at (x, y) with size (bw, bh), so the
    # shadow extends outward. The shadow-padded image should be centred on the
    # (x..x+bw, y..y+bh) box minus the pad.
    # Use rendered.size to centre:
    px = x - pad + (bw - iw) // 2 if pad else x + (bw - iw) // 2
    py = y - pad + (bh - ih) // 2 if pad else y + (bh - ih) // 2
    if rendered.mode == "RGBA":
        canvas.alpha_composite(rendered, (px, py))
    else:
        canvas.paste(rendered, (px, py))


# ---- public API ----

def render(
    template_id: int,
    *,
    product_id: int | None = None,
    layer_overrides: dict | None = None,
    filter_name: str | None = None,
    aspect_ratio: str | None = None,
    intensity: float = 1.0,
    brand_id: int | None = None,
    cache_hit_only: bool = False,
    template_override: dict | None = None,
    job_id: str | None = None,
) -> RenderResult:
    """Compose a single image. Returns the RenderResult and writes an outputs row."""
    started = time.monotonic()
    template = template_override or templates_mod.get_template(template_id)
    if template is None:
        raise ValueError(f"no template with id={template_id}")
    product = products_mod.get_product(int(product_id)) if product_id else None
    brand = _resolve_brand(brand_id or (product or {}).get("brand_id"))
    # Phase G.6 — surface render progress via the in-process event queue.
    if job_id:
        try:
            from app import events as events_mod
            events_mod.enqueue(job_id, "started")
        except Exception:  # noqa: BLE001
            pass
    t_substituted = templates_mod.substitute_template(
        template, product=product or {}, brand=brand or {}
    )
    if aspect_ratio and aspect_ratio != t_substituted.get("aspect_ratio"):
        # Resize canvas to the requested aspect ratio.
        cw = t_substituted.get("canvas_w") or t_substituted.get("canvas", {}).get("width", 1080)
        ch = t_substituted.get("canvas_h") or t_substituted.get("canvas", {}).get("height", 1350)
        if aspect_ratio == "1:1":
            ch = cw
        elif aspect_ratio == "4:5":
            ch = int(cw / 0.8)
        elif aspect_ratio == "9:16":
            ch = int(cw / 0.5625)
        elif aspect_ratio == "16:9":
            ch = int(cw / 1.7777777)
        t_substituted["canvas"] = {"width": cw, "height": ch}
        t_substituted["canvas_w"] = cw
        t_substituted["canvas_h"] = ch
        t_substituted["aspect_ratio"] = aspect_ratio

    cw = t_substituted.get("canvas_w") or t_substituted.get("canvas", {}).get("width", 1080)
    ch = t_substituted.get("canvas_h") or t_substituted.get("canvas", {}).get("height", 1350)
    canvas = Image.new("RGBA", (cw, ch), (245, 240, 232, 255))
    total_cost = 0.0
    bg_cached = False

    # Layer pass — we honour the original ordering and skip brand-locked layers
    # only if the brand isn't known (locked layers are still rendered; they
    # just can't be edited by users).
    for layer in t_substituted.get("layers") or []:
        if not layer.get("visible", True):
            continue
        ltype = layer.get("type")
        if ltype in ("ai_background", "ai_image"):
            bg, cost, cached = _render_ai_background(layer, canvas, cache_hit_only=cache_hit_only)
            total_cost += cost
            bg_cached = bg_cached or cached
            canvas.alpha_composite(bg.convert("RGBA"))
        elif ltype == "product_cutout":
            if product is None:
                continue
            r = _render_product_cutout(layer, canvas, product)
            if r is not None:
                _position_layer(canvas, layer, r)
        elif ltype == "text":
            r = _render_text(layer, canvas, brand)
            _position_layer(canvas, layer, r)
        elif ltype == "image":
            r = _render_image(layer, canvas, brand)
            if r is not None:
                _position_layer(canvas, layer, r)
        elif ltype == "shape":
            r = _render_shape(layer, canvas)
            _position_layer(canvas, layer, r)
        elif ltype == "video_background":
            # Phase D handles this; treat as a neutral fill for static export.
            neutral = Image.new("RGBA", canvas.size, (16, 16, 20, 255))
            canvas = Image.alpha_composite(canvas, neutral)
        else:
            continue

    # Optional brand watermark (always overlaid if brand.watermark_path exists).
    if brand and brand.get("watermark_path"):
        try:
            wm = Image.open(PROJECT_ROOT / brand["watermark_path"]).convert("RGBA")
            w, h = canvas.size
            wm.thumbnail((w // 6, h // 6))
            canvas.alpha_composite(
                wm, (w - wm.size[0] - 24, h - wm.size[1] - 24), wm,
            )
        except OSError:
            pass

    # Apply filter if requested.
    settings = _resolve_filter_settings(filter_name, template)
    if settings:
        rgb = canvas.convert("RGB")
        out = filters_mod.apply(rgb, settings, intensity=intensity)
        canvas = out.image.convert("RGBA")
        if job_id:
            try:
                from app import events as events_mod
                events_mod.enqueue(job_id, "filter_applied")
            except Exception:  # noqa: BLE001
                pass

    # Emit per-layer events for the SSE stream.
    if job_id:
        try:
            from app import events as events_mod
            events_mod.enqueue(job_id, "layers_composed")
        except Exception:  # noqa: BLE001
            pass

    # Export to outputs/images/{output_id}.jpg
    output_id = _next_output_id()
    dest = IMAGES_DIR / f"{output_id}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(dest, "JPEG", quality=95)

    # Insert outputs row.
    now = time.time()
    conn = app_db.get_conn()
    layers_json = json.dumps(t_substituted.get("layers") or [])
    filter_settings = json.dumps({
        "filter_name": filter_name,
        "intensity": intensity,
    })
    conn.execute(
        """
        INSERT INTO outputs(
            brand_id, product_id, template_id, type, file_path,
            aspect_ratio, file_size_bytes, filter_applied, status,
            cost_usd, created_at,
            layers_json, filter_settings
        ) VALUES (
            ?, ?, ?, 'image', ?, ?, ?, ?, 'draft', ?, ?,
            ?, ?
        )
        """,
        (
            brand_id or (product or {}).get("brand_id"),
            product_id,
            template_id,
            str(dest),
            t_substituted.get("aspect_ratio"),
            dest.stat().st_size,
            filter_name,
            total_cost,
            now,
            layers_json,
            filter_settings,
        ),
    )
    elapsed = round(time.monotonic() - started, 3)
    if job_id:
        try:
            from app import events as events_mod
            events_mod.enqueue(job_id, "exported", {"output_id": output_id})
        except Exception:  # noqa: BLE001
            pass
    return RenderResult(
        output_id=output_id,
        file_path=str(dest),
        cost_usd=total_cost,
        cached_background=bg_cached,
        elapsed_seconds=elapsed,
    )


def render_batch(
    *,
    template_id: int,
    product_ids: list[int],
    layer_overrides: dict | None = None,
    filter_name: str | None = None,
    intensity: float = 1.0,
    max_workers: int = 4,
    cache_hit_only: bool = False,
) -> list[RenderResult]:
    """Render a template against multiple products in parallel."""
    if max_workers <= 1:
        return [
            render(
                template_id,
                product_id=pid,
                layer_overrides=layer_overrides,
                filter_name=filter_name,
                intensity=intensity,
                cache_hit_only=cache_hit_only,
            )
            for pid in product_ids
        ]
    out: list[RenderResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(
                render,
                template_id,
                product_id=pid,
                layer_overrides=layer_overrides,
                filter_name=filter_name,
                intensity=intensity,
                cache_hit_only=cache_hit_only,
            ): pid
            for pid in product_ids
        }
        for fut in concurrent.futures.as_completed(futures):
            try:
                out.append(fut.result())
            except Exception:  # noqa: BLE001
                continue
    return out


# ---- internal helpers ----

def _resolve_brand(brand_id: int | None) -> dict | None:
    if brand_id is None:
        return None
    from app import brand as brand_mod
    return brand_mod.get_brand(brand_id)


def _resolve_filter_settings(filter_name: str | None, template: dict) -> dict | None:
    name = filter_name or template.get("default_filter")
    if not name:
        return None
    if name in filters_mod.PRESETS:
        return filters_mod.PRESETS[name]
    return None


def _next_output_id() -> int:
    conn = app_db.get_conn()
    row = conn.execute("SELECT IFNULL(MAX(id), 0) AS m FROM outputs").fetchone()
    return int(row["m"]) + 1


__all__ = [
    "render",
    "render_batch",
    "RenderResult",
    "IMAGES_DIR",
    "CACHE_DIR",
]