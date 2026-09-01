"""Phase G.1 — preset CRUD + apply tests."""

from __future__ import annotations

import pytest

from app import db as app_db
from app import presets as presets_mod
from app import products as products_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "presets.db"
    monkeypatch.setattr(app_db, "DB_PATH", db)
    app_db.reset_for_tests(db)
    app_db.init_db(db)
    yield db


@pytest.fixture
def brand_with_template(fresh_db):
    from app import brand as brand_mod
    from app import templates as tpl_mod

    bid = brand_mod.save_brand(name="Preset Brand", voice="bold")["id"]
    tid = tpl_mod.create_template({
        "name": "Bold Drop",
        "category": "ugc",
        "aspect_ratio": "1:1",
        "canvas": {"width": 1080, "height": 1080},
        "layers": [
            {"id": "bg", "type": "ai_background", "name": "BG",
             "config": {"prompt": "studio"}},
            {"id": "h", "type": "text", "name": "Headline",
             "config": {"content": "Hi", "font_family": "Inter",
                         "color": "#fff"}},
        ],
    }, brand_id=bid)
    return {"brand_id": bid, "template_id": tid}


def test_create_returns_id(fresh_db):
    pid = presets_mod.create(
        None, name="My Preset", description="a winner"
    )
    assert isinstance(pid, int)
    assert pid > 0


def test_create_rejects_empty_name(fresh_db):
    with pytest.raises(ValueError):
        presets_mod.create(None, name="")


def test_get_returns_decoded_layers(fresh_db):
    pid = presets_mod.create(
        None, name="P1", layers=[{"id": "h", "text": "Override"}]
    )
    p = presets_mod.get(pid)
    assert p["name"] == "P1"
    assert isinstance(p["layers"], list)
    assert p["layers"][0]["text"] == "Override"


def test_list_for_brand(fresh_db, brand_with_template):
    bid = brand_with_template["brand_id"]
    presets_mod.create(bid, name="a")
    presets_mod.create(bid, name="b")
    presets_mod.create(None, name="c")
    rows = presets_mod.list_for_brand(bid)
    names = sorted(p["name"] for p in rows)
    assert names == ["a", "b"]


def test_update_partial(fresh_db):
    pid = presets_mod.create(None, name="U", filter_name="bright")
    updated = presets_mod.update(pid, name="U2", filter="moody")
    assert updated["name"] == "U2"
    assert updated["filter"] == "moody"


def test_delete(fresh_db):
    pid = presets_mod.create(None, name="del")
    assert presets_mod.delete(pid) is True
    assert presets_mod.get(pid) is None


def test_apply_renders_outputs(fresh_db, brand_with_template, monkeypatch):
    """apply() should render the preset's template against each product
    and create one outputs row per product."""
    bid = brand_with_template["brand_id"]
    tid = brand_with_template["template_id"]
    # Stub the compositor to avoid rembg model download + PIL rendering.
    from app import compositor as compositor_mod

    class FakeResult:
        def __init__(self, oid):
            self.output_id = oid
            self.file_path = f"/tmp/{oid}.jpg"
            self.cost_usd = 0.0
            self.cached_background = False
            self.elapsed_seconds = 0.01

    counter = {"i": 0}

    def fake_render(template_id, **kwargs):
        counter["i"] += 1
        return FakeResult(counter["i"])

    monkeypatch.setattr(compositor_mod, "render", fake_render)

    pid = products_mod.create_product(brand_id=bid, name="Sneaker")
    p2 = products_mod.create_product(brand_id=bid, name="Boot")
    preset_id = presets_mod.create(bid, name="auto", template_id=tid,
                                     filter_name="bright")
    ids = presets_mod.apply(preset_id, [pid, p2])
    assert sorted(ids) == [1, 2]


def test_apply_no_template_returns_empty(fresh_db):
    pid = presets_mod.create(None, name="no-tpl")
    assert presets_mod.apply(pid, []) == []


def test_batch_apply_returns_summary(fresh_db, brand_with_template, monkeypatch):
    from app import compositor as compositor_mod

    class FakeResult:
        output_id = 1
        file_path = "/tmp/x.jpg"
        cost_usd = 0.0
        cached_background = False
        elapsed_seconds = 0.0

    monkeypatch.setattr(compositor_mod, "render", lambda *a, **k: FakeResult())

    bid = brand_with_template["brand_id"]
    p1 = products_mod.create_product(brand_id=bid, name="A")
    p2 = products_mod.create_product(brand_id=bid, name="B")
    p3 = products_mod.create_product(brand_id=bid, name="C")
    pid = presets_mod.create(
        bid, name="b", template_id=brand_with_template["template_id"],
    )
    summary = presets_mod.batch_apply(pid, [p1, p2, p3])
    assert summary["queued"] == 3
    assert "output_ids" in summary
    assert summary["errors"] == []