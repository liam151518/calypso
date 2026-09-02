"""Tests for app/publishers/instagram.py — Instagram publisher via instagrapi.

Run: `python -m pytest tests/test_instagram_publisher.py -v`

These tests don't require a real Instagram account or the instagrapi
package. They mock the instagrapi.Client to verify our wrapper behaves
correctly: can_publish gating, session reuse, photo vs video dispatch,
and the failure paths.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def fake_instagrapi(monkeypatch):
    """Inject a fake `instagrapi` module so `app.publishers.instagram`
    imports cleanly without the real package installed."""
    fake = types.ModuleType("instagrapi")

    class FakeClient:
        last_method: str | None = None

        def login(self, *, username, password):
            self.username = username
            self.password = password
            self.settings = {"fake_session": True}

        def get_settings(self):
            return getattr(self, "settings", {"fake_session": True})

        def load_settings(self, settings):
            self.settings = settings

        def get_timeline_feed(self):
            return {"items": []}

        def photo_upload(self, *, path, caption):
            self.last_method = "photo_upload"
            self.last_path = path
            self.last_caption = caption
            return types.SimpleNamespace(id="1818181818", code="CkXYZabc")

        def video_upload(self, *, path, caption):
            self.last_method = "video_upload"
            self.last_path = path
            self.last_caption = caption
            return types.SimpleNamespace(id="1919191919", code="DlAbCdef")

    fake.Client = FakeClient
    monkeypatch.setitem(sys.modules, "instagrapi", fake)
    # Force a fresh import of the publisher module in case it was already
    # loaded with a broken `from instagrapi import Client`.
    sys.modules.pop("app.publishers.instagram", None)
    mod = importlib.import_module("app.publishers.instagram")
    return mod, fake


@pytest.fixture
def tmp_image(tmp_path: Path) -> Path:
    p = tmp_path / "hero.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    return p


@pytest.fixture
def tmp_video(tmp_path: Path) -> Path:
    p = tmp_path / "hero.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return p


# ---- can_publish --------------------------------------------------------


class TestCanPublish:
    def test_false_without_credentials(self, fake_instagrapi, tmp_image):
        mod, _ = fake_instagrapi
        pub = mod.InstagramPublisher(username=None, password=None,
                                     session_file=str(tmp_image))
        # Force the env to be clear too.
        import os
        os.environ.pop("INSTAGRAM_USERNAME", None)
        os.environ.pop("INSTAGRAM_PASSWORD", None)
        assert pub.can_publish({
            "file_path": str(tmp_image),
        }, "instagram") is False

    def test_false_for_other_platforms(self, fake_instagrapi, tmp_image):
        mod, _ = fake_instagrapi
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(tmp_image))
        assert pub.can_publish({"file_path": str(tmp_image)}, "tiktok") is False

    def test_false_when_file_missing(self, fake_instagrapi):
        mod, _ = fake_instagrapi
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file="/tmp/missing.pickle")
        assert pub.can_publish({"file_path": "/does/not/exist.png"},
                               "instagram") is False

    def test_true_with_credentials_and_file(self, fake_instagrapi, tmp_image):
        mod, _ = fake_instagrapi
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(tmp_image))
        assert pub.can_publish({"file_path": str(tmp_image)},
                               "instagram") is True


# ---- publish ------------------------------------------------------------


class TestPublish:
    def test_photo_upload_returns_external_id(self, fake_instagrapi, tmp_image):
        mod, fake = fake_instagrapi
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(tmp_image.with_suffix(".pickle")))
        result = pub.publish(
            {"id": 1, "file_path": str(tmp_image), "caption": "hello world"},
            "instagram",
        )
        assert result["status"] == "sent"
        assert result["external_id"] == "1818181818"
        assert result["url"] == "https://www.instagram.com/p/CkXYZabc/"
        # The fake client received the call
        client = pub._state.client
        assert client.last_method == "photo_upload"
        assert client.last_path == str(tmp_image)
        assert client.last_caption == "hello world"

    def test_video_upload_dispatch(self, fake_instagrapi, tmp_video):
        mod, fake = fake_instagrapi
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(tmp_video.with_suffix(".pickle")))
        result = pub.publish(
            {"id": 2, "file_path": str(tmp_video), "caption": "vibes"},
            "instagram",
        )
        assert result["status"] == "sent"
        assert result["external_id"] == "1919191919"
        assert pub._state.client.last_method == "video_upload"

    def test_skips_non_instagram_platform(self, fake_instagrapi, tmp_image):
        mod, _ = fake_instagrapi
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(tmp_image))
        result = pub.publish({"id": 3, "file_path": str(tmp_image)}, "tiktok")
        assert result["status"] == "skipped"
        assert pub._state is None  # never tried to log in

    def test_skips_when_file_missing(self, fake_instagrapi):
        mod, _ = fake_instagrapi
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file="/tmp/missing.pickle")
        result = pub.publish({"id": 4, "file_path": "/nope.png"}, "instagram")
        assert result["status"] == "skipped"
        assert result["external_id"] == "instagram-skipped"

    def test_returns_failed_on_instagrapi_exception(self, fake_instagrapi,
                                                    tmp_image, monkeypatch):
        mod, fake = fake_instagrapi

        class BrokenClient(fake.Client):
            def photo_upload(self, *, path, caption):
                raise RuntimeError("challenge_required")

        monkeypatch.setattr(fake, "Client", BrokenClient)
        # Re-import so the publisher picks up the patched Client class
        sys.modules.pop("app.publishers.instagram", None)
        mod = importlib.import_module("app.publishers.instagram")
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(tmp_image.with_suffix(".pickle")))
        result = pub.publish({"id": 5, "file_path": str(tmp_image)}, "instagram")
        assert result["status"] == "failed"
        assert result["external_id"] == "instagram-error"

    def test_session_persisted_to_disk(self, fake_instagrapi, tmp_path):
        mod, fake = fake_instagrapi
        session_path = tmp_path / "session.pickle"
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(session_path))
        # Write a real image so the publish path runs end-to-end.
        image_path = tmp_path / "x.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        result = pub.publish({"id": 6, "file_path": str(image_path)},
                            "instagram")
        assert result["status"] == "sent"
        assert session_path.exists()


# ---- session reuse ------------------------------------------------------


class TestSessionReuse:
    def test_reuses_existing_session_file(self, fake_instagrapi, tmp_path):
        mod, fake = fake_instagrapi
        import pickle

        session_path = tmp_path / "session.pickle"
        session_path.write_bytes(pickle.dumps({"fake_session": "preset"}))

        # No tmp image needed — we just check the client reuses the session.
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(session_path))
        client = pub._ensure_client()
        assert client.settings == {"fake_session": "preset"}

    def test_logs_in_when_session_missing(self, fake_instagrapi, tmp_path):
        mod, fake = fake_instagrapi
        session_path = tmp_path / "fresh.pickle"
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(session_path))
        client = pub._ensure_client()
        assert client.username == "u"
        assert client.password == "p"
        # Login writes the session file
        assert session_path.exists()


# ---- register() ---------------------------------------------------------


class TestRegister:
    def test_register_adds_to_publisher_registry(self, fake_instagrapi,
                                                 tmp_image):
        mod, _ = fake_instagrapi
        from app import publisher as core_pub

        before = set(core_pub.list_publishers())
        mod.register()
        after = set(core_pub.list_publishers())
        assert "instagram" in after
        # Idempotent: registering twice doesn't duplicate
        mod.register()
        assert core_pub.list_publishers().count("instagram") == 1
        # Registry contains the same instance (or a new one with the same name)
        assert "instagram" in core_pub.list_publishers()

    def test_instagrapi_missing_means_runtime_error(self, monkeypatch,
                                                    tmp_image):
        # Remove the fake instagrapi entirely so the real import fails.
        monkeypatch.delitem(sys.modules, "instagrapi", raising=False)
        # Make `from instagrapi import Client` raise
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "instagrapi":
                raise ImportError("simulated missing dependency")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        sys.modules.pop("app.publishers.instagram", None)
        mod = importlib.import_module("app.publishers.instagram")
        pub = mod.InstagramPublisher(username="u", password="p",
                                     session_file=str(tmp_image))
        result = pub.publish({"id": 99, "file_path": str(tmp_image)},
                            "instagram")
        assert result["status"] == "failed"
