"""app/publishers/instagram.py. Instagram publisher via instagrapi.

Wraps ``instagrapi.Client`` behind the standard :class:`Publisher`
protocol so the scheduler can dispatch outputs to Instagram just like
it does to Telegram or dry_run. The dependency is *optional* — if
``instagrapi`` is not installed the publisher reports ``can_publish=False``
and the dispatcher falls back to dry_run.

Credentials:
    INSTAGRAM_USERNAME         required
    INSTAGRAM_PASSWORD         required
    INSTAGRAM_SESSION_FILE     optional, path to a pickled session file
                               (avoids repeated 2FA / login challenges)

Why instagrapi and not Meta Graph API? instagrapi speaks the private
Instagram API which allows photo + video + carousel + reel uploads
without going through the Graph API's content-publishing review queue.
Meta Graph is more "official" but requires a Business/Creator account
and a days-long app review. Both have their place; instagrapi is the
default because it's the only one that works for a fresh operator.
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger(__name__)

NAME = "instagram"


class Publisher(Protocol):
    name: str

    def can_publish(self, output: dict[str, Any], platform: str) -> bool: ...
    def publish(self, output: dict[str, Any], platform: str) -> dict[str, Any]: ...


@dataclass
class _InstagramState:
    """Lazy-loaded client + the timestamp we logged in at."""

    client: Any
    logged_in_at: float


class InstagramPublisher:
    """Publisher that uploads images / videos to Instagram via instagrapi."""

    name = NAME

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        session_file: str | None = None,
    ) -> None:
        self.username = username or os.environ.get("INSTAGRAM_USERNAME")
        self.password = password or os.environ.get("INSTAGRAM_PASSWORD")
        self.session_file = (
            session_file
            or os.environ.get("INSTAGRAM_SESSION_FILE")
            or "~/.calypso/instagram_session.pickle"
        )
        self._state: _InstagramState | None = None

    # ---- helpers --------------------------------------------------------

    def _session_path(self) -> Path:
        return Path(self.session_file).expanduser()

    def _load_instagrapi(self) -> Any:
        """Lazy import so the dependency stays optional. Tests mock this."""
        try:
            from instagrapi import Client  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "instagrapi is not installed — `pip install instagrapi`"
            ) from exc
        return Client

    def _ensure_client(self) -> Any:
        """Return a logged-in instagrapi.Client, reusing a pickled session
        when one is available."""
        if self._state is not None and (time.time() - self._state.logged_in_at) < 3600:
            return self._state.client
        Client = self._load_instagrapi()
        client = Client()
        session_path = self._session_path()
        if session_path.exists():
            try:
                client.load_settings(pickle.loads(session_path.read_bytes()))
                # Touch the API to confirm the session is still valid.
                client.get_timeline_feed()
                log.info("instagram: reused session from %s", session_path)
            except Exception as exc:  # noqa: BLE001
                log.warning("instagram: session load failed, re-logging in: %s", exc)
                client = Client()
                self._login(client)
        else:
            self._login(client)
        self._state = _InstagramState(client=client, logged_in_at=time.time())
        return client

    def _login(self, client: Any) -> None:
        if not (self.username and self.password):
            raise RuntimeError("INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD not set")
        client.login(username=self.username, password=self.password)
        try:
            session_path = self._session_path()
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_bytes(pickle.dumps(client.get_settings()))
        except Exception as exc:  # noqa: BLE001
            log.warning("instagram: could not persist session: %s", exc)

    # ---- protocol ------------------------------------------------------

    def can_publish(self, output: dict[str, Any], platform: str) -> bool:
        if platform != "instagram":
            return False
        if not (self.username and self.password):
            return False
        file_path = output.get("file_path")
        return bool(file_path) and Path(str(file_path)).exists()

    def publish(self, output: dict[str, Any], platform: str) -> dict[str, Any]:
        if platform != "instagram":
            return {"external_id": "", "url": None, "status": "skipped"}
        file_path = output.get("file_path")
        if not file_path or not Path(str(file_path)).exists():
            log.warning(
                "instagram: skipped output=%s — no file_path",
                output.get("id"),
            )
            return {"external_id": "instagram-skipped", "url": None, "status": "skipped"}
        try:
            client = self._ensure_client()
        except RuntimeError as exc:
            log.error("instagram: cannot publish — %s", exc)
            return {"external_id": "instagram-error", "url": None, "status": "failed"}
        ext = Path(str(file_path)).suffix.lower()
        caption = (output.get("caption") or output.get("title") or "")[:2200]
        try:
            if ext in {".mp4", ".mov", ".webm"}:
                # Clips API: video upload with optional cover thumbnail.
                media = client.video_upload(
                    path=str(file_path),
                    caption=caption,
                )
            else:
                media = client.photo_upload(
                    path=str(file_path),
                    caption=caption,
                )
        except Exception as exc:  # noqa: BLE001
            log.exception("instagram: upload failed: %s", exc)
            return {"external_id": "instagram-error", "url": None, "status": "failed"}
        ext_id = str(getattr(media, "id", ""))
        # instagrapi doesn't return a public URL; the canonical permalink
        # can be built with media.code if we have it.
        code = getattr(media, "code", None)
        url = f"https://www.instagram.com/p/{code}/" if code else None
        log.info(
            "instagram: uploaded output=%s media_id=%s url=%s",
            output.get("id"),
            ext_id,
            url,
        )
        return {"external_id": ext_id, "url": url, "status": "sent"}


def register() -> bool:
    """Register this publisher with the global registry if instagrapi is
    available. The publisher's ``can_publish`` is what gates whether it
    actually fires — registration just makes it eligible.

    Returns True when the publisher was added to the registry.
    """
    try:
        from app.publisher import register as register_core
    except ImportError:
        return False
    pub = InstagramPublisher()
    register_core(pub)  # type: ignore[arg-type]
    return True


__all__ = ["InstagramPublisher", "NAME", "register"]
