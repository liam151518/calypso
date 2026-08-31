"""Social Stats publisher — push approved posts to X, Instagram, TikTok.

This is a thin wrapper around the Social Stats self-hosted API (Phase 5
deliverable — see https://github.com/cbsshekhawat18-lab/social-stats-social-media-manager).

Per the plan: n8n calls this after the operator approves a Telegram message.
The publisher authenticates to Social Stats with the operator's stored tokens,
uploads the media, and posts.

Setup: docs/accounts.md → Social Stats (deployed in Phase 1.3 docker-compose)

Tests: tests/test_social_stats_publisher.py
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


class SocialStatsError(RuntimeError):
    """Raised when Social Stats API returns an error or is unreachable."""


@dataclass(frozen=True)
class PublishRequest:
    """A single publish request."""

    media_path: Path
    caption: str
    platforms: list[str]  # subset of ["x", "instagram", "tiktok"]
    scheduled_at: str | None = None  # ISO 8601; None = publish immediately
    post_id: str = ""

    def is_valid(self) -> bool:
        return bool(self.media_path.exists() and self.caption and self.platforms)


class SocialStatsPublisher:
    """Client for the Social Stats API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        *,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("SOCIAL_STATS_URL", "http://localhost:3000")).rstrip("/")
        self.api_token = api_token or os.environ.get("SOCIAL_STATS_API_TOKEN", "")
        self.timeout = timeout

    def _request(self, method: str, path: str, *, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read().decode()
                return json.loads(payload) if payload else {}
        except urllib.error.URLError as exc:
            raise SocialStatsError(f"cannot reach Social Stats at {url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode()[:500] if exc.fp else ""
            raise SocialStatsError(f"Social Stats HTTP {exc.code}: {body_text}") from exc

    # ---------- high-level API ----------

    def publish(self, request: PublishRequest) -> dict:
        """Publish to the requested platforms. Returns the publish_id per platform."""
        if not request.is_valid():
            raise SocialStatsError(f"invalid request: media exists? {request.media_path.exists()}, caption? {bool(request.caption)}, platforms? {request.platforms}")

        body = {
            "media_path": str(request.media_path),
            "caption": request.caption,
            "platforms": request.platforms,
            "post_id": request.post_id,
        }
        if request.scheduled_at:
            body["scheduled_at"] = request.scheduled_at

        return self._request("POST", "/api/publish", body=body)

    def schedule(self, request: PublishRequest) -> dict:
        """Schedule a publish for later. Same as publish() but with a future scheduled_at."""
        return self.publish(request)

    def get_status(self, post_id: str) -> dict:
        """Check the status of a post (publishing, published, failed)."""
        return self._request("GET", f"/api/posts/{post_id}")

    def health(self) -> bool:
        """Check API reachability."""
        try:
            self._request("GET", "/api/health")
            return True
        except SocialStatsError:
            return False


# ---------- module-level singleton ----------

_default_publisher: SocialStatsPublisher | None = None


def get_publisher() -> SocialStatsPublisher:
    """Return a process-wide publisher."""
    global _default_publisher
    if _default_publisher is None:
        _default_publisher = SocialStatsPublisher()
    return _default_publisher
