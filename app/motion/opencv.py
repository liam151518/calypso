"""app.motion.opencv. Phase E.2 — built-in motion graphics via cv2 + numpy.

Implements the `MotionBackend` protocol for every kind the Compositor asks
for. Each `generate(request)` writes a sequence of PNG frames with alpha
to a temp directory and returns the resulting `MotionClip`.

Animation recipes (from the spec §6.3 + plan E.2):

- text_bounce_in:    `easeOutBack` on scale + position
- lower_third_slide: linear interp on y
- slide_up:          linear interp on y (alias for slide; same easing)
- sticker_pop:       `scale = 1 + sin(t·π)·0.3` with overshoot
- pulse:             `scale = 1 + sin(t·2π)·0.1`
- countdown_pulse:   pulse + numeric countdown overlay
- transition_wipe:   horizontal wipe
- fade:              alpha interp

All animations are brand-aware — text overlays pull font/color from
`app.brand.load_font(...)` when available.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.motion import MotionBackend, MotionClip, MotionRequest


@dataclass
class OpenCVMotionBackend:
    """Always-available motion backend. Implements all 5 + extended kinds."""

    name: str = "opencv"
    output_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.output_dir is None:
            from app.motion import __file__ as _mot_init

            self.output_dir = (
                Path(_mot_init).resolve().parent.parent / "outputs" / "motion"
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def available(self) -> bool:
        try:
            import cv2  # noqa: F401
            return True
        except ImportError:
            return False

    # ----------------- main entry point -----------------

    def generate(self, request: MotionRequest) -> MotionClip:
        total_frames = max(1, int(round(request.duration_s * request.fps)))
        frames = self._allocate_frames(request, total_frames)
        # The dispatcher returns a fresh list of frame paths, populated
        # by the per-kind helper.
        kind = request.kind
        params = dict(request.params or {})
        if kind == "text_bounce_in":
            self._bounce_in(frames, request, params)
        elif kind == "lower_third_slide":
            self._slide(frames, request, params, axis="y", from_below=True)
        elif kind == "slide_up":
            self._slide(frames, request, params, axis="y", from_below=True)
        elif kind == "sticker_pop":
            self._pop(frames, request, params)
        elif kind == "pulse":
            self._pulse(frames, request, params)
        elif kind == "countdown_pulse":
            self._countdown_pulse(frames, request, params)
        elif kind == "transition_wipe":
            self._wipe(frames, request, params)
        elif kind == "fade":
            self._fade(frames, request, params)
        else:
            raise ValueError(f"unsupported motion kind: {kind!r}")
        return MotionClip(
            frames=frames,
            duration_s=float(total_frames / request.fps),
            backend=self.name,
            kind=kind,
        )

    # ----------------- helpers -----------------

    def _allocate_frames(self, request: MotionRequest, total: int) -> list[Path]:
        ts = int(time.time() * 1000)
        out: list[Path] = []
        for i in range(total):
            path = self.output_dir / f"{request.kind}_{ts}_{i:04d}.png"
            out.append(path)
        return out

    def _ease_out_back(self, t: float) -> float:
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

    def _ease_in_out(self, t: float) -> float:
        if t < 0.5:
            return 4 * t * t * t
        return 1 - ((-2 * t + 2) ** 3) / 2

    def _load_text_overlay(
        self,
        request: MotionRequest,
        params: dict[str, Any],
    ) -> tuple[Image.Image, int, int]:
        """Return a fully-opaque RGBA text image + width/height."""
        cw, ch = request.canvas_w, request.canvas_h
        text = str(params.get("text") or "")
        size = int(params.get("font_size") or max(36, cw // 18))
        color = params.get("color") or "#ffffff"
        font = self._brand_font(request, size)
        # Measure text size so the caller can position it.
        tmp = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tmp)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((-bbox[0], -bbox[1]), text, fill=color, font=font)
        return layer, tw, th

    def _brand_font(self, request: MotionRequest, size: int) -> ImageFont.ImageFont:
        try:
            from app import brand as brand_mod
            from app import compositor as compositor_mod

            brand_dict = brand_mod.get_active_brand() if hasattr(brand_mod, "get_active_brand") else {}
            return compositor_mod._load_font("headline", size, brand_dict)
        except Exception:  # noqa: BLE001
            return ImageFont.load_default()

    # ----------------- animation recipes -----------------

    def _bounce_in(
        self,
        frames: list[Path],
        request: MotionRequest,
        params: dict[str, Any],
    ) -> None:
        cw, ch = request.canvas_w, request.canvas_h
        layer, tw, th = self._load_text_overlay(request, params)
        cx = int(float(params.get("cx") or 0.5) * cw)
        cy = int(float(params.get("cy") or 0.5) * ch)
        n = len(frames)
        for i, p in enumerate(frames):
            t = (i + 1) / n
            scale = max(0.05, self._ease_out_back(t))
            offset_y = int((1 - scale) * ch * 0.1)
            new_w = max(1, int(tw * scale))
            new_h = max(1, int(th * scale))
            scaled = layer.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            canvas.alpha_composite(scaled, (cx - new_w // 2, cy - new_h // 2 + offset_y))
            canvas.save(p)

    def _slide(
        self,
        frames: list[Path],
        request: MotionRequest,
        params: dict[str, Any],
        *,
        axis: str = "y",
        from_below: bool = True,
    ) -> None:
        cw, ch = request.canvas_w, request.canvas_h
        layer, tw, th = self._load_text_overlay(request, params)
        target_x = int(float(params.get("x") or 0.5) * cw) - tw // 2
        target_y = int(float(params.get("y") or 0.85) * ch) - th // 2
        n = len(frames)
        start_x = -tw if axis == "x" and not from_below else target_x
        start_y = ch if from_below else -th
        if axis == "x":
            start_x = -tw if from_below else cw
            start_y = target_y
        for i, p in enumerate(frames):
            t = (i + 1) / n
            x = int(start_x + (target_x - start_x) * t) if axis == "x" else target_x
            y = int(start_y + (target_y - start_y) * t) if axis == "y" else target_y
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            canvas.alpha_composite(layer, (x, y))
            canvas.save(p)

    def _pop(
        self,
        frames: list[Path],
        request: MotionRequest,
        params: dict[str, Any],
    ) -> None:
        cw, ch = request.canvas_w, request.canvas_h
        layer, tw, th = self._load_text_overlay(request, params)
        cx = int(float(params.get("cx") or 0.5) * cw)
        cy = int(float(params.get("cy") or 0.5) * ch)
        n = len(frames)
        for i, p in enumerate(frames):
            t = (i + 1) / n
            scale = 1 + math.sin(t * math.pi) * 0.3
            new_w = max(1, int(tw * scale))
            new_h = max(1, int(th * scale))
            scaled = layer.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            canvas.alpha_composite(scaled, (cx - new_w // 2, cy - new_h // 2))
            canvas.save(p)

    def _pulse(
        self,
        frames: list[Path],
        request: MotionRequest,
        params: dict[str, Any],
    ) -> None:
        cw, ch = request.canvas_w, request.canvas_h
        layer, tw, th = self._load_text_overlay(request, params)
        cx = int(float(params.get("cx") or 0.5) * cw)
        cy = int(float(params.get("cy") or 0.5) * ch)
        n = max(1, len(frames))
        for i, p in enumerate(frames):
            t = (i + 1) / n
            scale = 1 + math.sin(t * 2 * math.pi) * 0.1
            new_w = max(1, int(tw * scale))
            new_h = max(1, int(th * scale))
            scaled = layer.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            canvas.alpha_composite(scaled, (cx - new_w // 2, cy - new_h // 2))
            canvas.save(p)

    def _countdown_pulse(
        self,
        frames: list[Path],
        request: MotionRequest,
        params: dict[str, Any],
    ) -> None:
        from app.motion.opencv import _numeric_layer

        cw, ch = request.canvas_w, request.canvas_h
        n = len(frames)
        duration = request.duration_s
        for i, p in enumerate(frames):
            t = (i + 1) / n
            remaining = max(0, int(math.ceil(duration - t * duration)))
            scale = 1 + math.sin(t * 2 * math.pi) * 0.12
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            num_layer = _numeric_layer(str(remaining), cw, ch, scale, color=params.get("color", "#ff2e63"))
            canvas.alpha_composite(num_layer)
            canvas.save(p)

    def _wipe(
        self,
        frames: list[Path],
        request: MotionRequest,
        params: dict[str, Any],
    ) -> None:
        cw, ch = request.canvas_w, request.canvas_h
        color = params.get("color") or "#000000"
        n = len(frames)
        for i, p in enumerate(frames):
            t = (i + 1) / n
            width = int(cw * self._ease_in_out(t))
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            ImageDraw.Draw(canvas).rectangle((0, 0, width, ch), fill=color)
            canvas.save(p)

    def _fade(
        self,
        frames: list[Path],
        request: MotionRequest,
        params: dict[str, Any],
    ) -> None:
        cw, ch = request.canvas_w, request.canvas_h
        layer, tw, th = self._load_text_overlay(request, params)
        cx = int(float(params.get("cx") or 0.5) * cw) - tw // 2
        cy = int(float(params.get("cy") or 0.5) * ch) - th // 2
        n = len(frames)
        for i, p in enumerate(frames):
            t = (i + 1) / n
            alpha = int(255 * t)
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            faded = layer.copy()
            # Apply alpha by multiplying the layer's alpha channel.
            arr = np.array(faded)
            arr[..., 3] = (arr[..., 3].astype(np.float32) * alpha / 255).astype(np.uint8)
            faded = Image.fromarray(arr, mode="RGBA")
            canvas.alpha_composite(faded, (cx, cy))
            canvas.save(p)


def _numeric_layer(text: str, cw: int, ch: int, scale: float, *, color: str) -> Image.Image:
    """Render a large numeric glyph (used by countdown_pulse)."""
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    font = ImageFont.truetype(
        "/System/Library/Fonts/Helvetica.ttc",
        int(cw * 0.4 * scale),
    ) if Path("/System/Library/Fonts/Helvetica.ttc").exists() else ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (cw - tw) // 2
    y = (ch - th) // 2 - bbox[1]
    draw.text((x, y), text, fill=color, font=font)
    return canvas


__all__ = ["OpenCVMotionBackend"]