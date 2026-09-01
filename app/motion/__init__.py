"""app.motion. Phase E — motion-graphics backends for video overlays.

A `MotionBackend` knows how to render a `MotionRequest` (one of the
`MotionKIND` literals) into an alpha PNG sequence that the Compositor can
overlay on top of a scene.

Built-in backends:

- `app.motion.opencv.OpenCVMotionBackend` — always available, no network.
  Uses cv2 + numpy alpha masks to implement bounce/slide/pop/pulse/fade
  plus a simple wipe transition. Used as the default when Omni isn't
  configured.
- `app.motion.omni.OmniMotionBackend` — opt-in. Wraps the Omni API (or
  whatever Omni-compatible service exists); if `OMNI_API_KEY` is missing
  or the call fails the Compositor falls back to OpenCV.

Use `get_backend(name=None)` to resolve the preferred backend
(omni → opencv → fail) based on what's installed and configured.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable
from dataclasses import dataclass, field
from pathlib import Path

MotionKIND = Literal[
    "text_bounce_in",
    "lower_third_slide",
    "sticker_pop",
    "transition_wipe",
    "countdown_pulse",
    "fade",
    "slide_up",
    "pulse",
]


@dataclass
class MotionRequest:
    """Input to a motion backend."""

    kind: MotionKIND
    params: dict = field(default_factory=dict)
    duration_s: float = 1.0
    fps: int = 30
    canvas_w: int = 1080
    canvas_h: int = 1920


@dataclass
class MotionClip:
    """The output of a motion backend."""

    frames: list[Path]
    duration_s: float
    backend: str
    kind: str


@runtime_checkable
class MotionBackend(Protocol):
    name: str

    def available(self) -> bool: ...

    def generate(self, request: MotionRequest) -> MotionClip: ...


_active_backend: str | None = None


def set_active(name: str | None) -> None:
    """Force a particular backend. Pass None to clear the override."""
    global _active_backend
    _active_backend = name


def get_backend(name: str | None = None) -> MotionBackend:
    """Resolve the backend to use, in priority order:

      1. Explicit `name` (if it loads and is available)
      2. Active override (`set_active`)
      3. `omni` if available
      4. `opencv` fallback
    """
    from app.motion import opencv as opencv_mod

    candidates: list[MotionBackend] = []
    if name:
        candidates.append(_instantiate(name))
    if not candidates and _active_backend:
        candidates.append(_instantiate(_active_backend))
    if not candidates:
        # Try Omni first, fall back to opencv.
        try:
            from app.motion import omni as omni_mod

            backend = omni_mod.OmniMotionBackend()
            if backend.available():
                candidates.append(backend)
        except Exception:  # noqa: BLE001
            pass
    candidates.append(opencv_mod.OpenCVMotionBackend())
    for b in candidates:
        if b.available():
            return b
    raise RuntimeError("no motion backend available")


def _instantiate(name: str) -> MotionBackend:
    name = name.lower()
    if name == "opencv":
        from app.motion import opencv as opencv_mod

        return opencv_mod.OpenCVMotionBackend()
    if name == "omni":
        from app.motion import omni as omni_mod

        return omni_mod.OmniMotionBackend()
    raise ValueError(f"unknown motion backend: {name!r}")


__all__ = [
    "MotionBackend",
    "MotionRequest",
    "MotionClip",
    "MotionKIND",
    "get_backend",
    "set_active",
]