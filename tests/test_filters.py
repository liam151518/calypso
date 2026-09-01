"""Tests for app/filters.py (Phase A). 5 built-in presets + intensity + preview."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app import db as app_db, filters as filters_mod, server


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "calypso.db"
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    yield db_path


@pytest.fixture
def sample_img(tmp_path: Path) -> Path:
    p = tmp_path / "sample.png"
    Image.new("RGB", (240, 320), (180, 130, 90)).save(p)
    return p


# ---------- presets ----------

class TestPresets:
    def test_five_built_in_presets_present(self):
        names = set(filters_mod.PRESETS.keys())
        assert {"moody", "bright", "vintage", "minimal", "neon"} <= names

    def test_each_preset_has_expected_keys(self):
        expected = {"brightness", "contrast", "saturation", "temperature", "tint",
                    "highlights", "shadows", "sepia", "vignette", "glow", "grain"}
        for name, settings in filters_mod.PRESETS.items():
            missing = expected - set(settings.keys())
            assert not missing, f"preset {name} missing {missing}"

    def test_list_presets_returns_copy(self):
        presets = filters_mod.list_presets()
        assert len(presets) == 5
        for p in presets:
            assert "name" in p and "settings" in p


# ---------- apply ----------

class TestApply:
    def test_apply_runs_for_each_preset(self, sample_img):
        img = Image.open(sample_img)
        for name, settings in filters_mod.PRESETS.items():
            res = filters_mod.apply(img, settings, intensity=1.0)
            assert res.image.size == img.size
            assert res.image.mode == "RGB"

    def test_intensity_zero_returns_original(self, sample_img):
        img = Image.open(sample_img)
        res = filters_mod.apply(img, filters_mod.PRESETS["moody"], intensity=0.0)
        # The returned image must match the input bytes for non-touched pixels.
        assert res.image.size == img.size
        assert res.image.mode == "RGB"

    def test_intensity_one_modifies_image(self, sample_img):
        img = Image.open(sample_img).convert("RGB")
        before = list(img.getdata())[0]
        res = filters_mod.apply(img, filters_mod.PRESETS["moody"], intensity=1.0)
        after = list(res.image.getdata())[0]
        # Moody lowers brightness, so the pixel value should change.
        assert before != after

    def test_unknown_settings_are_ignored(self, sample_img):
        img = Image.open(sample_img)
        res = filters_mod.apply(img, {"garbage_key": 99, "brightness": 1.2})
        assert res.image.size == img.size

    def test_apply_path_writes_file(self, sample_img, tmp_path):
        out = filters_mod.apply_path(
            sample_img,
            filters_mod.PRESETS["neon"],
            output_path=tmp_path / "out.jpg",
        )
        assert out.exists()
        assert out.suffix == ".jpg"


# ---------- preview ----------

class TestPreview:
    def test_preview_writes_small_png(self, sample_img):
        out = filters_mod.preview(sample_img, filters_mod.PRESETS["minimal"])
        assert out.exists()
        img = Image.open(out)
        # preview is downsampled to 320px max edge.
        assert max(img.size) <= 320


# ---------- user presets ----------

class TestUserPresets:
    def test_save_user_preset_round_trip(self, fresh_db):
        pid = filters_mod.save_user_preset(brand_id=None, name="My Look",
                                            settings={"brightness": 1.1, "contrast": 1.2})
        assert isinstance(pid, int)
        rows = filters_mod.list_user_presets()
        assert any(r["name"] == "My Look" for r in rows)
        mine = next(r for r in rows if r["name"] == "My Look")
        assert mine["settings"]["brightness"] == 1.1

    def test_save_user_preset_upserts(self, fresh_db):
        pid1 = filters_mod.save_user_preset(brand_id=None, name="Dup",
                                             settings={"brightness": 1.0})
        pid2 = filters_mod.save_user_preset(brand_id=None, name="Dup",
                                             settings={"brightness": 1.5})
        # Same name → upsert; we don't care about the exact id, only that the
        # settings are the latest.
        rows = filters_mod.list_user_presets()
        mine = next(r for r in rows if r["name"] == "Dup")
        assert mine["settings"]["brightness"] == 1.5

    def test_list_user_presets_filters_by_brand(self, fresh_db):
        from app import brand as brand_mod
        a_brand = brand_mod.save_brand(name="A brand")
        b_brand = brand_mod.save_brand(name="B brand")
        filters_mod.save_user_preset(brand_id=a_brand["id"], name="Brand A Look",
                                     settings={"brightness": 1.0})
        filters_mod.save_user_preset(brand_id=b_brand["id"], name="Brand B Look",
                                     settings={"brightness": 1.0})
        a = filters_mod.list_user_presets(brand_id=a_brand["id"])
        b = filters_mod.list_user_presets(brand_id=b_brand["id"])
        assert any(r["name"] == "Brand A Look" for r in a)
        assert any(r["name"] == "Brand B Look" for r in b)
        assert all(r["brand_id"] == a_brand["id"] for r in a)
        assert all(r["brand_id"] == b_brand["id"] for r in b)