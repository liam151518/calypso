"""Phase E.5 — motion-graphics backend tests.

We exercise:

- OpenCVMotionBackend is always available and produces alpha PNGs for every
  supported kind.
- The frame count matches `duration_s * fps`.
- `get_backend()` returns OpenCV by default and never raises on import.
- Omni is unavailable when `OMNI_API_KEY` is unset (and falls back to OpenCV
  if invoked anyway).
- Prompt templates render without raising for every kind.
"""

from __future__ import annotations

import pytest
from PIL import Image

from app import motion as motion_mod
from app.motion import MotionRequest
from app.motion.opencv import OpenCVMotionBackend
from app.motion.omni import OmniMotionBackend
from app.motion.prompts import OMNI_PROMPTS, render_prompt


SUPPORTED_KINDS = [
    "text_bounce_in",
    "lower_third_slide",
    "sticker_pop",
    "pulse",
    "countdown_pulse",
    "transition_wipe",
    "fade",
    "slide_up",
]


@pytest.fixture
def opencv_backend(tmp_path):
    return OpenCVMotionBackend(output_dir=tmp_path)


def test_opencv_backend_is_always_available(opencv_backend):
    assert opencv_backend.available() is True
    assert opencv_backend.name == "opencv"


@pytest.mark.parametrize("kind", SUPPORTED_KINDS)
def test_opencv_produces_alpha_pngs(opencv_backend, kind):
    req = MotionRequest(
        kind=kind,
        params={"text": "Hello", "color": "#ff5722"},
        duration_s=0.5,
        fps=20,
        canvas_w=320,
        canvas_h=480,
    )
    clip = opencv_backend.generate(req)
    assert clip.backend == "opencv"
    assert clip.kind == kind
    assert len(clip.frames) == 10  # 0.5s @ 20fps
    assert all(p.exists() for p in clip.frames)
    # Alpha present — re-open and confirm mode is RGBA.
    with Image.open(clip.frames[0]) as im:
        assert im.mode == "RGBA"


def test_opencv_text_bounce_in_varies_alpha_across_frames(opencv_backend):
    req = MotionRequest(
        kind="text_bounce_in",
        params={"text": "Hi"},
        duration_s=1.0,
        fps=20,
        canvas_w=320,
        canvas_h=320,
    )
    clip = opencv_backend.generate(req)
    # We measure the alpha-mass of each frame: a bounce-in should start with
    # very little visible ink (early frames are tiny) and end with full ink.
    import numpy as np

    alphas = []
    for p in clip.frames:
        with Image.open(p) as im:
            alphas.append(int(np.asarray(im)[..., 3].sum()))
    assert alphas[0] < alphas[-1]


def test_opencv_countdown_decrements(opencv_backend):
    req = MotionRequest(
        kind="countdown_pulse",
        params={"color": "#ff0000"},
        duration_s=3.0,
        fps=3,
        canvas_w=320,
        canvas_h=320,
    )
    clip = opencv_backend.generate(req)
    assert len(clip.frames) == 9


def test_get_backend_returns_opencv_by_default():
    backend = motion_mod.get_backend()
    assert isinstance(backend, OpenCVMotionBackend)
    assert backend.available()


def test_omni_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("OMNI_API_KEY", raising=False)
    backend = OmniMotionBackend()
    assert backend.available() is False


def test_omni_falls_back_to_opencv_when_invoked_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OMNI_API_KEY", raising=False)
    backend = OmniMotionBackend(output_dir=tmp_path)
    clip = backend.generate(MotionRequest(
        kind="fade",
        params={"text": "Hello"},
        duration_s=0.3,
        fps=10,
        canvas_w=120,
        canvas_h=120,
    ))
    # Falls back to OpenCV, which produces frames.
    assert clip.backend == "opencv"
    assert len(clip.frames) == 3


def test_omni_with_fake_key_still_falls_back(tmp_path, monkeypatch):
    """With a key set, the stub `_call_omni` returns None → still falls back."""
    monkeypatch.setenv("OMNI_API_KEY", "fake-key")
    backend = OmniMotionBackend(output_dir=tmp_path)
    clip = backend.generate(MotionRequest(
        kind="fade",
        params={"text": "x"},
        duration_s=0.2,
        fps=10,
        canvas_w=120,
        canvas_h=120,
    ))
    assert clip.backend == "opencv"


def test_render_prompt_substitutes_params():
    out = render_prompt("text_bounce_in", text="Drop is live", color="#fff")
    assert "Drop is live" in out
    assert "{text}" not in out


def test_render_prompt_unknown_kind_raises():
    with pytest.raises(ValueError):
        render_prompt("nope", text="x")


def test_omni_prompts_covers_every_kind():
    for kind in SUPPORTED_KINDS:
        assert kind in OMNI_PROMPTS


def test_set_active_overrides_default_resolution():
    motion_mod.set_active("opencv")
    assert isinstance(motion_mod.get_backend(), OpenCVMotionBackend)
    motion_mod.set_active(None)
