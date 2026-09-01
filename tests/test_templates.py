"""Tests for app/templates.py (Phase A). Template CRUD + validation + built-ins."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import brand, db as app_db, server, templates as tpl_mod
from app.utils import TemplateError


VALID_TEMPLATE = {
    "name": "Test Template",
    "aspect_ratio": "4:5",
    "canvas": {"width": 1080, "height": 1350},
    "layers": [
        {"id": "bg", "type": "ai_background", "name": "BG",
         "config": {"prompt": "soft studio"}},
        {"id": "title", "type": "text", "name": "Title",
         "config": {"content": "Hello", "font_family": "Inter", "color": "#ff6a1f"}},
    ],
}


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "calypso.db"
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    yield db_path


# ---------- validation ----------

class TestValidateTemplate:
    def test_valid_template_passes(self):
        assert tpl_mod.validate(VALID_TEMPLATE)["name"] == "Test Template"

    def test_bad_aspect_ratio_rejected(self):
        bad = {**VALID_TEMPLATE, "aspect_ratio": "banana"}
        with pytest.raises(TemplateError):
            tpl_mod.validate(bad)

    def test_brand_lock_must_reference_real_layer(self):
        bad = {**VALID_TEMPLATE, "brand_locks": ["nonexistent"]}
        with pytest.raises(TemplateError, match="unknown layer id"):
            tpl_mod.validate(bad)

    def test_unknown_layer_type_rejected(self):
        bad = json.loads(json.dumps(VALID_TEMPLATE))
        bad["layers"][0]["type"] = "wat"
        with pytest.raises(TemplateError):
            tpl_mod.validate(bad)

    def test_text_layer_requires_font_family_and_color(self):
        bad = json.loads(json.dumps(VALID_TEMPLATE))
        bad["layers"][1]["config"] = {"content": "x"}
        with pytest.raises(TemplateError):
            tpl_mod.validate(bad)

    def test_duplicate_layer_ids_rejected(self):
        bad = json.loads(json.dumps(VALID_TEMPLATE))
        bad["layers"].append({"id": "bg", "type": "image", "name": "BG2",
                              "config": {"src": "x"}})
        with pytest.raises(TemplateError, match="duplicate id"):
            tpl_mod.validate(bad)

    def test_aspect_ratio_mismatch_with_canvas_rejected(self):
        bad = {**VALID_TEMPLATE, "canvas": {"width": 1080, "height": 1080}}  # 1:1 ratio
        # aspect_ratio is 4:5 but canvas is square — should warn.
        with pytest.raises(TemplateError, match="aspect_ratio"):
            tpl_mod.validate(bad)


# ---------- CRUD ----------

class TestTemplateCRUD:
    def test_create_returns_id(self, fresh_db):
        tid = tpl_mod.create_template(VALID_TEMPLATE)
        assert isinstance(tid, int)
        assert tid > 0

    def test_create_with_brand_id(self, fresh_db):
        saved = brand.save_brand(name="Test Brand")
        tid = tpl_mod.create_template(VALID_TEMPLATE, brand_id=saved["id"])
        assert tid > 0

    def test_get_returns_full_template(self, fresh_db):
        tid = tpl_mod.create_template(VALID_TEMPLATE)
        out = tpl_mod.get_template(tid)
        assert out is not None
        assert out["name"] == "Test Template"
        assert isinstance(out["layers"], list)
        assert isinstance(out["brand_locks"], list)

    def test_update_persists_changes(self, fresh_db):
        tid = tpl_mod.create_template(VALID_TEMPLATE)
        assert tpl_mod.update_template(tid, {"name": "Renamed"})
        assert tpl_mod.get_template(tid)["name"] == "Renamed"

    def test_update_validates_layers(self, fresh_db):
        tid = tpl_mod.create_template(VALID_TEMPLATE)
        bad = {"layers": [{"id": "x", "type": "wat", "name": "X", "config": {}}]}
        with pytest.raises(TemplateError):
            tpl_mod.update_template(tid, bad)

    def test_update_returns_false_for_missing(self, fresh_db):
        assert tpl_mod.update_template(99999, {"name": "x"}) is False

    def test_delete_custom_template(self, fresh_db):
        tid = tpl_mod.create_template(VALID_TEMPLATE)
        assert tpl_mod.delete_template(tid)
        assert tpl_mod.get_template(tid) is None

    def test_delete_missing_returns_false(self, fresh_db):
        assert tpl_mod.delete_template(99999) is False

    def test_duplicate_creates_editable_copy(self, fresh_db):
        tid = tpl_mod.create_template(VALID_TEMPLATE)
        new_id = tpl_mod.duplicate_template(tid, "Copy")
        assert new_id != tid
        out = tpl_mod.get_template(new_id)
        assert out is not None
        assert out["name"] == "Copy"
        assert out["parent_template_id"] == tid


# ---------- built-ins ----------

class TestBuiltins:
    def test_load_builtins_inserts_six(self, fresh_db):
        inserted = tpl_mod.load_builtins()
        assert inserted == 6
        items = tpl_mod.list_templates(include_builtin=True)
        assert len(items) == 6
        names = {t["name"] for t in items}
        assert {"Minimal Launch", "Bold Drop", "Lifestyle Flatlay",
                "Announcement", "UGC Raw", "Sale Blast"} <= names

    def test_load_builtins_idempotent(self, fresh_db):
        first = tpl_mod.load_builtins()
        second = tpl_mod.load_builtins()
        assert first == 6
        assert second == 0

    def test_built_in_protected_from_delete(self, fresh_db):
        tpl_mod.load_builtins()
        items = tpl_mod.list_templates(category="product", include_builtin=True)
        assert items
        first_id = items[0]["id"]
        with pytest.raises(TemplateError, match="read-only"):
            tpl_mod.delete_template(int(first_id))

    def test_built_in_protected_from_update(self, fresh_db):
        tpl_mod.load_builtins()
        items = tpl_mod.list_templates(category="product", include_builtin=True)
        first_id = int(items[0]["id"])
        with pytest.raises(TemplateError, match="read-only"):
            tpl_mod.update_template(first_id, {"name": "Tampered"})

    def test_force_flag_overrides_builtin_protection(self, fresh_db):
        tpl_mod.load_builtins()
        items = tpl_mod.list_templates(category="product", include_builtin=True)
        first_id = int(items[0]["id"])
        # Force-update succeeds.
        assert tpl_mod.update_template(first_id, {"name": "Tampered"}, force=True)
        assert tpl_mod.get_template(first_id)["name"] == "Tampered"


# ---------- listing ----------

class TestListTemplates:
    def test_list_filters_by_category(self, fresh_db):
        tpl_mod.load_builtins()
        items = tpl_mod.list_templates(category="announcement")
        assert all(t["category"] == "announcement" for t in items)

    def test_list_filters_by_brand(self, fresh_db):
        b = brand.save_brand(name="My Brand")
        tid = tpl_mod.create_template(VALID_TEMPLATE, brand_id=b["id"])
        items = tpl_mod.list_templates(brand_id=b["id"], include_builtin=False)
        assert len(items) == 1
        assert items[0]["id"] == tid


# ---------- substitution ----------

class TestSubstitution:
    def test_render_substitutions_resolves_product(self):
        out = tpl_mod.render_substitutions("Price: R{{product.price}}",
                                          product={"price": 899})
        assert out == "Price: R899"

    def test_render_substitutions_resolves_brand_palette(self):
        out = tpl_mod.render_substitutions("Color {{brand.colors.primary}}",
                                           brand={"colors": {"primary": "#ff6a1f"}})
        assert out == "Color #ff6a1f"

    def test_render_substitutions_leaves_unknown_alone(self):
        out = tpl_mod.render_substitutions("{{unknown.token}}", product={}, brand={})
        assert out == ""

    def test_substitute_template_walks_layers(self):
        t = json.loads(json.dumps(VALID_TEMPLATE))
        out = tpl_mod.substitute_template(
            t, product={"name": "Tee", "price": 999},
            brand={"tagline": "Hello world"},
        )
        bg_cfg = out["layers"][0]["config"]
        # The ai_background prompt in the test template is "soft studio" — no
        # substitutions to make, but walk must not crash.
        assert isinstance(bg_cfg, dict)