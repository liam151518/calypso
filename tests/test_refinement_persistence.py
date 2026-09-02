"""Tests for Phase I: Refinement Studio persistence.

Validates that `outputs.layers_json` and `outputs.filter_settings` are
written by the compositor and round-tripped through `outputs.get_output()`.
Also confirms the `output_versions` table is created.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    from app import db as app_db
    target = tmp_path / "refine.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


def test_outputs_columns_exist(fresh_db):
    from app import db as app_db
    conn = app_db.get_conn(fresh_db)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(outputs)").fetchall()}
    assert "layers_json" in cols
    assert "filter_settings" in cols


def test_output_versions_table_exists(fresh_db):
    from app import db as app_db
    conn = app_db.get_conn(fresh_db)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='output_versions'"
    ).fetchone()
    assert row is not None
    cols = {row[1] for row in conn.execute("PRAGMA table_info(output_versions)").fetchall()}
    assert {"id", "output_id", "layers_json", "filter_settings",
            "file_path", "thumbnail_path", "notes", "cost_usd",
            "created_at"}.issubset(cols)


def test_compositor_persists_layers_and_filter(fresh_db, monkeypatch, tmp_path):
    """Run a full compositor.render() and confirm layers/filter get stored."""
    from app import db as app_db, templates as templates_mod
    now = __import__("time").time()

    # Seed a brand + a template
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("Test Brand", now, now),
        )
        bid = c.execute("SELECT id FROM brands WHERE name='Test Brand'").fetchone()[0]

    template_id = templates_mod.create_template({
        "name": "Refine Test",
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
                "config": {"prompt": "soft gradient", "model": "flux-pro/v1.1"},
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

    # Render with a filter
    from app import compositor
    monkeypatch.setattr(compositor, "IMAGES_DIR", tmp_path / "imgs")
    monkeypatch.setattr(compositor, "CACHE_DIR", tmp_path / "cache")
    result = compositor.render(
        template_id=template_id,
        brand_id=bid,
        filter_name="moody",
        intensity=0.5,
        cache_hit_only=True,  # don't hit fal.ai
    )
    assert result.output_id > 0

    # Read it back
    from app import outputs as outputs_mod
    out = outputs_mod.get_output(result.output_id)
    assert out is not None
    assert isinstance(out["layers"], list)
    assert len(out["layers"]) == 2
    assert out["layers"][0]["type"] == "ai_background"
    assert out["layers"][0]["config"]["prompt"] == "soft gradient"
    assert isinstance(out["filter"], dict)
    assert out["filter"]["filter_name"] == "moody"
    assert out["filter"]["intensity"] == 0.5


def test_get_output_handles_malformed_json(fresh_db, monkeypatch):
    """Defensive: malformed JSON should not crash get_output()."""
    from app import db as app_db, outputs as outputs_mod
    now = __import__("time").time()
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("X", now, now),
        )
        bid = c.execute("SELECT id FROM brands WHERE name='X'").fetchone()[0]
        c.execute(
            "INSERT INTO outputs (brand_id, type, file_path, status, "
            "created_at, layers_json, filter_settings) "
            "VALUES (?, 'image', '/tmp/x.jpg', 'draft', ?, 'NOT_JSON', 'also-bad')",
            (bid, now),
        )
        oid = c.execute("SELECT id FROM outputs ORDER BY id DESC LIMIT 1").fetchone()[0]

    out = outputs_mod.get_output(oid)
    assert out is not None
    assert out["layers"] == []   # fallback
    assert out["filter"] == {}   # fallback


def test_legacy_outputs_get_default_columns(fresh_db):
    """Migration is idempotent on legacy rows (no layers_json before)."""
    from app import db as app_db, outputs as outputs_mod
    now = __import__("time").time()
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("Y", now, now),
        )
        bid = c.execute("SELECT id FROM brands WHERE name='Y'").fetchone()[0]
        # Insert WITHOUT specifying the new columns — should get defaults.
        c.execute(
            "INSERT INTO outputs (brand_id, type, file_path, status, created_at) "
            "VALUES (?, 'image', '/tmp/y.jpg', 'draft', ?)",
            (bid, now),
        )
        oid = c.execute("SELECT id FROM outputs ORDER BY id DESC LIMIT 1").fetchone()[0]

    out = outputs_mod.get_output(oid)
    assert out is not None
    assert out["layers"] == []
    assert out["filter"] == {}
