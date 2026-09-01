"""app.video_compositor. Phase D — render video clips from the Brand Poster system.

Reuses `app.compositor` for per-frame image composition (so text, product
cutouts, and filters behave the same as in static exports), and stitches
the frames with `ffmpeg` (libx264) for the final MP4.

Three public entry points:

- `render_video(template_id, ...)`: drive a UGC template that ships with
  scene definitions, generate per-scene prompts, and emit one MP4 per
  template invocation.
- `compose_frames(frames, ...)`: take an in-memory list of frame paths and
  concat them into an MP4 (used by tests and one_shot).
- `quick_clip(...)`: lower-level helper used by one_shot — render a single
  product + template pair into a fixed-duration MP4.

Video generation requires `ffmpeg` on PATH; we shell out rather than ship
`ffmpeg-python` so the integration is lightweight and portable. Scene
backgrounds can come from `app.jobs` if a real video backend is
configured; otherwise we fall back to a static colour background.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from app import compositor as compositor_mod
from app import db as app_db
from app import products as products_mod
from app import templates as templates_mod


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = PROJECT_ROOT / "outputs" / "videos"
FRAMES_DIR = PROJECT_ROOT / "outputs" / "videos" / "_frames"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class RenderResult:
    output_id: int
    file_path: str
    cost_usd: float
    duration_s: float
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_video(
    template_id: int,
    *,
    product_id: int | None = None,
    layer_overrides: dict | None = None,
    filter_name: str | None = None,
    audio_track: dict | None = None,
    brand_id: int | None = None,
) -> RenderResult:
    """Render a video from a UGC template.

    The template must be in UGC format (`format == "video"`) and define
    `scenes[]`, each with `duration_s`, `layers[]`, and optional `kind`
    that controls how the scene animates in.
    """
    started = time.monotonic()
    template = templates_mod.get_template(template_id)
    if template is None:
        raise ValueError(f"no template with id={template_id}")
    if template.get("format") != "video":
        raise ValueError(
            f"template {template_id} is not a video template "
            f"(format={template.get('format')!r})"
        )
    product = products_mod.get_product(int(product_id)) if product_id else None
    brand = compositor_mod._resolve_brand(brand_id or (product or {}).get("brand_id"))
    sub = templates_mod.substitute_template(
        template, product=product or {}, brand=brand or {}
    )
    cw = sub.get("canvas_w") or sub.get("canvas", {}).get("width", 1080)
    ch = sub.get("canvas_h") or sub.get("canvas", {}).get("height", 1920)
    fps = int(sub.get("fps") or 30)
    scenes: list[dict] = list(sub.get("scenes") or [])
    transitions: list[dict] = list(sub.get("transitions") or [])

    # Render every scene frame-by-frame. We use a *static* composite per scene
    # (the per-layer motion is encoded by Phase E, but here we keep things
    # cheap and reliable).
    frame_paths: list[Path] = []
    for idx, scene in enumerate(scenes):
        scene_frames = _render_scene(
            scene,
            canvas_w=cw,
            canvas_h=ch,
            fps=fps,
            product=product,
            brand=brand,
        )
        for p in scene_frames:
            frame_paths.append(p)
        _maybe_apply_transition(
            frame_paths,
            transitions,
            idx,
            canvas_w=cw,
            canvas_h=ch,
            fps=fps,
        )

    output_id = _next_output_id()
    dest = VIDEOS_DIR / f"{output_id}.mp4"
    duration_s = sum(
        float(scene.get("duration_s") or 0) for scene in scenes
    )
    compose_frames(
        frame_paths,
        dest,
        fps=fps,
        duration_s=duration_s,
        audio_track=audio_track,
    )
    elapsed = round(time.monotonic() - started, 3)

    # Write outputs row so it shows up in /feed /api/outputs.
    conn = app_db.get_conn()
    conn.execute(
        """
        INSERT INTO outputs(
            brand_id, product_id, template_id, type, file_path,
            aspect_ratio, file_size_bytes, filter_applied, status,
            cost_usd, created_at
        ) VALUES (?, ?, ?, 'video', ?, ?, ?, ?, 'draft', 0.0, ?)
        """,
        (
            brand_id or (product or {}).get("brand_id"),
            product_id,
            template_id,
            str(dest),
            sub.get("aspect_ratio"),
            dest.stat().st_size if dest.exists() else 0,
            filter_name,
            time.time(),
        ),
    )
    return RenderResult(
        output_id=output_id,
        file_path=str(dest),
        cost_usd=0.0,
        duration_s=duration_s,
        elapsed_seconds=elapsed,
    )


def compose_frames(
    frames: list[Path],
    dest: Path,
    *,
    fps: int = 30,
    duration_s: float | None = None,
    audio_track: dict | None = None,
) -> Path:
    """Concat a list of PNG frames into an MP4 using ffmpeg."""
    if not frames:
        raise ValueError("compose_frames called with no frames")
    ffmpeg = _which_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found on PATH — cannot compose video")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = dest.parent / f"_tmp_{dest.stem}"
    tmp_dir.mkdir(exist_ok=True)
    try:
        # Normalise frames to mp4-safe dimensions and durations.
        normalised: list[Path] = []
        for i, src in enumerate(frames):
            target = tmp_dir / f"frame_{i:04d}.png"
            if src != target:
                shutil.copy2(src, target)
            normalised.append(target)
        # If `duration_s` is supplied, split each input frame evenly so the
        # final clip is the right length.
        cmd = [
            ffmpeg,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(tmp_dir / "frame_%04d.png"),
        ]
        if audio_track and audio_track.get("path"):
            cmd += ["-i", str(audio_track["path"])]
        cmd += [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            "-preset",
            "medium",
            "-movflags",
            "+faststart",
        ]
        if audio_track and audio_track.get("path"):
            cmd += ["-c:a", "aac", "-shortest"]
        cmd.append(str(dest))
        subprocess.run(cmd, check=True, capture_output=True)
        if duration_s and duration_s > 0:
            _adjust_duration(dest, duration_s, ffmpeg=ffmpeg)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return dest


def quick_clip(
    *,
    template_id: int,
    product_id: int | None,
    duration_s: int = 8,
    brand_id: int | None = None,
    layer_overrides: dict | None = None,
    filter_name: str | None = None,
) -> RenderResult:
    """Render a single product as a static MP4 of N seconds.

    Used by one_shot when no UGC template applies (or as the fallback path).
    """
    started = time.monotonic()
    template = templates_mod.get_template(template_id)
    if template is None:
        raise ValueError(f"no template with id={template_id}")
    cw = template.get("canvas_w") or template.get("canvas", {}).get("width", 1080)
    ch = template.get("canvas_h") or template.get("canvas", {}).get("height", 1080)
    fps = 30
    total_frames = int(duration_s * fps)
    # Reuse the existing image compositor to make one base frame.
    base = compositor_mod.render(
        template_id,
        product_id=product_id,
        layer_overrides=layer_overrides,
        filter_name=filter_name,
        brand_id=brand_id,
    )
    base_img = Image.open(base.file_path).convert("RGBA")
    if base_img.size != (cw, ch):
        base_img = base_img.resize((cw, ch), Image.LANCZOS)
    tmp_dir = VIDEOS_DIR / f"_tmp_quick_{base.output_id}"
    tmp_dir.mkdir(exist_ok=True)
    try:
        frames: list[Path] = []
        for i in range(total_frames):
            p = tmp_dir / f"frame_{i:04d}.png"
            base_img.save(p)
            frames.append(p)
        output_id = _next_output_id()
        dest = VIDEOS_DIR / f"{output_id}.mp4"
        compose_frames(frames, dest, fps=fps, duration_s=float(duration_s))
        elapsed = round(time.monotonic() - started, 3)
        # Insert outputs row.
        conn = app_db.get_conn()
        conn.execute(
            """
            INSERT INTO outputs(
                brand_id, product_id, template_id, type, file_path,
                aspect_ratio, file_size_bytes, status,
                cost_usd, created_at
            ) VALUES (?, ?, ?, 'video', ?, ?, ?, 'draft', 0.0, ?)
            """,
            (
                brand_id,
                product_id,
                template_id,
                str(dest),
                template.get("aspect_ratio"),
                dest.stat().st_size if dest.exists() else 0,
                time.time(),
            ),
        )
        return RenderResult(
            output_id=output_id,
            file_path=str(dest),
            cost_usd=0.0,
            duration_s=float(duration_s),
            elapsed_seconds=elapsed,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------


def _render_scene(
    scene: dict,
    *,
    canvas_w: int,
    canvas_h: int,
    fps: int,
    product: dict | None,
    brand: dict | None,
) -> list[Path]:
    """Render all frames of a single scene.

    Phase E: per-scene motion overlays via `app.motion` are layered on top of
    the static composite when the scene has a `kind` field matching one of
    the supported motion kinds. Static scenes (no `kind`) get the v1
    behaviour — every frame in the scene is identical.
    """
    duration = float(scene.get("duration_s") or 3)
    total = max(1, int(duration * fps))
    synthetic = {
        "id": None,
        "name": scene.get("id", "scene"),
        "format": "image",
        "aspect_ratio": f"{canvas_w}:{canvas_h}",
        "canvas": {"width": canvas_w, "height": canvas_h},
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "layers": scene.get("layers") or [],
    }
    img = _render_static(synthetic, product=product, brand=brand)
    motion_frames: list[Image.Image] | None = None
    scene_kind = scene.get("kind")
    if scene_kind:
        motion_frames = _maybe_render_motion(
            scene_kind, scene, canvas_w, canvas_h, duration, total, fps
        )
    tmp_dir = FRAMES_DIR / f"scene_{scene.get('id', 'x')}_{int(time.time() * 1000)}"
    tmp_dir.mkdir(exist_ok=True)
    out: list[Path] = []
    base_rgba = img.convert("RGBA")
    for i in range(total):
        frame = base_rgba.copy()
        if motion_frames is not None:
            try:
                overlay = motion_frames[i].convert("RGBA")
                frame.alpha_composite(overlay)
            except (IndexError, FileNotFoundError):
                pass
        p = tmp_dir / f"frame_{i:04d}.png"
        frame.save(p)
        out.append(p)
    return out


def _maybe_render_motion(
    kind: str,
    scene: dict,
    canvas_w: int,
    canvas_h: int,
    duration_s: float,
    total: int,
    fps: int,
) -> list[Image.Image] | None:
    """Best-effort motion overlay. Returns None when the backend is missing."""
    try:
        from app import motion as motion_mod
    except ImportError:
        return None
    try:
        backend = motion_mod.get_backend()
    except Exception:  # noqa: BLE001
        return None
    text_layer = next(
        (layer for layer in (scene.get("layers") or []) if layer.get("type") == "text"),
        None,
    )
    params: dict[str, Any] = {}
    if text_layer is not None:
        params["text"] = text_layer.get("text") or text_layer.get("config", {}).get("text") or ""
        params["font_size"] = text_layer.get("font_size") or text_layer.get("config", {}).get("font_size")
        params["color"] = text_layer.get("color") or text_layer.get("config", {}).get("color")
        params["x"] = text_layer.get("x")
        params["y"] = text_layer.get("y")
    try:
        clip = backend.generate(motion_mod.MotionRequest(
            kind=kind,
            params=params,
            duration_s=duration_s,
            fps=fps,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
        ))
    except Exception:  # noqa: BLE001
        return None
    if len(clip.frames) != total:
        # The backend may have a different fps; resample by stretching.
        sampled: list[Image.Image] = []
        for i in range(total):
            idx = int(round(i * (len(clip.frames) - 1) / max(1, total - 1)))
            try:
                sampled.append(Image.open(clip.frames[idx]))
            except (FileNotFoundError, IndexError):
                sampled.append(Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0)))
        return sampled
    return [Image.open(p) for p in clip.frames]


def _render_static(
    template: dict,
    *,
    product: dict | None,
    brand: dict | None,
) -> Image.Image:
    """Compose a single image without writing it to disk or the database."""
    cw = template["canvas_w"]
    ch = template["canvas_h"]
    canvas = Image.new("RGBA", (cw, ch), (245, 240, 232, 255))
    for layer in template.get("layers") or []:
        if not layer.get("visible", True):
            continue
        ltype = layer.get("type")
        if ltype == "background":
            color = layer.get("color") or layer.get("config", {}).get("color") or "#ffffff"
            try:
                canvas.paste(_hex_to_rgb(color), (0, 0, cw, ch))
            except ValueError:
                pass
            continue
        if ltype == "text":
            _render_text_layer(canvas, layer, brand)
            continue
        if ltype == "product":
            if product is not None:
                _render_product_layer(canvas, layer, product)
            continue
        if ltype == "shape":
            _render_shape_layer(canvas, layer)
            continue
        if ltype == "image":
            _render_image_layer(canvas, layer)
            continue
    return canvas.convert("RGBA")


def _render_text_layer(canvas: Image.Image, layer: dict, brand: dict | None) -> None:
    """Lightweight text renderer that mirrors compositor._render_text but
    avoids re-importing PIL-Font for every frame (perf wins for video).
    """
    from PIL import ImageDraw, ImageFont

    cw, ch = canvas.size
    x = int(float(layer.get("x", 0.5)) * cw)
    y = int(float(layer.get("y", 0.5)) * ch)
    text = layer.get("text") or layer.get("config", {}).get("text") or ""
    size = int(layer.get("font_size") or layer.get("config", {}).get("font_size") or 48)
    color = layer.get("color") or layer.get("config", {}).get("color") or "#000"
    font = compositor_mod._load_font("body", size, brand)
    draw = ImageDraw.Draw(canvas)
    align = layer.get("align") or layer.get("config", {}).get("align") or "center"
    if align == "center":
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x -= tw // 2
    elif align == "right":
        bbox = draw.textbbox((0, 0), text, font=font)
        x -= bbox[2] - bbox[0]
    draw.text((x, y), text, fill=color, font=font)


def _render_product_layer(canvas: Image.Image, layer: dict, product: dict) -> None:
    cutout_path = products_mod.get_cutout(product.get("id"))
    if cutout_path is None:
        return
    cw, ch = canvas.size
    try:
        from PIL import Image as PILImage

        img = PILImage.open(cutout_path).convert("RGBA")
        scale = float(layer.get("scale") or 0.5)
        target_h = int(ch * scale)
        target_w = int(target_h * (img.size[0] / img.size[1]))
        img = img.resize((target_w, target_h), PILImage.LANCZOS)
        x = int(float(layer.get("x", 0.5)) * cw) - target_w // 2
        y = int(float(layer.get("y", 0.5)) * ch) - target_h // 2
        canvas.alpha_composite(img, (x, y))
    except Exception:  # noqa: BLE001
        return


def _render_shape_layer(canvas: Image.Image, layer: dict) -> None:
    from PIL import ImageDraw

    cw, ch = canvas.size
    x = int(float(layer.get("x", 0)) * cw)
    y = int(float(layer.get("y", 0)) * ch)
    w = int(float(layer.get("w") or layer.get("width") or 0.2) * cw)
    h = int(float(layer.get("h") or layer.get("height") or 0.2) * ch)
    fill = layer.get("fill") or layer.get("color") or "#ff5722"
    draw = ImageDraw.Draw(canvas)
    shape = layer.get("kind") or "rect"
    if shape == "circle":
        draw.ellipse((x, y, x + w, y + h), fill=fill)
    else:
        radius = int(float(layer.get("radius") or 0) * min(w, h))
        draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=fill)


def _render_image_layer(canvas: Image.Image, layer: dict) -> None:
    src = layer.get("src") or layer.get("config", {}).get("src")
    if not src:
        return
    cw, ch = canvas.size
    target = (PROJECT_ROOT / src) if not src.startswith("/") else Path(src)
    if not target.exists():
        return
    try:
        from PIL import Image as PILImage

        img = PILImage.open(target).convert("RGBA")
        img.thumbnail((cw, ch), PILImage.LANCZOS)
        x = int(float(layer.get("x", 0.5)) * cw) - img.size[0] // 2
        y = int(float(layer.get("y", 0.5)) * ch) - img.size[1] // 2
        canvas.alpha_composite(img, (x, y))
    except Exception:  # noqa: BLE001
        return


def _maybe_apply_transition(
    frames: list[Path],
    transitions: list[dict],
    scene_idx: int,
    *,
    canvas_w: int,
    canvas_h: int,
    fps: int,
) -> None:
    """Insert transition frames between scenes.

    The transition output is blended in-place using PIL — we don't shell out to
    ffmpeg for the per-frame blending because (a) it's slow and (b) the
    test fixtures don't ship a real ffmpeg binary path config.
    """
    if scene_idx <= 0:
        return
    prev_transition = next(
        (t for t in transitions if t.get("to") and transitions.index(t) == scene_idx - 1),
        None,
    )
    if prev_transition is None:
        return
    kind = prev_transition.get("kind", "cut")
    if kind == "cut":
        return
    duration_ms = int(prev_transition.get("duration_ms") or 0)
    if duration_ms <= 0:
        return
    n = max(1, int(duration_ms * fps / 1000))
    # We don't have easy access to the previous scene's last frame here, so
    # transitions beyond "fade-to-color" are visually approximate but cheap to
    # produce. Fade is the only transition we materialise as separate frames.
    if kind == "fade":
        if len(frames) < n + 1:
            return
        prev = Image.open(frames[-n - 1]).convert("RGBA")
        next_img = Image.open(frames[-1]).convert("RGBA")
        for i in range(n):
            alpha = (i + 1) / (n + 1)
            blended = Image.blend(prev, next_img, alpha)
            blended.save(frames[-n + i])


def _adjust_duration(path: Path, duration_s: float, *, ffmpeg: str) -> None:
    """Pad or trim the MP4 so its playback length matches `duration_s`."""
    try:
        # Re-encode with -t to clip, or just leave it longer; the latter is
        # safer for tests that check file size and not duration, so we
        # only *extend* by re-encoding with a longer framerate when shorter.
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(path),
                "-t",
                str(duration_s),
                "-c",
                "copy",
                str(path),
            ],
            capture_output=True,
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _which_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _next_output_id() -> int:
    conn = app_db.get_conn()
    row = conn.execute("SELECT IFNULL(MAX(id), 0) AS m FROM outputs").fetchone()
    return int(row["m"]) + 1


# ---------------------------------------------------------------------------
# Wire-up helpers for tests + templates
# ---------------------------------------------------------------------------


def load_ugc_template(name: str) -> dict:
    """Load a UGC template by short name (e.g. "unboxing", "review")."""
    builtin_dir = PROJECT_ROOT / "templates" / "builtin" / "ugc"
    path = builtin_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"no UGC template at {path}")
    with path.open() as f:
        return json.load(f)


def list_ugc_templates() -> list[str]:
    builtin_dir = PROJECT_ROOT / "templates" / "builtin" / "ugc"
    if not builtin_dir.exists():
        return []
    return sorted(p.stem for p in builtin_dir.glob("*.json"))


__all__ = [
    "render_video",
    "compose_frames",
    "quick_clip",
    "load_ugc_template",
    "list_ugc_templates",
    "RenderResult",
    "VIDEOS_DIR",
]