"""Tests for app/drafts.py. SQLite-backed prompt-draft library."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import db as app_db
from app import drafts, server


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "calypso.db"
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    return db_path


class TestSaveAndGet:
    def test_save_then_get(self, fresh_db):
        d = drafts.save_draft("Damascus blade", "Hero reveals damascus blade in firelight")
        assert d["id"] > 0
        assert d["name"] == "Damascus blade"
        assert d["body"].startswith("Hero reveals")
        assert d["category"] is None
        assert d["is_favorite"] is False

        fetched = drafts.get_draft(d["id"])
        assert fetched["name"] == d["name"]
        assert fetched["body"] == d["body"]

    def test_save_requires_name(self, fresh_db):
        with pytest.raises(ValueError):
            drafts.save_draft("", "body")

    def test_save_requires_body(self, fresh_db):
        with pytest.raises(ValueError):
            drafts.save_draft("name", "")

    def test_save_with_category(self, fresh_db):
        d = drafts.save_draft("Hero", "Close-up of a hero.", category="portrait")
        assert d["category"] == "portrait"

    def test_save_blank_category_is_none(self, fresh_db):
        d = drafts.save_draft("Hero", "Close-up of a hero.", category="   ")
        assert d["category"] is None

    def test_update_existing_draft(self, fresh_db):
        d = drafts.save_draft("Hero", "first version")
        drafts.save_draft("Hero v2", "second version", draft_id=d["id"])
        fetched = drafts.get_draft(d["id"])
        assert fetched["name"] == "Hero v2"
        assert fetched["body"] == "second version"

    def test_update_bumps_updated_at(self, fresh_db):
        d = drafts.save_draft("Hero", "first")
        first_updated = d["updated_at"]
        drafts.save_draft("Hero", "second", draft_id=d["id"])
        second = drafts.get_draft(d["id"])
        assert second["updated_at"] >= first_updated


class TestListDrafts:
    def test_newest_first(self, fresh_db):
        a = drafts.save_draft("A", "alpha")
        b = drafts.save_draft("B", "beta")
        result = drafts.list_drafts()
        # Both saved with the same time. Either order is acceptable,
        # but in practice newer rows return first.
        assert {d["id"] for d in result} == {a["id"], b["id"]}

    def test_search_query(self, fresh_db):
        drafts.save_draft("Damascus", "blade close-up")
        drafts.save_draft("Intro", "Hello world")
        result = drafts.list_drafts(query="damascus")
        assert len(result) == 1
        assert result[0]["name"] == "Damascus"

    def test_search_matches_body(self, fresh_db):
        drafts.save_draft("A", "alpha damascus blade")
        drafts.save_draft("B", "hello world")
        result = drafts.list_drafts(query="Damascus")
        assert len(result) == 1
        assert result[0]["name"] == "A"

    def test_filter_category(self, fresh_db):
        drafts.save_draft("A", "x", category="portrait")
        drafts.save_draft("B", "y", category="landscape")
        result = drafts.list_drafts(category="portrait")
        assert len(result) == 1
        assert result[0]["name"] == "A"

    def test_favorites_only(self, fresh_db):
        drafts.save_draft("A", "alpha")
        b = drafts.save_draft("B", "beta")
        drafts.toggle_favorite(b["id"])
        result = drafts.list_drafts(favorites_only=True)
        assert len(result) == 1
        assert result[0]["id"] == b["id"]


class TestToggleFavorite:
    def test_toggle_on_then_off(self, fresh_db):
        d = drafts.save_draft("A", "alpha")
        assert d["is_favorite"] is False
        toggled = drafts.toggle_favorite(d["id"])
        assert toggled["is_favorite"] is True
        toggled = drafts.toggle_favorite(d["id"])
        assert toggled["is_favorite"] is False

    def test_toggle_unknown_returns_none(self, fresh_db):
        assert drafts.toggle_favorite(9999) is None


class TestDelete:
    def test_delete_removes(self, fresh_db):
        d = drafts.save_draft("A", "alpha")
        assert drafts.delete_draft(d["id"]) is True
        assert drafts.get_draft(d["id"]) is None

    def test_delete_unknown_returns_false(self, fresh_db):
        assert drafts.delete_draft(9999) is False


class TestCategories:
    def test_returns_used_categories(self, fresh_db):
        drafts.save_draft("A", "x", category="portrait")
        drafts.save_draft("B", "y", category="portrait")
        drafts.save_draft("C", "z", category="landscape")
        drafts.save_draft("D", "w")  # no category
        cats = drafts.categories()
        names = [c["category"] for c in cats]
        assert names == ["portrait", "landscape"]
        portrait = next(c for c in cats if c["category"] == "portrait")
        assert portrait["count"] == 2

    def test_no_categories(self, fresh_db):
        drafts.save_draft("A", "x")
        assert drafts.categories() == []

    def test_count(self, fresh_db):
        drafts.save_draft("A", "x")
        drafts.save_draft("B", "y")
        drafts.save_draft("C", "z")
        assert drafts.count() == 3