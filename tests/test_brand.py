"""Tests for app/brand.py. Brand profiles + active brand + compose."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import brand, db as app_db, server


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "calypso.db"
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    yield db_path
    # Reset the active brand between tests so each starts clean.
    brand.clear_active_brand()


# ---------- palette parsing ----------

class TestParsePalette:
    def test_empty_inputs(self):
        assert brand.parse_palette(None) == []
        assert brand.parse_palette("") == []
        assert brand.parse_palette("   ") == []

    def test_comma_separated(self):
        assert brand.parse_palette("#ff6a1f, #0a0a0c, #f6efe6") == [
            "#ff6a1f",
            "#0a0a0c",
            "#f6efe6",
        ]

    def test_newline_separated(self):
        assert brand.parse_palette("#ff6a1f\n#0a0a0c\n#f6efe6") == [
            "#ff6a1f",
            "#0a0a0c",
            "#f6efe6",
        ]

    def test_json_input(self):
        assert brand.parse_palette('["#ff6a1f", "#0a0a0c"]') == [
            "#ff6a1f",
            "#0a0a0c",
        ]

    def test_lowercases(self):
        assert brand.parse_palette("#FF6A1F") == ["#ff6a1f"]

    def test_strips_hash(self):
        assert brand.parse_palette("ff6a1f") == ["#ff6a1f"]

    def test_short_hex_expanded(self):
        assert brand.parse_palette("#abc") == ["#aabbcc"]

    def test_skips_invalid(self):
        assert brand.parse_palette("#ff6a1f, not a color, #0a0a0c") == [
            "#ff6a1f",
            "#0a0a0c",
        ]

    def test_dedupes(self):
        assert brand.parse_palette("#ff6a1f, #ff6a1f, #FF6A1F") == ["#ff6a1f"]

    def test_caps_at_12(self):
        raw = ", ".join(f"#{i:06x}" for i in range(20))
        assert len(brand.parse_palette(raw)) == 12

    def test_rgb_function(self):
        assert brand.parse_palette("rgb(255, 106, 31)") == ["#ff6a1f"]


# ---------- CRUD ----------

class TestSaveBrand:
    def test_save_minimal(self, fresh_db):
        b = brand.save_brand("Gachakingdoms")
        assert b["name"] == "Gachakingdoms"
        assert b["palette"] == []
        assert b["tagline"] == ""

    def test_save_full(self, fresh_db):
        b = brand.save_brand(
            "Gachakingdoms",
            tagline="Pull the blade. Rule the realm.",
            audience="Collectors of mythic gacha characters",
            palette=["#ff6a1f", "#0a0a0c", "#f6efe6"],
            typography="Playfair Display for display, Inter for body",
            voice="cinematic, intimate, archival",
            do_examples="tight close-ups\nwarm light",
            dont_examples="bright saturated backgrounds",
            style_guide="Hero always off-axis. Never break the 4th wall.",
        )
        assert b["name"] == "Gachakingdoms"
        assert b["tagline"].startswith("Pull the blade")
        assert b["palette"] == ["#ff6a1f", "#0a0a0c", "#f6efe6"]
        assert b["do_examples"] == "tight close-ups\nwarm light"
        assert b["style_guide"].startswith("Hero always off-axis")

    def test_save_requires_name(self, fresh_db):
        with pytest.raises(ValueError):
            brand.save_brand("")
        with pytest.raises(ValueError):
            brand.save_brand("   ")

    def test_save_updates_existing(self, fresh_db):
        b = brand.save_brand("Old", tagline="old")
        brand.save_brand("New", tagline="new", brand_id=b["id"])
        fetched = brand.get_brand(b["id"])
        assert fetched["name"] == "New"
        assert fetched["tagline"] == "new"

    def test_unique_name(self, fresh_db):
        brand.save_brand("Gachakingdoms")
        with pytest.raises(Exception):
            brand.save_brand("Gachakingdoms")


class TestGetList:
    def test_list_empty(self, fresh_db):
        assert brand.list_brands() == []

    def test_list_orders_by_updated(self, fresh_db):
        a = brand.save_brand("A", tagline="a")
        b = brand.save_brand("B", tagline="b")
        # B was just updated, A is older → B comes first.
        result = brand.list_brands()
        assert result[0]["id"] == b["id"]
        assert result[1]["id"] == a["id"]

    def test_get_unknown(self, fresh_db):
        assert brand.get_brand(9999) is None
        assert brand.get_brand(None) is None
        assert brand.get_brand("") is None


class TestDelete:
    def test_delete_removes(self, fresh_db):
        b = brand.save_brand("Test")
        assert brand.delete_brand(b["id"]) is True
        assert brand.get_brand(b["id"]) is None

    def test_delete_unknown(self, fresh_db):
        assert brand.delete_brand(9999) is False

    def test_delete_clears_active(self, fresh_db):
        b = brand.save_brand("Test")
        brand.set_active_brand(b["id"])
        brand.delete_brand(b["id"])
        assert brand.get_active_brand() is None


# ---------- active brand ----------

class TestActiveBrand:
    def test_no_active_returns_none(self, fresh_db):
        assert brand.get_active_brand() is None

    def test_activate_then_get(self, fresh_db):
        b = brand.save_brand("Test")
        brand.set_active_brand(b["id"])
        active = brand.get_active_brand()
        assert active is not None
        assert active["id"] == b["id"]

    def test_activate_unknown_raises(self, fresh_db):
        with pytest.raises(ValueError):
            brand.set_active_brand(9999)

    def test_clear_active(self, fresh_db):
        b = brand.save_brand("Test")
        brand.set_active_brand(b["id"])
        brand.clear_active_brand()
        assert brand.get_active_brand() is None

    def test_set_active_to_none_clears(self, fresh_db):
        b = brand.save_brand("Test")
        brand.set_active_brand(b["id"])
        brand.set_active_brand(None)
        assert brand.get_active_brand() is None

    def test_only_one_active(self, fresh_db):
        a = brand.save_brand("A")
        b = brand.save_brand("B")
        brand.set_active_brand(a["id"])
        brand.set_active_brand(b["id"])
        assert brand.get_active_brand()["id"] == b["id"]


# ---------- compose ----------

class TestComposePrompt:
    def test_no_brand_returns_prompt_unchanged(self, fresh_db):
        result = brand.compose_prompt("Hero reveals blade")
        assert result == "Hero reveals blade"

    def test_active_brand_injected(self, fresh_db):
        b = brand.save_brand(
            "Gachakingdoms",
            tagline="Pull the blade",
            audience="Collectors",
            palette=["#ff6a1f", "#0a0a0c"],
            voice="cinematic",
            do_examples="warm light",
            dont_examples="stock typography",
        )
        brand.set_active_brand(b["id"])
        result = brand.compose_prompt("Hero reveals blade")
        assert "[BRAND]" in result
        assert "Name: Gachakingdoms" in result
        assert "Tagline: Pull the blade" in result
        assert "Audience: Collectors" in result
        assert "#ff6a1f" in result
        assert "Voice: cinematic" in result
        assert "Do: warm light" in result
        assert "Don't: stock typography" in result
        assert "[PROMPT]" in result
        assert "Hero reveals blade" in result
        assert "[/PROMPT]" in result

    def test_explicit_brand_overrides_active(self, fresh_db):
        active = brand.save_brand("Active")
        explicit = brand.save_brand("Explicit")
        brand.set_active_brand(active["id"])
        result = brand.compose_prompt("Hi", brand_id=explicit["id"])
        assert "Name: Explicit" in result
        assert "Name: Active" not in result

    def test_style_guide_section(self, fresh_db):
        b = brand.save_brand("X", style_guide="Hero always off-axis.")
        brand.set_active_brand(b["id"])
        result = brand.compose_prompt("Hi")
        assert "[STYLE GUIDE]" in result
        assert "Hero always off-axis" in result
        assert "[/STYLE GUIDE]" in result

    def test_omits_empty_sections(self, fresh_db):
        b = brand.save_brand("JustName")
        brand.set_active_brand(b["id"])
        result = brand.compose_prompt("Hi")
        assert "Tagline:" not in result
        assert "Palette:" not in result
        assert "Voice:" not in result
        assert "[STYLE GUIDE]" not in result

    def test_user_prompt_preserved_when_blank(self, fresh_db):
        b = brand.save_brand("X")
        brand.set_active_brand(b["id"])
        result = brand.compose_prompt("   ")
        assert "[PROMPT]" in result
        assert "[/PROMPT]" in result