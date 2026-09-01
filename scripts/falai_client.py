"""fal.ai client. H3 Max (speed tier) and Kling 2.6 Pro (hero tier).

fal.ai is the fastest way to call multiple video models behind one API.
We use it for:
- MiniMax H3 Max: high-volume dailies (480p/768p, faster than base H3)
- Kling 2.6 Pro: 1/week hero posts (cinematic, $0.07/s)

Setup: docs/accounts.md → fal.ai

Tests: tests/test_falai_client.py
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

Model = Literal["minimax/h3-max", "kling-video/v2.6/pro"]


class FalError(RuntimeError):
    """Raised when the fal.ai API returns an error or is unreachable."""


@dataclass
class FalVideoRequest:
    """A single fal.ai video generation request."""

    model: Model
    prompt: str
    duration_seconds: int = 8
    resolution: Literal["480p", "768p", "1080p"] = "768p"
    seed: int | None = None
    reference_image_urls: list[str] = field(default_factory=list)
    negative_prompt: str = ""

    def estimated_cost_usd(self) -> float:
        """fal.ai's pricing is model-specific. Approximate."""
        if self.model == "minimax/h3-max":
            per_second = {"480p": 0.03, "768p": 0.05, "1080p": 0.08}
        elif self.model == "kling-video/v2.6/pro":
            per_second = {"480p": 0.05, "768p": 0.07, "1080p": 0.10}
        else:
            per_second = {"480p": 0.05, "768p": 0.07, "1080p": 0.10}
        return per_second[self.resolution] * self.duration_seconds


class FalAIClient:
    """Client for fal.ai's queue-based model API."""

    BASE_URL = "https://queue.fal.run"
    SYNC_URL = "https://fal.run"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
        poll_interval: float = 3.0,
        max_poll_seconds: float = 600.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("FAL_API_KEY", "")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_seconds = max_poll_seconds

        if not self.api_key:
            raise FalError("FAL_API_KEY not set")

    # ---------- low-level HTTP ----------

    def _request(self, method: str, url: str, *, body: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read().decode()
                result = json.loads(payload) if payload else {}
                if isinstance(result, dict) and "error" in result and "request_id" not in result:
                    raise FalError(f"fal.ai error: {result['error']}")
                return result
        except urllib.error.URLError as exc:
            raise FalError(f"cannot reach fal.ai at {url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode()[:500] if exc.fp else ""
            raise FalError(f"fal.ai HTTP {exc.code}: {body_text}") from exc

    # ---------- queue-based submission ----------

    def submit(self, request: FalVideoRequest) -> tuple[str, str]:
        """Submit to the queue. Returns (request_id, status_url)."""
        url = f"{self.BASE_URL}/{request.model}"
        body = {
            "prompt": request.prompt,
            "duration_seconds": request.duration_seconds,
            "resolution": request.resolution,
            "negative_prompt": request.negative_prompt,
        }
        if request.seed is not None:
            body["seed"] = request.seed
        if request.reference_image_urls:
            body["image_urls"] = request.reference_image_urls

        resp = self._request("POST", url, body=body)
        request_id = resp.get("request_id")
        status_url = resp.get("status_url") or f"{self.BASE_URL}/{request.model}/requests/{request_id}/status"
        if not request_id:
            raise FalError(f"no request_id in response: {resp}")
        return str(request_id), status_url

    def get_status(self, status_url: str) -> dict:
        """Poll a queued task. Returns the status dict (includes 'status' key).

        Accepts both absolute URLs and relative paths (relative to BASE_URL).
        """
        url = status_url if status_url.startswith("http") else f"{self.BASE_URL}{status_url}"
        return self._request("GET", url)

    def get_result(self, request_id: str, model: Model) -> dict:
        """Fetch the final result for a completed task."""
        url = f"{self.SYNC_URL}/{model}/requests/{request_id}"
        return self._request("GET", url)

    def wait_for_completion(self, status_url: str) -> dict:
        """Poll until the queued task is complete. Returns the final status dict."""
        deadline = time.monotonic() + self.max_poll_seconds
        while time.monotonic() < deadline:
            status = self.get_status(status_url)
            state = status.get("status")
            if state == "COMPLETED":
                return status
            if state in ("FAILED", "CANCELLED"):
                raise FalError(f"fal.ai task {state}: {status.get('error', 'unknown')}")
            time.sleep(self.poll_interval)
        raise FalError(f"fal.ai task did not complete within {self.max_poll_seconds}s")

    def download_result(self, request: FalVideoRequest, output_path: Path) -> Path:
        """Submit + wait + download. Returns the output path."""
        request_id, status_url = self.submit(request)
        self.wait_for_completion(status_url)
        result = self.get_result(request_id, request.model)
        url = (result.get("video") or {}).get("url")
        if not url:
            raise FalError(f"no video URL in result: {result}")
        try:
            with urllib.request.urlopen(url, timeout=self.timeout * 3) as resp:
                output_path.write_bytes(resp.read())
        except urllib.error.URLError as exc:
            raise FalError(f"failed to download video: {exc}") from exc
        return output_path

    # ---------- sync (no-queue) endpoint for small models ----------

    def run_sync(self, model: Model, body: dict) -> dict:
        """Run a model synchronously (no queue). Used for quick utility models."""
        url = f"{self.SYNC_URL}/{model}"
        return self._request("POST", url, body=body)

    def health(self) -> bool:
        """Check API reachability via the user endpoint."""
        try:
            self._request("GET", f"{self.SYNC_URL}/user")
            return True
        except FalError:
            return False


# ---------- module-level singleton ----------

_default_client: FalAIClient | None = None


def get_client() -> FalAIClient:
    """Return a process-wide fal.ai client."""
    global _default_client
    if _default_client is None:
        _default_client = FalAIClient()
    return _default_client
