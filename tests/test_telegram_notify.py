"""Tests for scripts/telegram_notify.py.

Run: `python -m pytest tests/test_telegram_notify.py -v`
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts.telegram_notify import (
    ApprovalRequest,
    TelegramError,
    TelegramNotifier,
)


# ---------- fake Telegram server ----------

class FakeTelegram(BaseHTTPRequestHandler):
    """Minimal Telegram Bot API mock."""

    last_request: dict | None = None
    next_message_id = 1000

    def log_message(self, *_args, **_kwargs):
        pass

    def do_POST(self):  # noqa: N802
        # Parse multipart body (very loosely: extract caption + reply_markup)
        content_type = self.headers.get("Content-Type", "")
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("latin-1", errors="ignore")

        caption = ""
        reply_markup = ""
        # Naive extraction. Find captions and reply_markup.
        for line in body.split("\r\n"):
            if line.startswith("Content-Disposition"):
                continue
            # Heuristic: parse the simple JSON or text that follows a blank line
        # Just look for our known field values
        if "caption" in body.lower():
            # Extract caption between name="caption" headers
            idx = body.lower().find('name="caption"')
            if idx >= 0:
                start = body.find("\r\n\r\n", idx)
                if start >= 0:
                    end = body.find("\r\n--", start)
                    caption = body[start + 4 : end if end > 0 else len(body)]

        if "reply_markup" in body.lower():
            idx = body.lower().find('name="reply_markup"')
            if idx >= 0:
                start = body.find("\r\n\r\n", idx)
                if start >= 0:
                    end = body.find("\r\n--", start)
                    reply_markup = body[start + 4 : end if end > 0 else len(body)]

        type(self).last_request = {
            "path": self.path,
            "content_type": content_type,
            "caption": caption,
            "reply_markup": reply_markup,
            "body_length": len(body),
        }

        # Respond based on the method
        method = self.path.split("?")[0].rsplit("/", 1)[-1]
        if method == "sendPhoto":
            msg_id = type(self).next_message_id
            type(self).next_message_id += 1
            self._json(200, {"ok": True, "result": {"message_id": msg_id}})
        elif method == "sendVideo":
            msg_id = type(self).next_message_id
            type(self).next_message_id += 1
            self._json(200, {"ok": True, "result": {"message_id": msg_id}})
        elif method == "sendMessage":
            msg_id = type(self).next_message_id
            type(self).next_message_id += 1
            self._json(200, {"ok": True, "result": {"message_id": msg_id}})
        elif method == "answerCallbackQuery":
            self._json(200, {"ok": True, "result": True})
        elif method == "getUpdates":
            self._json(200, {"ok": True, "result": []})
        else:
            self._json(404, {"ok": False, "description": "unknown method"})

    def _json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def fake_tg_server():
    """Spin up a fake Telegram server in a background thread."""
    # Monkey-patch BASE_URL before constructing clients
    original = TelegramNotifier.BASE_URL
    server = HTTPServer(("127.0.0.1", 0), FakeTelegram)
    host, port = server.server_address
    TelegramNotifier.BASE_URL = f"http://{host}:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    TelegramNotifier.BASE_URL = original
    server.shutdown()


@pytest.fixture
def notifier(fake_tg_server):
    return TelegramNotifier(bot_token="test-token", chat_id="12345")


@pytest.fixture(autouse=True)
def reset_fake_tg():
    FakeTelegram.last_request = None
    FakeTelegram.next_message_id = 1000
    yield


@pytest.fixture
def sample_photo(tmp_path: Path) -> Path:
    from PIL import Image
    img = Image.new("RGB", (512, 512), color=(255, 0, 0))
    path = tmp_path / "test.jpg"
    img.save(path, "JPEG")
    return path


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    # A minimal MP4. Just a file with the right extension.
    path = tmp_path / "test.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
    return path


# ---------- tests ----------

class TestApprovalRequest:
    def test_callback_data_within_byte_limit(self):
        req = ApprovalRequest(
            image_path=Path("/tmp/x.jpg"),
            caption="test",
            post_id="post-2026-08-31-001",
        )
        callback = req.to_callback_data("approve")
        assert callback.startswith("approve:")
        assert len(callback.encode("utf-8")) <= 64  # Telegram's limit


class TestTelegramNotifierInit:
    def test_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with pytest.raises(TelegramError, match="BOT_TOKEN"):
            TelegramNotifier(bot_token="", chat_id="x")

    def test_raises_without_chat_id(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        with pytest.raises(TelegramError, match="CHAT_ID"):
            TelegramNotifier(bot_token="x", chat_id="")

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "env-chat")
        n = TelegramNotifier()
        assert n.bot_token == "env-token"
        assert n.chat_id == "env-chat"


class TestSendPhoto:
    def test_returns_message_id(self, notifier: TelegramNotifier, sample_photo: Path):
        req = ApprovalRequest(image_path=sample_photo, caption="PINK DROP", post_id="post-1")
        msg_id = notifier.send_approval_request(req)
        assert msg_id >= 1000

    def test_sends_caption(self, notifier: TelegramNotifier, sample_photo: Path):
        req = ApprovalRequest(image_path=sample_photo, caption="JUST DROPPED", post_id="post-1")
        notifier.send_approval_request(req)
        assert FakeTelegram.last_request is not None
        assert "JUST DROPPED" in FakeTelegram.last_request["caption"]

    def test_truncates_oversized_caption(self, notifier: TelegramNotifier, sample_photo: Path):
        long_caption = "x" * 2000
        req = ApprovalRequest(image_path=sample_photo, caption=long_caption, post_id="post-1")
        notifier.send_approval_request(req)
        assert FakeTelegram.last_request is not None
        assert len(FakeTelegram.last_request["caption"]) <= 1024


class TestSendVideo:
    def test_sends_video_when_path_provided(
        self, notifier: TelegramNotifier, sample_photo: Path, sample_video: Path
    ):
        req = ApprovalRequest(
            image_path=sample_photo,
            caption="video test",
            post_id="post-video-1",
            video_path=sample_video,
        )
        msg_id = notifier.send_approval_request(req)
        assert msg_id >= 1000


class TestSendText:
    def test_returns_message_id(self, notifier: TelegramNotifier):
        msg_id = notifier.send_text("hello")
        assert msg_id >= 1000


class TestGetUpdates:
    def test_returns_empty_list(self, notifier: TelegramNotifier):
        updates = notifier.get_updates(timeout=1)
        assert updates == []


class TestAnswerCallback:
    def test_does_not_raise(self, notifier: TelegramNotifier):
        # Should not raise
        notifier.answer_callback("cb-query-id-1", text="approved")
