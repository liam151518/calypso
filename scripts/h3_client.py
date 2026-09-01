"""MiniMax H3 video generation client.

Talks to the MiniMax platform's H3 video generation API at api.minimax.io.
The 3-stage pipeline:
  1. H3-Context-IR. Establishes the visual context from references.
  2. H3-Base. Generates the base 768p video with native audio.
  3. H3-Regenerate-2K. Upscales to 2K with detail preservation.

Mode: Ref2VA (reference-to-video-and-audio). Feed it Folder A references
+ Folder B brand assets, get a coherent gacha-style clip with native
32 kHz stereo audio.

Setup: docs/accounts.md → MiniMax platform

Tests: tests/test_h3_client.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Mode = Literal["ref2va", "text2video", "image2video"]


class H3Error(RuntimeError):
    """Raised when the MiniMax H3 API returns an error or is unreachable."""


@dataclass
class VideoRequest:
    """A single video generation request."""

    prompt: str
    reference_paths: list[Path] = field(default_factory=list)
    motion: str | None = None
    duration_seconds: int = 8
    resolution: Literal["480p", "768p", "1080p", "2k"] = "768p"
    mode: Mode = "ref2va"
    seed: int | None = None
    negative_prompt: str = ""
    audio_prompt: str | None = None  # optional H3 audio style guidance
    brand_assets: list[Path] = field(default_factory=list)

    def estimated_cost_usd(self) -> float:
        """Rough cost estimate based on resolution + duration. Real costs are server-side."""
        per_second = {
            "480p": 0.05,
            "768p": 0.07,
            "1080p": 0.10,
            "2k": 0.14,
        }
        return per_second[self.resolution] * self.duration_seconds


class H3Client:
    """Client for the MiniMax H3 video API."""

    BASE_URL = "https://api.minimax.io"

    def __init__(
        self,
        api_token: str | None = None,
        *,
        timeout: float = 30.0,
        poll_interval: float = 5.0,
        max_poll_seconds: float = 600.0,
    ) -> None:
        self.api_token = api_token or os.environ.get("MINIMAX_API_TOKEN", "")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_seconds = max_poll_seconds

        if not self.api_token:
            raise H3Error("MINIMAX_API_TOKEN not set")

    # ---------- low-level HTTP ----------

    def _request(self, method: str, path: str, *, body: dict | None = None) -> dict:
        url = f"{self.BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read().decode()
                result = json.loads(payload) if payload else {}
                if result.get("error"):
                    raise H3Error(f"H3 API error: {result['error']}")
                return result
        except urllib.error.URLError as exc:
            raise H3Error(f"cannot reach H3 API at {url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode()[:500] if exc.fp else ""
            raise H3Error(f"H3 API HTTP {exc.code}: {body_text}") from exc

    # ---------- high-level API ----------

    def submit_generation(self, request: VideoRequest) -> str:
        """Submit a generation request. Returns the task_id."""
        payload = {
            "model": "MiniMax-H3",
            "mode": request.mode,
            "prompt": request.prompt,
            "duration_seconds": request.duration_seconds,
            "resolution": request.resolution,
            "negative_prompt": request.negative_prompt,
            "reference_urls": [str(p) for p in request.reference_paths],
            "brand_asset_urls": [str(p) for p in request.brand_assets],
        }
        if request.motion:
            payload["motion"] = request.motion
        if request.audio_prompt:
            payload["audio_prompt"] = request.audio_prompt
        if request.seed is not None:
            payload["seed"] = request.seed

        resp = self._request("POST", "/v1/video/generations", body=payload)
        task_id = resp.get("task_id")
        if not task_id:
            raise H3Error(f"no task_id in response: {resp}")
        return str(task_id)

    def get_status(self, task_id: str) -> dict:
        """Poll a task's status. Returns the full status dict."""
        return self._request("GET", f"/v1/video/generations/{task_id}")

    def wait_for_completion(self, task_id: str) -> dict:
        """Poll until the task is complete. Returns the final status dict."""
        deadline = time.monotonic() + self.max_poll_seconds
        while time.monotonic() < deadline:
            status = self.get_status(task_id)
            state = status.get("status")
            if state == "completed":
                return status
            if state in ("failed", "cancelled"):
                raise H3Error(f"H3 task {task_id} {state}: {status.get('error', 'unknown')}")
            time.sleep(self.poll_interval)
        raise H3Error(f"H3 task {task_id} did not complete within {self.max_poll_seconds}s")

    def download_result(self, task_id: str, output_path: Path) -> Path:
        """Download the completed video to output_path. Returns the path."""
        status = self.wait_for_completion(task_id)
        url = status.get("video_url")
        if not url:
            raise H3Error(f"no video_url in completed status: {status}")
        try:
            with urllib.request.urlopen(url, timeout=self.timeout * 3) as resp:
                output_path.write_bytes(resp.read())
        except urllib.error.URLError as exc:
            raise H3Error(f"failed to download video: {exc}") from exc
        return output_path

    def generate(self, request: VideoRequest, output_path: Path) -> Path:
        """Submit + wait + download. Returns the output path."""
        task_id = self.submit_generation(request)
        return self.download_result(task_id, output_path)

    def health(self) -> bool:
        """Check API reachability. Returns True if the user-info endpoint responds."""
        try:
            self._request("GET", "/v1/user/info")
            return True
        except H3Error:
            return False


# ---------- module-level singleton ----------

_default_client: H3Client | None = None


def get_client() -> H3Client:
    """Return a process-wide H3 client."""
    global _default_client
    if _default_client is None:
        _default_client = H3Client()
    return _default_client
