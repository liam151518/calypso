"""app.publisher. Pluggable publish surface for brand-poster outputs.

A ``Publisher`` is anything that can ship an output to an external
platform. The default plugins are:

* :class:`DryRunPublisher` — logs and returns a synthetic id, useful for
  development and for the Phase C exit gate.
* :class:`TelegramHandoffPublisher` — posts the output to a configured
  Telegram chat (separate from the approval bot) so the operator can
  manually publish from their phone.

Phase G will add real publishers via the extension system (instagrapi,
tweepy, tiktok). Each publisher is responsible for its own credentials;
the orchestrator (Phase C.3 scheduler) only routes by ``name``.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)


class Publisher(Protocol):
    name: str

    def can_publish(self, output: dict[str, Any], platform: str) -> bool: ...
    def publish(self, output: dict[str, Any], platform: str) -> dict[str, Any]: ...


@dataclass
class PublishResult:
    external_id: str
    url: str | None
    status: str = "sent"

    def to_dict(self) -> dict[str, Any]:
        return {"external_id": self.external_id, "url": self.url, "status": self.status}


class DryRunPublisher:
    """Default publisher: logs the dispatch and returns a fake id.

    This is what the Phase C exit gate uses. It's also what runs when
    no other plugin claims an output, so the scheduler never silently
    drops a job.
    """

    name = "dry_run"

    def can_publish(self, output: dict[str, Any], platform: str) -> bool:
        return True

    def publish(self, output: dict[str, Any], platform: str) -> dict[str, Any]:
        ext_id = f"dryrun-{int(time.time() * 1000)}"
        log.info(
            "[dry_run] publish output_id=%s platform=%s external_id=%s",
            output.get("id"),
            platform,
            ext_id,
        )
        return PublishResult(
            external_id=ext_id,
            url=None,
            status="dry_run",
        ).to_dict()


class TelegramHandoffPublisher:
    """Send the output's file + caption to a Telegram chat for manual posting.

    Uses ``python-telegram-bot`` only when ``TELEGRAM_HANDOFF_CHAT_ID`` is
    set; otherwise it no-ops with a warning. This keeps the dependency
    optional — when the bot token isn't configured, the scheduler falls
    back to dry_run.
    """

    name = "telegram_handoff"

    def __init__(self, bot_token: str | None = None,
                 chat_id: str | None = None) -> None:
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_HANDOFF_CHAT_ID")

    def can_publish(self, output: dict[str, Any], platform: str) -> bool:
        return bool(self.bot_token and self.chat_id)

    def publish(self, output: dict[str, Any], platform: str) -> dict[str, Any]:
        if not self.can_publish(output, platform):
            log.warning(
                "[telegram_handoff] skipped output=%s — bot_token or chat_id missing",
                output.get("id"),
            )
            return PublishResult(
                external_id="telegram-skipped",
                url=None,
                status="skipped",
            ).to_dict()
        try:
            # Lazy import keeps the optional dependency truly optional.
            from telegram import Bot

            bot = Bot(token=self.bot_token)  # type: ignore[arg-type]
            file_path = output.get("file_path")
            caption = output.get("caption") or output.get("title") or ""
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    msg = bot.send_photo(
                        chat_id=self.chat_id,
                        photo=f,
                        caption=caption[:1024],
                    )
            else:
                msg = bot.send_message(
                    chat_id=self.chat_id,
                    text=caption or f"Output {output.get('id')}",
                )
            ext_id = str(getattr(msg, "message_id", ""))
            url = None
            if msg.chat and msg.chat.username:
                url = f"https://t.me/{msg.chat.username}/{msg.message_id}"
            return PublishResult(external_id=ext_id, url=url, status="sent").to_dict()
        except Exception as exc:  # noqa: BLE001
            log.exception("[telegram_handoff] failed: %s", exc)
            return PublishResult(
                external_id="telegram-error",
                url=None,
                status="failed",
            ).to_dict()


_REGISTRY: dict[str, Publisher] = {
    "dry_run": DryRunPublisher(),
    "telegram_handoff": TelegramHandoffPublisher(),
}


def register(publisher: Publisher) -> None:
    _REGISTRY[publisher.name] = publisher


def get(name: str) -> Publisher:
    if name not in _REGISTRY:
        raise KeyError(f"unknown publisher: {name}")
    return _REGISTRY[name]


def list_publishers() -> list[str]:
    return sorted(_REGISTRY.keys())


def dispatch(output: dict[str, Any], platform: str, *,
             preferred: str | None = None) -> dict[str, Any]:
    """Dispatch an output using the preferred publisher or the first available."""
    if preferred:
        pub = get(preferred)
        if pub.can_publish(output, platform):
            return pub.publish(output, platform)
    for pub in _REGISTRY.values():
        if pub.can_publish(output, platform):
            return pub.publish(output, platform)
    # No publisher claims it; fall back to dry_run so the job still completes.
    return DryRunPublisher().publish(output, platform)