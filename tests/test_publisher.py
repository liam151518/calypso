"""Phase C publisher tests.

Dry-run + Telegram handoff behaviour, plus the registry dispatcher. The
Telegram publisher is exercised without a real token by asserting that
``can_publish`` is False (so the dispatcher falls through to dry-run).
"""

from __future__ import annotations

from app import publisher as publisher_mod


def _output(**overrides):
    base = {"id": 1, "file_path": "/tmp/output.jpg", "caption": "Hello"}
    base.update(overrides)
    return base


def test_dry_run_always_can_publish():
    p = publisher_mod.DryRunPublisher()
    assert p.can_publish(_output(), "instagram") is True


def test_dry_run_returns_synthetic_external_id():
    p = publisher_mod.DryRunPublisher()
    res = p.publish(_output(), "instagram")
    assert res["status"] == "dry_run"
    assert res["external_id"].startswith("dryrun-")


def test_telegram_handoff_unconfigured_cannot_publish():
    p = publisher_mod.TelegramHandoffPublisher(bot_token=None, chat_id=None)
    assert p.can_publish(_output(), "instagram") is False


def test_telegram_handoff_skipped_when_unconfigured():
    p = publisher_mod.TelegramHandoffPublisher(bot_token=None, chat_id=None)
    res = p.publish(_output(), "instagram")
    assert res["status"] == "skipped"


def test_dispatch_prefers_named_publisher():
    publisher_mod.register(publisher_mod.DryRunPublisher())
    out = _output(id=42)
    res = publisher_mod.dispatch(out, "instagram", preferred="dry_run")
    assert res["status"] == "dry_run"


def test_dispatch_falls_through_when_preferred_cannot_publish():
    # Force telegram_handoff into a state where it claims it CAN publish,
    # then ensure dispatch returns its result.
    class StubPub:
        name = "stub"
        def can_publish(self, output, platform):
            return True
        def publish(self, output, platform):
            return {"external_id": "stub-1", "url": None, "status": "sent"}

    publisher_mod.register(StubPub())
    res = publisher_mod.dispatch(_output(id=99), "instagram", preferred="stub")
    assert res["status"] == "sent"
    assert res["external_id"] == "stub-1"


def test_dispatch_unknown_publisher_raises():
    with __import__("pytest").raises(KeyError):
        publisher_mod.dispatch(_output(id=99), "instagram", preferred="bogus")


def test_registry_lists_known_publishers():
    names = publisher_mod.list_publishers()
    assert "dry_run" in names
    assert "telegram_handoff" in names