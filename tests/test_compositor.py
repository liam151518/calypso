"""Tests for app/compositor.py (Phase A). End-to-end minimal render."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from PIL import Image

from app import compositor as comp_mod
from app import db as app_db, products as prod_mod, server
from app import templates as tpl_mod


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "calypso.db"
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    yield db_path


@pytest.fixture
def tee_with_fake_cutout(fresh_db, tmp_path: Path):
    pid = prod_mod.create_product(brand_id=None, name="Test Tee", price=899)
    sample = tmp_path / "tee.png"
    Image.new("RGBA", (200, 200), (200, 60, 80, 255)).save(sample)
    prod_mod.update_product(pid, {"image_path": str(sample)})
    # Stub rembg in a way that doesn't require the binary model.
    import types
    fake = types.ModuleType("rembg")
    fake.remove = lambda img: img.copy()
    sys.modules["rembg"] = fake
    import importlib
    importlib.reload(prod_mod)
    return pid


@pytest.fixture
def minimal_template(fresh_db):
    tpl_mod.load_builtins()
    items = tpl_mod.list_templates(include_builtin=True)
    return next(t for t in items if t["name"] == "Minimal Launch")


# ---------- happy path ----------

class TestRenderMinimalLaunch:
    def test_renders_to_outputs_images(
        self, fresh_db, minimal_template, tee_with_fake_cutout, tmp_path,
        monkeypatch,
    ):
        # Redirect outputs dir into the tmp_path so we don't pollute the repo.
        images_dir = tmp_path / "images"
        cache_dir = tmp_path / "cache"
        images_dir.mkdir()
        cache_dir.mkdir()
        monkeypatch.setattr(comp_mod, "IMAGES_DIR", images_dir)
        monkeypatch.setattr(comp_mod, "CACHE_DIR", cache_dir)

        res = comp_mod.render(
            template_id=int(minimal_template["id"]),
            product_id=tee_with_fake_cutout,
            filter_name="minimal",
            cache_hit_only=True,  # don't actually call Fal for the background
        )
        assert res.output_id > 0
        assert res.file_path.endswith(".jpg")
        out = Path(res.file_path)
        assert out.exists()
        assert out.stat().st_size > 1000  # actual image bytes
        # Outputs row recorded.
        from app import db as app_db
        row = app_db.get_conn().execute(
            "SELECT * FROM outputs WHERE id = ?", (res.output_id,)
        ).fetchone()
        assert row is not None
        assert row["filter_applied"] == "minimal"
        assert row["status"] == "draft"

    def test_no_product_still_renders(
        self, fresh_db, minimal_template, tmp_path, monkeypatch,
    ):
        images_dir = tmp_path / "images"
        cache_dir = tmp_path / "cache"
        images_dir.mkdir()
        cache_dir.mkdir()
        monkeypatch.setattr(comp_mod, "IMAGES_DIR", images_dir)
        monkeypatch.setattr(comp_mod, "CACHE_DIR", cache_dir)
        res = comp_mod.render(
            template_id=int(minimal_template["id"]),
            cache_hit_only=True,
        )
        assert Path(res.file_path).exists()


# ---------- aspect ratio override ----------

class TestAspectRatioOverride:
    def test_requested_aspect_ratio_resizes_canvas(
        self, fresh_db, minimal_template, tmp_path, monkeypatch,
    ):
        images_dir = tmp_path / "images"
        cache_dir = tmp_path / "cache"
        images_dir.mkdir()
        cache_dir.mkdir()
        monkeypatch.setattr(comp_mod, "IMAGES_DIR", images_dir)
        monkeypatch.setattr(comp_mod, "CACHE_DIR", cache_dir)
        res = comp_mod.render(
            template_id=int(minimal_template["id"]),
            cache_hit_only=True,
            aspect_ratio="1:1",
        )
        img = Image.open(res.file_path)
        assert img.size[0] == img.size[1]


# ---------- batch ----------

class TestRenderBatch:
    def test_render_batch_produces_one_per_product(
        self, fresh_db, minimal_template, tmp_path, monkeypatch,
    ):
        # Three products.
        ids = []
        for nm in ("A", "B", "C"):
            pid = prod_mod.create_product(brand_id=None, name=nm)
            sample = tmp_path / f"{nm}.png"
            Image.new("RGBA", (200, 200), (180, 60, 80, 255)).save(sample)
            prod_mod.update_product(pid, {"image_path": str(sample)})
            ids.append(pid)

        images_dir = tmp_path / "images"
        cache_dir = tmp_path / "cache"
        images_dir.mkdir()
        cache_dir.mkdir()
        monkeypatch.setattr(comp_mod, "IMAGES_DIR", images_dir)
        monkeypatch.setattr(comp_mod, "CACHE_DIR", cache_dir)
        results = comp_mod.render_batch(
            template_id=int(minimal_template["id"]),
            product_ids=ids,
            cache_hit_only=True,
            max_workers=1,
        )
        assert len(results) == 3
        for r in results:
            assert Path(r.file_path).exists()


# ---------- filters integration ----------

class TestFiltersIntegration:
    def test_each_builtin_filter_runs(self, fresh_db, minimal_template, tmp_path, monkeypatch):
        images_dir = tmp_path / "images"
        cache_dir = tmp_path / "cache"
        images_dir.mkdir()
        cache_dir.mkdir()
        monkeypatch.setattr(comp_mod, "IMAGES_DIR", images_dir)
        monkeypatch.setattr(comp_mod, "CACHE_DIR", cache_dir)
        for fn in ("moody", "bright", "vintage", "minimal", "neon"):
            res = comp_mod.render(
                template_id=int(minimal_template["id"]),
                cache_hit_only=True,
                filter_name=fn,
            )
            assert Path(res.file_path).exists()