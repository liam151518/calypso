"""app/upscale.py. Upscale an image with Real-ESRGAN (local) or fal.ai.

The choice between local and cloud is intentionally runtime-driven:
    - "realesrgan" — tries to shell out to `realesrgan-ncnn-vulkan` (or
      a binary path from REALESRGAN_BIN). When the binary is missing,
      we fall back to the cloud path with a warning. This keeps the
      UX identical regardless of whether the operator has a GPU.
    - "fal" — submits to fal.ai's ESRGAN endpoint via `image_jobs`.

Both paths return a new file path + cost estimate. Callers (the API +
UI) wrap the result in an `output_versions` row so the upscale lives in
the version history.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger(__name__)

Scale = Literal[2, 4]
Model = Literal["realesrgan", "fal"]
DEFAULT_BIN = "realesrgan-ncnn-vulkan"
DEFAULT_MODEL = "realesrgan-x4plus"
_FAL_MODEL = "fal-ai/esrgan"


@dataclass
class UpscaleResult:
    file_path: str
    cost_usd: float
    scale: int
    model_used: str
    width: int
    height: int
    face_enhance: bool = False
    elapsed_seconds: float = 0.0
    warnings: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "cost_usd": self.cost_usd,
            "scale": self.scale,
            "model_used": self.model_used,
            "width": self.width,
            "height": self.height,
            "face_enhance": self.face_enhance,
            "elapsed_seconds": self.elapsed_seconds,
            "warnings": self.warnings or [],
        }


# ---- public API ---------------------------------------------------------


def upscale(
    file_path: str,
    *,
    scale: Scale = 4,
    model: Model = "realesrgan",
    face_enhance: bool = False,
    output_dir: str | None = None,
) -> UpscaleResult:
    """Upscale an image. `scale` must be 2 or 4.

    Raises:
        FileNotFoundError — when the input file doesn't exist.
        ValueError        — on invalid scale.
        RuntimeError      — when the requested backend fails and no
                           fallback succeeded.
    """
    if scale not in (2, 4):
        raise ValueError(f"scale must be 2 or 4, got {scale!r}")
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(file_path)

    started = time.monotonic()
    warnings: list[str] = []

    # Try the requested backend first, then fall back.
    if model == "realesrgan":
        try:
            result = _upscale_realesrgan(
                src, scale=scale, face_enhance=face_enhance,
                output_dir=output_dir,
            )
        except RuntimeError as exc:
            log.warning("local Real-ESRGAN failed (%s) — falling back to fal.ai", exc)
            warnings.append(f"local realesrgan failed: {exc}")
            try:
                result = _upscale_fal(
                    src, scale=scale,
                    face_enhance=face_enhance,
                    output_dir=output_dir,
                )
            except Exception as exc2:  # noqa: BLE001
                raise RuntimeError(
                    f"both upscalers failed: local={exc!s}; fal={exc2!s}"
                ) from exc2
    elif model == "fal":
        result = _upscale_fal(
            src, scale=scale,
            face_enhance=face_enhance,
            output_dir=output_dir,
        )
    else:
        raise ValueError(f"unknown model: {model!r}")

    result.warnings = warnings
    result.elapsed_seconds = round(time.monotonic() - started, 3)
    return result


# ---- local Real-ESRGAN --------------------------------------------------


def _realesrgan_binary() -> str | None:
    """Return the binary path if Real-ESRGAN is installed, else None.

    Honours REALESRGAN_BIN env override, then PATH lookup."""
    override = os.environ.get("REALESRGAN_BIN")
    if override and Path(override).exists():
        return override
    return shutil.which(DEFAULT_BIN)


def _upscale_realesrgan(
    src: Path, *, scale: int, face_enhance: bool,
    output_dir: str | None,
) -> UpscaleResult:
    """Shell out to Real-ESRGAN ncnn. Returns the upscaled path."""
    bin_path = _realesrgan_binary()
    if not bin_path:
        raise RuntimeError(
            f"{DEFAULT_BIN} not on PATH and REALESRGAN_BIN not set"
        )
    out_dir = Path(output_dir) if output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{src.stem}_x{scale}{src.suffix}"
    model_name = DEFAULT_MODEL if scale == 4 else "realesrgan-x4plus-anime"
    cmd = [bin_path, "-i", str(src), "-o", str(out_path),
           "-s", str(scale), "-n", model_name]
    if face_enhance:
        # Real-ESRGAN ncnn has a GFPGAN face-enhancement option via -g.
        cmd.extend(["-g", "0"])  # face enhance on, single GPU
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("realesrgan timed out after 120s") from exc
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(
            f"realesrgan failed: rc={proc.returncode} stderr={proc.stderr.strip()[:300]}"
        )

    from PIL import Image
    with Image.open(out_path) as img:
        w, h = img.size
    return UpscaleResult(
        file_path=str(out_path),
        cost_usd=0.0,  # local is free
        scale=scale,
        model_used="realesrgan",
        width=w,
        height=h,
        face_enhance=face_enhance,
    )


# ---- cloud (fal.ai) -----------------------------------------------------


_FAL_COST_PER_MEGAPIXEL_USD = 0.04   # rough; matches fal-ai/esrgan page


def _upscale_fal(
    src: Path, *, scale: int, face_enhance: bool,
    output_dir: str | None,
) -> UpscaleResult:
    """Submit to fal.ai ESRGAN via the fal-client SDK.

    When `FAL_API_KEY` is not configured, falls back to a deterministic
    PIL Lanczos upscale so tests + first-run UX still produce a result.
    The "fallback" path is clearly marked in the returned `model_used`
    field as `fal_fallback`.
    """
    out_dir = Path(output_dir) if output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{src.stem}_x{scale}_fal{src.suffix}"

    if not os.environ.get("FAL_API_KEY"):
        # Offline / test mode: do a PIL resize and return a synthetic cost.
        log.info("upscale: FAL_API_KEY unset; using PIL fallback for %s", src)
        from PIL import Image
        with Image.open(src) as img:
            img = img.convert("RGB")
            new_size = (img.size[0] * scale, img.size[1] * scale)
            img.resize(new_size, Image.LANCZOS).save(out_path, "PNG")
            w, h = new_size
        return UpscaleResult(
            file_path=str(out_path),
            cost_usd=0.0,
            scale=scale,
            model_used="fal_fallback",
            width=w,
            height=h,
            face_enhance=face_enhance,
            warnings=["FAL_API_KEY not set — used PIL fallback"],
        )

    # Real path: call fal-client (kept minimal so we don't import the SDK
    # at module load time).
    try:
        import fal_client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "fal-client is not installed; run `pip install fal-client`"
        ) from exc
    with open(src, "rb") as fh:
        url = fal_client.upload(fh.read(), content_type="image/png")
    result = fal_client.subscribe(
        _FAL_MODEL,
        arguments={"image_url": url, "scale": scale,
                   "face_enhance": face_enhance},
    )
    # Result format varies; pull the first image URL out.
    images = result.get("images") if isinstance(result, dict) else None
    if not images:
        raise RuntimeError(f"fal.ai response had no images: {result!r}")
    out_url = images[0].get("url") if isinstance(images[0], dict) else None
    if not out_url:
        raise RuntimeError(f"fal.ai image entry had no url: {images[0]!r}")
    import urllib.request
    with urllib.request.urlopen(out_url, timeout=60) as resp:
        out_path.write_bytes(resp.read())
    from PIL import Image
    with Image.open(out_path) as img:
        w, h = img.size
    return UpscaleResult(
        file_path=str(out_path),
        cost_usd=float(_FAL_COST_PER_MEGAPIXEL_USD * (w * h) / 1_000_000),
        scale=scale,
        model_used="fal",
        width=w,
        height=h,
        face_enhance=face_enhance,
    )


__all__ = [
    "upscale",
    "UpscaleResult",
    "Scale",
    "Model",
]
