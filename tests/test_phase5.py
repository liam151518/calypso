"""Tests for Phase 5 scripts (social_stats_publisher, auto_reply).

Run: `python -m pytest tests/test_phase5.py -v`
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts.auto_reply import Intent, classify, generate_reply
from scripts.social_stats_publisher import (
    PublishRequest,
    SocialStatsError,
    SocialStatsPublisher,
)


# ---------- fake Social Stats server ----------

class FakeSocialStats(BaseHTTPRequestHandler):
    last_request: dict | None = None

    def log_message(self, *_args, **_kwargs):
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/api/health":
            self._json(200, {"ok": True})
        elif self.path.startswith("/api/posts/"):
            self._json(200, {"post_id": self.path.split("/")[-1], "status": "published"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body_raw = self.rfile.read(length).decode() if length > 0 else "{}"
        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError:
            body = {}

        type(self).last_request = {
            "path": self.path,
            "body": body,
            "auth": self.headers.get("Authorization"),
        }
        self._json(200, {"publish_id": "pub-1", "platforms": body.get("platforms", [])})

    def _json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def fake_ss_server():
    server = HTTPServer(("127.0.0.1", 0), FakeSocialStats)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()


@pytest.fixture
def publisher(fake_ss_server, monkeypatch):
    host, port = fake_ss_server
    monkeypatch.setenv("SOCIAL_STATS_API_TOKEN", "test-token")
    return SocialStatsPublisher(base_url=f"http://{host}:{port}", api_token="test-token")


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    from PIL import Image
    img = Image.new("RGB", (512, 512), color=(255, 0, 0))
    path = tmp_path / "test.jpg"
    img.save(path, "JPEG")
    return path


@pytest.fixture(autouse=True)
def reset_fake():
    FakeSocialStats.last_request = None
    yield


# ---------- PublishRequest ----------

class TestPublishRequest:
    def test_valid_request(self, sample_image: Path):
        req = PublishRequest(
            media_path=sample_image,
            caption="Just dropped",
            platforms=["x"],
            post_id="post-1",
        )
        assert req.is_valid() is True

    def test_invalid_when_media_missing(self, tmp_path: Path):
        req = PublishRequest(
            media_path=tmp_path / "nope.jpg",
            caption="test",
            platforms=["x"],
        )
        assert req.is_valid() is False

    def test_invalid_when_caption_empty(self, sample_image: Path):
        req = PublishRequest(
            media_path=sample_image,
            caption="",
            platforms=["x"],
        )
        assert req.is_valid() is False

    def test_invalid_when_platforms_empty(self, sample_image: Path):
        req = PublishRequest(
            media_path=sample_image,
            caption="test",
            platforms=[],
        )
        assert req.is_valid() is False


# ---------- SocialStatsPublisher ----------

class TestSocialStatsPublisher:
    def test_health(self, publisher: SocialStatsPublisher):
        assert publisher.health() is True

    def test_publish_returns_publish_id(self, publisher: SocialStatsPublisher, sample_image: Path):
        req = PublishRequest(
            media_path=sample_image,
            caption="Just dropped the Damascus pink",
            platforms=["x", "instagram"],
            post_id="post-1",
        )
        result = publisher.publish(req)
        assert result["publish_id"] == "pub-1"
        assert "x" in result["platforms"]
        assert "instagram" in result["platforms"]

    def test_sends_correct_payload(self, publisher: SocialStatsPublisher, sample_image: Path):
        req = PublishRequest(
            media_path=sample_image,
            caption="Test caption",
            platforms=["x"],
            scheduled_at="2026-09-01T12:00:00Z",
            post_id="post-1",
        )
        publisher.publish(req)
        assert FakeSocialStats.last_request is not None
        body = FakeSocialStats.last_request["body"]
        assert body["caption"] == "Test caption"
        assert body["platforms"] == ["x"]
        assert body["scheduled_at"] == "2026-09-01T12:00:00Z"
        assert body["post_id"] == "post-1"

    def test_get_status(self, publisher: SocialStatsPublisher):
        status = publisher.get_status("post-1")
        assert status["status"] == "published"

    def test_publish_invalid_request_raises(self, publisher: SocialStatsPublisher, tmp_path: Path):
        req = PublishRequest(
            media_path=tmp_path / "nope.jpg",
            caption="test",
            platforms=["x"],
        )
        with pytest.raises(SocialStatsError, match="invalid request"):
            publisher.publish(req)


# ---------- Auto-reply classifier ----------

class TestClassify:
    def test_payment_always_forwards(self):
        result = classify("I want a refund for my chargeback")
        assert result.intent == Intent.PAYMENT_RELATED
        assert result.suggested_action == "forward_to_operator"

    def test_payment_takes_precedence_over_other_intents(self):
        # This message has both "refund" and "spin". Payment should win.
        result = classify("I want a refund, also which spin should I do")
        assert result.intent == Intent.PAYMENT_RELATED

    def test_spam_is_archived(self):
        result = classify("Make money fast! crypto investment opportunity")
        assert result.intent == Intent.SPAM
        assert result.suggested_action == "archive"

    def test_support_request_is_forwarded(self):
        result = classify("my order didn't arrive")
        assert result.intent == Intent.SUPPORT_REQUEST
        assert result.suggested_action == "forward_to_operator"

    def test_gacha_question_gets_auto_reply(self):
        result = classify("which cabinet should I pull from? tier list?")
        assert result.intent == Intent.GACHA_PULL_QUESTION
        assert result.suggested_action == "auto_reply"

    def test_single_gacha_keyword_matches(self):
        # One strong gacha keyword like "damascus" or "tier list" is enough
        result = classify("damascus drop?")
        assert result.intent == Intent.GACHA_PULL_QUESTION

    def test_brand_lone_keyword_does_not_match(self):
        # "spin" alone is too ambiguous to be a gacha question
        result = classify("I had a good spin")
        # Either other (most likely) or gacha with very low confidence;
        # acceptable behavior is that it doesn't trigger auto_reply
        if result.intent == Intent.GACHA_PULL_QUESTION:
            assert result.confidence < 0.7
        else:
            assert result.suggested_action == "forward_to_operator"

    def test_unknown_message_is_other(self):
        result = classify("hello there friend")
        assert result.intent == Intent.OTHER
        assert result.suggested_action == "forward_to_operator"

    def test_high_confidence_for_clear_matches(self):
        result = classify("refund please")
        assert result.confidence >= 0.9

    def test_lower_confidence_for_ambiguous(self):
        result = classify("hello")
        assert result.confidence < 0.7


class TestGenerateReply:
    def test_returns_empty_for_non_gacha(self):
        reply = generate_reply("I want a refund")
        assert reply == ""

    def test_tier_list_question(self):
        reply = generate_reply("tier list? best figure?")
        assert "tier list" in reply.lower() or "gachakingdoms.com" in reply.lower()

    def test_damascus_question(self):
        reply = generate_reply("damascus drop?")
        assert "damascus" in reply.lower()

    def test_location_question(self):
        reply = generate_reply("Rosebank machine location?")
        assert "rosebank" in reply.lower() or "cabinet" in reply.lower()

    def test_brand_voice_term_added(self):
        reply = generate_reply("tier list?", brand_voice_terms=["honestly the move"])
        assert "honestly the move" in reply


class TestAutoReplyCLI:
    def test_classifies(self, monkeypatch, capsys):
        from scripts import auto_reply
        monkeypatch.setattr("sys.argv", ["auto_reply.py", "tier list?"])
        rc = auto_reply._cli()
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["intent"] in [i.value for i in Intent]

    def test_classifies_with_reply(self, monkeypatch, capsys):
        from scripts import auto_reply
        monkeypatch.setattr("sys.argv", ["auto_reply.py", "damascus drop?", "--reply"])
        rc = auto_reply._cli()
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "reply" in parsed
