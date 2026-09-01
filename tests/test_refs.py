"""Tests for app/refs.py. SQLite-backed reference library."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import db as app_db
from app import refs, server


# ---------- fixtures ----------

@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    """Fresh SQLite DB at tmp_path + a fresh upload dir."""
    db_path = tmp_path / "calypso.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", upload_dir)
    # Reset the per-thread connection cache so it picks up the new path.
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    return db_path, upload_dir


def _write_ref(upload_dir: Path, name: str, body: bytes = b"x") -> Path:
    p = upload_dir / name
    p.write_bytes(body)
    return p


# ---------- normalisation ----------

class TestNormaliseTag:
    def test_lowercases(self):
        assert refs.normalise_tag("Character") == "character"

    def test_replaces_spaces(self):
        assert refs.normalise_tag("product angle") == "product-angle"
        assert refs.normalise_tag("Product Angle") == "product-angle"

    def test_strips_punctuation(self):
        assert refs.normalise_tag("Hello, World!") == "hello-world"

    def test_drops_unicode_combining(self):
        # é -> e
        assert refs.normalise_tag("café") == "cafe"

    def test_empty_returns_empty(self):
        assert refs.normalise_tag("") == ""
        assert refs.normalise_tag("!!!") == ""

    def test_truncates_long_tags(self):
        long = "a" * 50
        assert len(refs.normalise_tag(long)) == 32

    def test_dedupes_dashes(self):
        assert refs.normalise_tag("a -- b") == "a-b"


# ---------- listing + auto-register ----------

class TestListRefs:
    def test_empty_upload_dir_returns_empty_list(self, fresh_db):
        _, upload_dir = fresh_db
        assert refs.list_refs() == []

    def test_files_appear_with_no_tags(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        _write_ref(upload_dir, "b.mp4")
        result = refs.list_refs()
        assert len(result) == 2
        ids = {r["id"] for r in result}
        assert ids == {"a.png", "b.mp4"}
        for r in result:
            assert r["tags"] == []
            assert r["rel_url"].startswith("/references/file/")
            assert r["size_kb"] >= 0

    def test_filter_by_tag(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        _write_ref(upload_dir, "b.png")
        _write_ref(upload_dir, "c.mp4")
        refs.set_tags("a.png", ["character"])
        refs.set_tags("b.png", ["character", "hero"])
        result = refs.list_refs(tag="character")
        ids = {r["id"] for r in result}
        assert ids == {"a.png", "b.png"}

    def test_unknown_tag_filter_returns_empty(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        assert refs.list_refs(tag="does-not-exist") == []

    def test_file_outside_upload_dir_is_ignored(self, fresh_db, tmp_path):
        _, _upload_dir = fresh_db
        # A file that exists on disk but isn't in the upload dir must not show up.
        (tmp_path / "outside.png").write_bytes(b"x")
        assert refs.list_refs() == []


# ---------- tag CRUD ----------

class TestTags:
    def test_set_tags_replaces(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        refs.set_tags("a.png", ["character", "hero"])
        assert sorted(refs.get_tags("a.png")) == ["character", "hero"]
        refs.set_tags("a.png", ["background"])
        assert refs.get_tags("a.png") == ["background"]

    def test_set_tags_normalises(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        refs.set_tags("a.png", ["Product Angle", "HERO!"])
        assert sorted(refs.get_tags("a.png")) == ["hero", "product-angle"]

    def test_set_tags_dedupes(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        refs.set_tags("a.png", ["character", "Character", "CHARACTER "])
        assert refs.get_tags("a.png") == ["character"]

    def test_set_tags_empty_clears(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        refs.set_tags("a.png", ["character"])
        refs.set_tags("a.png", [])
        assert refs.get_tags("a.png") == []

    def test_add_tag(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        refs.add_tag_to("a.png", "character")
        refs.add_tag_to("a.png", "hero")
        assert sorted(refs.get_tags("a.png")) == ["character", "hero"]
        # Adding an existing tag is a no-op (no duplicate created).
        refs.add_tag_to("a.png", "character")
        tags = refs.get_tags("a.png")
        assert sorted(tags) == ["character", "hero"]
        assert len(tags) == 2  # no third duplicate

    def test_remove_tag(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        refs.set_tags("a.png", ["character", "hero"])
        refs.remove_tag_from("a.png", "character")
        assert refs.get_tags("a.png") == ["hero"]

    def test_all_tags_with_counts(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        _write_ref(upload_dir, "b.png")
        _write_ref(upload_dir, "c.mp4")
        refs.set_tags("a.png", ["character", "hero"])
        refs.set_tags("b.png", ["character"])
        refs.set_tags("c.mp4", [])
        tags = refs.all_tags()
        # Tags with no references are excluded (because of the LEFT JOIN? actually they appear with count 0)
        # Find the character row:
        char = next(t for t in tags if t["name"] == "character")
        assert char["count"] == 2
        hero = next(t for t in tags if t["name"] == "hero")
        assert hero["count"] == 1

    def test_delete_tag_everywhere(self, fresh_db):
        _, upload_dir = fresh_db
        _write_ref(upload_dir, "a.png")
        refs.set_tags("a.png", ["character"])
        refs.delete_tag_everywhere("character")
        assert refs.get_tags("a.png") == []
        assert refs.all_tags() == []


# ---------- path resolution ----------

class TestResolveToPath:
    def test_returns_path_for_existing(self, fresh_db):
        _, upload_dir = fresh_db
        p = _write_ref(upload_dir, "real.png")
        assert refs.resolve_to_path("real.png") == p.resolve()

    def test_returns_none_for_missing(self, fresh_db):
        _, _ = fresh_db
        assert refs.resolve_to_path("missing.png") is None

    def test_blocks_traversal(self, fresh_db):
        _, _ = fresh_db
        assert refs.resolve_to_path("../etc/passwd") is None
        assert refs.resolve_to_path("..\\windows\\system") is None
        assert refs.resolve_to_path("/abs/path") is None
        assert refs.resolve_to_path("subdir/file.png") is None
        assert refs.resolve_to_path("") is None

    def test_blocks_symlink_escape(self, fresh_db, tmp_path):
        """A symlink that escapes the upload dir must be rejected."""
        _, upload_dir = fresh_db
        outside = tmp_path / "outside.png"
        outside.write_bytes(b"x")
        link = upload_dir / "linked.png"
        link.symlink_to(outside)
        # The file resolves outside the upload dir, so resolve_to_path returns None.
        assert refs.resolve_to_path("linked.png") is None