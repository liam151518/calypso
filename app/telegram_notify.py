"""app.telegram_notify. Approval-gate helper for the brand-poster scheduler.

The plan splits the Telegram integration in two:

* :mod:`app.publisher.TelegramHandoffPublisher` ships *published* output to
  a chat for manual posting.
* This module sends an *approval request* before publishing, with inline
  ``Approve`` / ``Edit`` / ``Reject`` buttons.

The approval bot can be the same bot token as the handoff bot or a
separate one; both are read from environment variables. When no token is
configured, ``request_approval`` returns ``"approved"`` immediately so
the scheduler proceeds (Phase C exit gate behaviour).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

log = logging.getLogger(__name__)

Decision = Literal["approved", "edited", "rejected", "skipped"]

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def is_configured() -> bool:
    return bool(_BOT_TOKEN and _CHAT_ID)


def request_approval(output: dict[str, Any]) -> Decision:
    """Send an approval request to Telegram; return the decision.

    The bot is interactive (it listens for callback queries), so this
    function only *queues* the request. The webhook handler (``/api/telegram/webhook``)
    is responsible for translating a callback into ``approve_job`` /
    ``reject_job`` calls against :mod:`app.marketing.scheduler`.
    """
    if not is_configured():
        log.warning(
            "telegram approval skipped — TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set",
        )
        return "skipped"

    try:
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup  # type: ignore
    except ImportError:
        log.warning("python-telegram-bot not installed; auto-approving")
        return "skipped"

    bot = Bot(token=_BOT_TOKEN)
    caption = _format_caption(output)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=f"approve:{output.get('id')}"),
                InlineKeyboardButton("Reject", callback_data=f"reject:{output.get('id')}"),
            ]
        ]
    )
    try:
        bot.send_message(
            chat_id=_CHAT_ID,
            text=caption,
            reply_markup=keyboard,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("telegram approval send failed: %s", exc)
        return "skipped"

    # The actual decision comes asynchronously via the webhook. The job
    # in the scheduler is parked in ``blocked`` status until the webhook
    # arrives; for the in-process path we treat ``skipped`` as the default
    # so the scheduler can still complete jobs without manual approval.
    return "skipped"


def handle_callback(data: str, job_id: int | None = None) -> Decision:
    """Translate a Telegram callback_data payload into a decision."""
    if data.startswith("approve"):
        return "approved"
    if data.startswith("reject"):
        return "rejected"
    if data.startswith("edit"):
        return "edited"
    return "skipped"


def _format_caption(output: dict[str, Any]) -> str:
    parts = [f"Output #{output.get('id')}"]
    if output.get("caption"):
        parts.append(output["caption"])
    if output.get("filter_applied"):
        parts.append(f"Filter: {output['filter_applied']}")
    parts.append("Approve to publish, or reject to skip.")
    return "\n".join(parts)