"""Tests for app/products.py (Phase A). Product CRUD + CSV import + cutout."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app import brand, db as app_db, products as prod_mod, server


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "calypso.db"
    monkeypatch.setattr(server, "REFERENCES_UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    app_db.reset_for_tests(db_path)
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    yield db_path


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    p = tmp_path / "tee.png"
    Image.new("RGBA", (200, 200), (200, 60, 80, 255)).save(p)
    return p


# ---------- CRUD ----------

class TestCRUD:
    def test_create_minimal(self, fresh_db):
        pid = prod_mod.create_product(brand_id=None, name="Tee")
        assert isinstance(pid, int)
        p = prod_mod.get_product(pid)
        assert p is not None
        assert p["name"] == "Tee"
        assert p["tags"] == []

    def test_create_with_all_fields(self, fresh_db):
        pid = prod_mod.create_product(
            brand_id=None,
            name="Sneaker",
            price=1200,
            category="footwear",
            collection="drop1",
            description="Limited drop",
            image_path="brand/screenshots/x.png",
            tags=["streetwear", "drop"],
            launch_date="2026-09-01",
        )
        p = prod_mod.get_product(pid)
        assert p["price"] == 1200
        assert p["category"] == "footwear"
        assert "streetwear" in p["tags"]
        assert p["launch_date"] == "2026-09-01"

    def test_create_rejects_blank_name(self, fresh_db):
        with pytest.raises(ValueError, match="name is required"):
            prod_mod.create_product(brand_id=None, name="")

    def test_update_patches_fields(self, fresh_db):
        pid = prod_mod.create_product(brand_id=None, name="Tee", price=899)
        prod_mod.update_product(pid, {"price": 999, "tags": ["v2"]})
        p = prod_mod.get_product(pid)
        assert p["price"] == 999
        assert "v2" in p["tags"]

    def test_update_missing_returns_false(self, fresh_db):
        assert prod_mod.update_product(99999, {"name": "x"}) is False

    def test_delete_returns_true_then_false(self, fresh_db):
        pid = prod_mod.create_product(brand_id=None, name="Tee")
        assert prod_mod.delete_product(pid)
        assert prod_mod.delete_product(pid) is False

    def test_get_missing_returns_none(self, fresh_db):
        assert prod_mod.get_product(99999) is None


# ---------- variants ----------

class TestVariants:
    def test_add_and_list_variants(self, fresh_db):
        pid = prod_mod.create_product(brand_id=None, name="Tee")
        prod_mod.add_variant(pid, variant_name="Red", sku="T-RED", price_delta=0)
        prod_mod.add_variant(pid, variant_name="Blue", sku="T-BLU", price_delta=50)
        variants = prod_mod.list_variants(pid)
        assert {v["variant_name"] for v in variants} == {"Red", "Blue"}


# ---------- listing ----------

class TestList:
    def test_list_returns_all(self, fresh_db):
        prod_mod.create_product(brand_id=None, name="A")
        prod_mod.create_product(brand_id=None, name="B")
        prod_mod.create_product(brand_id=None, name="C")
        names = {p["name"] for p in prod_mod.list_products()}
        assert {"A", "B", "C"} <= names

    def test_list_filters_by_category(self, fresh_db):
        prod_mod.create_product(brand_id=None, name="A", category="apparel")
        prod_mod.create_product(brand_id=None, name="B", category="home")
        only_apparel = prod_mod.list_products(category="apparel")
        assert {p["name"] for p in only_apparel} == {"A"}

    def test_list_filters_by_brand(self, fresh_db):
        b = brand.save_brand(name="Z")
        prod_mod.create_product(brand_id=b["id"], name="Branded")
        prod_mod.create_product(brand_id=None, name="Unbranded")
        items = prod_mod.list_products(brand_id=b["id"])
        assert {p["name"] for p in items} == {"Branded"}

    def test_list_filters_by_tag(self, fresh_db):
        prod_mod.create_product(brand_id=None, name="A", tags=["vip"])
        prod_mod.create_product(brand_id=None, name="B", tags=["regular"])
        vip = prod_mod.list_products(tag="vip")
        assert {p["name"] for p in vip} == {"A"}


# ---------- CSV import ----------

class TestCSVImport:
    def test_import_basic_rows(self, fresh_db):
        csv_text = (
            "name,price,category,description,image_path,tags\n"
            "Sneaker,1200,footwear,Light sneaker,brand/screenshots/x.png,footwear|drop\n"
            "Mug,250,home,Ceramic mug,brand/screenshots/y.png,home\n"
        )
        res = prod_mod.import_csv(None, csv_text)
        assert res["imported"] == 2
        assert res["skipped"] == 0
        items = prod_mod.list_products()
        names = {p["name"] for p in items}
        assert {"Sneaker", "Mug"} <= names

    def test_import_skips_invalid_rows(self, fresh_db):
        rows = [
            {"name": "Valid", "price": "100", "category": "x"},
            {"name": "", "price": "100"},  # missing name
            {"name": "Bad price", "price": "not-a-number"},  # bad price
        ]
        res = prod_mod.bulk_import(None, rows)
        assert res["imported"] == 1
        assert res["skipped"] == 2
        assert len(res["errors"]) == 2

    def test_pipe_separated_tags_parsed(self, fresh_db):
        csv_text = "name,price,tags\nShirt,500,a|b|c\n"
        prod_mod.import_csv(None, csv_text)
        items = prod_mod.list_products()
        assert items[0]["tags"] == ["a", "b", "c"]


# ---------- cutout ----------

class TestCutout:
    def test_get_cutout_creates_cache(self, fresh_db, sample_image):
        pid = prod_mod.create_product(
            brand_id=None, name="Tee", image_path=str(sample_image),
        )
        # Stub out rembg so the test is hermetic.
        import sys
        class _FakeRembg:
            @staticmethod
            def remove(img):
                out = img.copy()
                # Make alpha zero everywhere (test stub).
                out.putalpha(0)
                return out
        sys.modules["rembg"] = _FakeRembg()
        # Re-import products module so it picks up the fake.
        import importlib
        importlib.reload(prod_mod)
        path = prod_mod.get_cutout(pid)
        assert path.endswith(f"{pid}.png")
        assert Path(path).exists()
        # Cached on second call.
        assert prod_mod.get_cutout(pid) == path

    def test_get_cutout_missing_image_raises(self, fresh_db):
        pid = prod_mod.create_product(
            brand_id=None, name="Tee", image_path="/does/not/exist.png",
        )
        with pytest.raises((FileNotFoundError, ValueError)):
            prod_mod.get_cutout(pid)

    def test_get_cutout_missing_product_raises(self, fresh_db):
        with pytest.raises(ValueError, match="no product"):
            prod_mod.get_cutout(99999)