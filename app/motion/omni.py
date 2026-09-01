"""app.motion.omni. Phase E.3 — Omni client (opt-in).

Loaded only when `OMNI_API_KEY` is present. If unavailable, `available()`
returns False and the Compositor falls back to OpenCV. Auto quality-check
runs through the existing VLM judge path (app.agents.qc) and falls back
when score < 0.7.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.motion import MotionBackend, MotionClip, MotionRequest


@dataclass
class OmniMotionBackend:
    """Opt-in Omni client. Falls back gracefully when the API is missing."""

    name: str = "omni"
    base_url: str = "https://api.omni.example.com"
    api_key: str | None = None
    timeout: float = 30.0
    output_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.api_key is None:
            self.api_key = os.environ.get("OMNI_API_KEY", "")
        if self.output_dir is None:
            self.output_dir = (
                Path(__file__).resolve().parent.parent.parent / "outputs" / "motion"
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def available(self) -> bool:
        return bool(self.api_key)

    def generate(self, request: MotionRequest) -> MotionClip:
        if not self.available():
            # No key set → fall back to OpenCV rather than raise. The spec
            # says Omni is opt-in; the caller asked for motion and we owe
            # them a clip.
            from app.motion.opencv import OpenCVMotionBackend

            return OpenCVMotionBackend(output_dir=self.output_dir).generate(request)
        # In a real implementation we'd POST to {base_url}/motion and
        # download the resulting PNG sequence. For v1 we follow the spec's
        # "auto-fallback" rule: try, then fall back to OpenCV.
        try:
            clip = self._call_omni(request)
            if clip is not None and self._quality_ok(clip):
                return clip
        except Exception:  # noqa: BLE001
            pass
        from app.motion.opencv import OpenCVMotionBackend

        return OpenCVMotionBackend(output_dir=self.output_dir).generate(request)

    def _call_omni(self, request: MotionRequest) -> MotionClip | None:
        """Stub: returns None until Omni's contract is locked down."""
        body = json.dumps({
            "kind": request.kind,
            "params": request.params,
            "duration_s": request.duration_s,
            "fps": request.fps,
            "canvas_w": request.canvas_w,
            "canvas_h": request.canvas_h,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/motion",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                # Real response handling TBD.
                _ = resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError):
            return None
        return None

    def _quality_ok(self, clip: MotionClip) -> bool:
        """Delegate to VLM judge; falls back to True on any failure."""
        try:
            from app.agents import qc as qc_mod
        except Exception:  # noqa: BLE001
            return True
        try:
            score = qc_mod.score_clip(clip)
            return score is not None and score >= 0.7
        except Exception:  # noqa: BLE001
            return True


__all__ = ["OmniMotionBackend"]