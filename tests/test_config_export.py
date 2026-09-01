"""Phase G.3 — config import/export tests."""

from __future__ import annotations

import pytest

from app import brand as brand_mod
from app import config_io as config_io_mod
from app import db as app_db
from app import products as products_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "cfg.db"
    monkeypatch.setattr(app_db, "DB_PATH", db)
    app_db.reset_for_tests(db)
    app_db.init_db(db)
    yield db


def test_export_round_trip(fresh_db):
    bid = brand_mod.save_brand(name="ExportBrand", voice="bold")["id"]
    products_mod.create_product(brand_id=bid, name="Hat")
    doc = config_io_mod.export_config()
    assert doc["version"] == 1
    assert any(b.get("name") == "ExportBrand" for b in doc["brands"])
    assert any(p.get("name") == "Hat" for p in doc["products"])


def test_export_excludes_outputs_and_captions(fresh_db):
    doc = config_io_mod.export_config()
    assert "outputs" not in doc
    assert "captions" not in doc


def test_import_recreates_brands_and_products(fresh_db):
    bid = brand_mod.save_brand(name="SrcBrand", voice="bold")["id"]
    products_mod.create_product(brand_id=bid, name="Item")
    doc = config_io_mod.export_config()

    # Wipe + re-init by truncating tables
    conn = app_db.get_conn()
    conn.execute("DELETE FROM products")
    conn.execute("DELETE FROM brands")
    conn.commit()

    counts = config_io_mod.import_config(doc)
    assert counts["brands"] >= 1
    assert counts["products"] >= 1


def test_import_rejects_non_dict(fresh_db):
    with pytest.raises(ValueError):
        config_io_mod.import_config("not a dict")


def test_import_rejects_bad_section_type(fresh_db):
    with pytest.raises(ValueError):
        config_io_mod.import_config({"brands": "nope"})


def test_import_rejects_bad_version(fresh_db):
    with pytest.raises(ValueError):
        config_io_mod.import_config({"version": 9999})


def test_import_merge_false_raises_on_collision(fresh_db):
    brand_mod.save_brand(name="Dup", voice="bold")
    doc = {"brands": [{"name": "Dup", "voice": "bold"}], "version": 1}
    with pytest.raises(ValueError):
        config_io_mod.import_config(doc, merge=False)


def test_import_merge_true_silently_overwrites(fresh_db):
    brand_mod.save_brand(name="Dup", voice="bold")
    doc = {"brands": [{"name": "Dup", "voice": "luxury"}], "version": 1}
    counts = config_io_mod.import_config(doc, merge=True)
    assert counts["brands"] == 1


def test_import_empty_sections_are_no_op(fresh_db):
    counts = config_io_mod.import_config({"version": 1})
    assert all(v == 0 for v in counts.values())