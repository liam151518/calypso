"""Tests for the Refinement Studio per-layer regenerate endpoint."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import pytest


@dataclass
class _FakeRenderResult:
    output_id: int = 0
    file_path: str = "/tmp/regen.jpg"
    cost_usd: float = 0.05
    cached_background: bool = False
    elapsed_seconds: float = 0.0


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    from app import db as app_db
    target = tmp_path / "regen.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


@pytest.fixture
def seeded_output_with_layers(fresh_db):
    """Insert one output row + a template that has 2 layers (bg + text)."""
    from app import db as app_db, templates as templates_mod
    now = time.time()
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("RegenBrand", now, now),
        )
        bid = c.execute(
            "SELECT id FROM brands WHERE name='RegenBrand'"
        ).fetchone()[0]

    template_id = templates_mod.create_template({
        "name": "Regen Test",
        "category": "minimal",
        "aspect_ratio": "1:1",
        "canvas": {"width": 512, "height": 512},
        "layers": [
            {
                "id": "bg",
                "type": "ai_background",
                "name": "Background",
                "visible": True,
                "locked": False,
                "x": 0, "y": 0, "width": 100, "height": 100,
                "config": {"prompt": "original", "model": "flux-pro/v1.1"},
            },
            {
                "id": "title",
                "type": "text",
                "name": "Title",
                "visible": True,
                "locked": False,
                "x": 10, "y": 10, "width": 80, "height": 20,
                "config": {
                    "content": "Hello",
                    "color": "#fff",
                    "font_family": "Inter",
                    "font_size": 32,
                    "font_weight": "normal",
                    "text_align": "center",
                },
            },
        ],
    }, brand_id=bid)

    layers_json = json.dumps([
        {
            "id": "bg", "type": "ai_background", "name": "BG",
            "visible": True, "locked": False,
            "x": 0, "y": 0, "width": 100, "height": 100,
            "config": {"prompt": "original", "model": "flux-pro/v1.1"},
        },
        {
            "id": "title", "type": "text", "name": "Title",
            "visible": True, "locked": False,
            "x": 10, "y": 10, "width": 80, "height": 20,
            "config": {"content": "Hello", "color": "#fff"},
        },
    ])
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO outputs (brand_id, template_id, type, file_path, "
            "status, created_at, layers_json, filter_settings) "
            "VALUES (?, ?, 'image', '/tmp/orig.jpg', 'draft', ?, ?, '{}')",
            (bid, template_id, now, layers_json),
        )
        oid = c.execute(
            "SELECT id FROM outputs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    return oid, template_id


def test_regenerate_layer_ai_background_updates_prompt(
        fresh_db, seeded_output_with_layers, monkeypatch, tmp_path):
    from app import refinement as refine
    oid, tid = seeded_output_with_layers

    # Mock compositor.render to avoid hitting fal.ai.
    from app import compositor

    captured = {}

    def fake_render(*, template_id, product_id=None, layer_overrides=None,
                    filter_name=None, aspect_ratio=None, intensity=1.0,
                    brand_id=None, cache_hit_only=False, **kw):
        captured["template_id"] = template_id
        captured["layer_overrides"] = layer_overrides
        captured["filter_name"] = filter_name
        captured["intensity"] = intensity
        return _FakeRenderResult(file_path=str(tmp_path / "regen.jpg"))

    monkeypatch.setattr(compositor, "render", fake_render)

    result = refine.regenerate_layer(
        oid, 0,
        prompt="new cinematic backdrop",
        seed=42,
        model="flux-pro/v1.0",
        notes="trying something moody",
    )

    # New version was persisted
    assert result["version"]["id"] > 0
    assert result["version"]["output_id"] == oid
    # Caller-supplied notes win over the auto-generated default.
    assert "trying something moody" in result["version"]["notes"]

    # Default notes auto-populate when not provided.
    monkeypatch.setattr(
        compositor, "render",
        lambda **kw: _FakeRenderResult(file_path=str(tmp_path / "r2.jpg")),
    )
    auto = refine.regenerate_layer(oid, 0, prompt="another")
    assert "regenerated layer 0" in auto["version"]["notes"]

    # The mutated layer reflects the new prompt
    layers = json.loads(result["version"]["layers_json"])
    bg = next(l for l in layers if l["id"] == "bg")
    assert bg["config"]["prompt"] == "new cinematic backdrop"
    assert bg["config"]["seed"] == 42
    assert bg["config"]["model"] == "flux-pro/v1.0"

    # The other layer is untouched
    title = next(l for l in layers if l["id"] == "title")
    assert title["config"]["content"] == "Hello"

    # The compositor was called with the patched layers
    assert captured["template_id"] == tid
    assert captured["layer_overrides"]["layers"] == layers


def test_regenerate_text_layer_changes_content(
        fresh_db, seeded_output_with_layers, monkeypatch, tmp_path):
    from app import refinement as refine
    from app import compositor
    oid, _ = seeded_output_with_layers

    monkeypatch.setattr(
        compositor, "render",
        lambda **kw: _FakeRenderResult(file_path=str(tmp_path / "r.jpg")),
    )

    result = refine.regenerate_layer(
        oid, 1, text_content="Goodbye world", notes="copy update",
    )
    layers = json.loads(result["version"]["layers_json"])
    title = next(l for l in layers if l["id"] == "title")
    assert title["config"]["content"] == "Goodbye world"


def test_regenerate_unknown_output_raises(fresh_db):
    from app import refinement as refine
    with pytest.raises(ValueError, match="not found"):
        refine.regenerate_layer(999999, 0, prompt="x")


def test_regenerate_layer_index_out_of_range(
        fresh_db, seeded_output_with_layers):
    from app import refinement as refine
    oid, _ = seeded_output_with_layers
    with pytest.raises(ValueError, match="out of range"):
        refine.regenerate_layer(oid, 99, prompt="x")


def test_regenerate_with_no_changes_raises(
        fresh_db, seeded_output_with_layers):
    from app import refinement as refine
    oid, _ = seeded_output_with_layers
    with pytest.raises(ValueError, match="no changes"):
        refine.regenerate_layer(oid, 0)


def test_regenerate_unsupported_layer_type_raises(
        fresh_db, seeded_output_with_layers, monkeypatch):
    from app import refinement as refine
    oid, _ = seeded_output_with_layers
    # Mutate the persisted layers to a shape type
    from app import db as app_db
    with app_db.connect() as c:
        c.execute(
            "UPDATE outputs SET layers_json = ? WHERE id = ?",
            (json.dumps([
                {"id": "rect", "type": "shape", "name": "R",
                 "visible": True, "locked": False,
                 "x": 0, "y": 0, "width": 100, "height": 100,
                 "config": {"shape_type": "rectangle", "fill_color": "#fff"}},
            ]), oid),
        )
    with pytest.raises(ValueError, match="not regeneratable"):
        refine.regenerate_layer(oid, 0, prompt="x")


# ---- API endpoint ------------------------------------------------------


@pytest.fixture
def app_with_db(fresh_db):
    from app.server import create_app
    return create_app()


@pytest.fixture
def client(app_with_db):
    return app_with_db.test_client()


def test_api_regenerate_layer_returns_version(
        client, seeded_output_with_layers, monkeypatch, tmp_path):
    oid, _ = seeded_output_with_layers
    from app import compositor
    monkeypatch.setattr(
        compositor, "render",
        lambda **kw: _FakeRenderResult(file_path=str(tmp_path / "r.jpg")),
    )
    res = client.post(
        f"/api/outputs/{oid}/layers/0/regenerate",
        json={"prompt": "new prompt", "seed": 7},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["layer"]["config"]["prompt"] == "new prompt"
    assert data["layer"]["config"]["seed"] == 7
    assert data["render"]["file_path"].endswith("r.jpg")


def test_api_regenerate_layer_unknown_output_returns_404(client):
    res = client.post(
        "/api/outputs/999999/layers/0/regenerate",
        json={"prompt": "x"},
    )
    assert res.status_code == 404


def test_api_regenerate_layer_bad_index_returns_400(
        client, seeded_output_with_layers):
    oid, _ = seeded_output_with_layers
    res = client.post(
        f"/api/outputs/{oid}/layers/99/regenerate",
        json={"prompt": "x"},
    )
    assert res.status_code == 400
