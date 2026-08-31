"""Telegram notification client — the approval gate.

Sends a preview image + caption + 3 inline buttons (Approve / Regenerate / Skip)
to a configured Telegram chat. n8n polls the callback query to know which
button the user pressed.

Setup: docs/accounts.md → Telegram bot

Tests: tests/test_telegram_notify.py
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


class TelegramError(RuntimeError):
    """Raised when the Telegram Bot API returns an error or is unreachable."""


@dataclass
class ApprovalRequest:
    """A single approval request sent to Telegram."""

    image_path: Path
    caption: str
    post_id: str  # unique identifier for callback routing
    video_path: Path | None = None  # if present, sent as a video instead
    extra_metadata: dict = field(default_factory=dict)

    def to_callback_data(self, action: str) -> str:
        """Encode an action + post_id into Telegram's callback_data field (max 64 bytes)."""
        return f"{action}:{self.post_id}"


class TelegramNotifier:
    """Sends messages via the Telegram Bot API."""

    BASE_URL = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.timeout = timeout

        if not self.bot_token:
            raise TelegramError("TELEGRAM_BOT_TOKEN not set")
        if not self.chat_id:
            raise TelegramError("TELEGRAM_CHAT_ID not set")

    # ---------- low-level HTTP ----------

    def _api_call(self, method: str, *, params: dict | None = None) -> dict:
        url = f"{self.BASE_URL}/bot{self.bot_token}/{method}"
        if params is None:
            params = {}
        # Form-encode params that contain Path or non-string values
        form = {}
        for k, v in params.items():
            if isinstance(v, (str, int, float)):
                form[k] = str(v)
        # Multipart body via urllib: use a fresh Request with data= for the simple ones,
        # and a manual multipart encoder for file uploads.
        # Simpler: use multipart with urllib's Request
        boundary = "----telegram-notify-boundary"
        body = self._encode_multipart(form, params.get("_files", {}), boundary)
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read().decode()
                data = json.loads(payload)
                if not data.get("ok"):
                    raise TelegramError(f"Telegram API error: {data.get('description', data)}")
                return data
        except urllib.error.URLError as exc:
            raise TelegramError(f"cannot reach Telegram: {exc}") from exc

    @staticmethod
    def _encode_multipart(form_fields: dict, files: dict, boundary: str) -> bytes:
        """Encode a multipart/form-data body manually."""
        import mimetypes

        parts: list[bytes] = []
        for key, value in form_fields.items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            parts.append(value.encode("utf-8"))
            parts.append(b"\r\n")

        for key, file_info in files.items():
            file_path = Path(file_info["path"])
            if not file_path.exists():
                raise TelegramError(f"file not found: {file_path}")
            mime = file_info.get("mime") or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(
                f'Content-Disposition: form-data; name="{key}"; filename="{file_path.name}"\r\n'.encode()
            )
            parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
            parts.append(file_path.read_bytes())
            parts.append(b"\r\n")

        parts.append(f"--{boundary}--\r\n".encode())
        return b"".join(parts)

    # ---------- high-level API ----------

    def send_approval_request(self, request: ApprovalRequest) -> int:
        """Send the approval message with inline buttons. Returns the message_id."""
        if request.video_path and request.video_path.exists():
            return self._send_video_with_buttons(request)
        return self._send_photo_with_buttons(request)

    def _send_photo_with_buttons(self, request: ApprovalRequest) -> int:
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "Approve", "callback_data": request.to_callback_data("approve")},
                    {"text": "Regenerate", "callback_data": request.to_callback_data("regenerate")},
                    {"text": "Skip", "callback_data": request.to_callback_data("skip")},
                ]
            ]
        }
        params = {
            "chat_id": self.chat_id,
            "caption": request.caption[:1024],  # Telegram caption limit
            "reply_markup": json.dumps(buttons),
            "_files": {"photo": {"path": str(request.image_path), "mime": "image/jpeg"}},
        }
        resp = self._api_call("sendPhoto", params=params)
        return int(resp["result"]["message_id"])

    def _send_video_with_buttons(self, request: ApprovalRequest) -> int:
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "Approve", "callback_data": request.to_callback_data("approve")},
                    {"text": "Regenerate", "callback_data": request.to_callback_data("regenerate")},
                    {"text": "Skip", "callback_data": request.to_callback_data("skip")},
                ]
            ]
        }
        params = {
            "chat_id": self.chat_id,
            "caption": request.caption[:1024],
            "reply_markup": json.dumps(buttons),
            "_files": {"video": {"path": str(request.video_path), "mime": "video/mp4"}},
        }
        resp = self._api_call("sendVideo", params=params)
        return int(resp["result"]["message_id"])

    def send_text(self, text: str) -> int:
        """Send a plain text message. Used for system alerts (cost cap, errors)."""
        resp = self._api_call(
            "sendMessage",
            params={"chat_id": self.chat_id, "text": text[:4096]},
        )
        return int(resp["result"]["message_id"])

    def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        """Acknowledge a button press so Telegram stops showing the spinner."""
        self._api_call(
            "answerCallbackQuery",
            params={"callback_query_id": callback_query_id, "text": text[:200]},
        )

    def get_updates(self, offset: int | None = None, timeout: int = 30) -> list[dict]:
        """Long-poll for new messages (used by n8n to receive button presses)."""
        params: dict = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        resp = self._api_call("getUpdates", params=params)
        return resp.get("result", [])


# ---------- module-level singleton ----------

_default_notifier: TelegramNotifier | None = None


def get_notifier() -> TelegramNotifier:
    """Return a process-wide Telegram notifier."""
    global _default_notifier
    if _default_notifier is None:
        _default_notifier = TelegramNotifier()
    return _default_notifier
