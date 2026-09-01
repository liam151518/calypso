"""Phase C caption generator tests.

Covers the heuristic path, banned-words enforcement, cache reuse, and the
LLM-fallback behaviour when no API key is configured. The DB is fresh per
test via the shared ``fresh_db`` fixture; the captions table was created
in Phase A and extended in Phase C with a unique ``cache_key`` index.
"""

from __future__ import annotations

import time

import pytest

from app import captions as captions_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Redirect app_db.DB_PATH to a temp file and re-init the schema."""
    from app import db as app_db
    target = tmp_path / "captions.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


def _req(platform: str = "instagram", tone: str = "bold") -> captions_mod.CaptionRequest:
    return captions_mod.CaptionRequest(
        product={"id": 1, "name": "Cyan Sneaker", "price": 99.0, "sku": "CS-01"},
        template={"id": 7, "name": "Minimal Launch"},
        brand={"id": 1, "name": "Gachakingdoms", "voice": tone},
        platform=platform,
    )


def test_generate_returns_three_variants(fresh_db):
    variants = captions_mod.generate(req=_req())
    assert len(variants) == 3
    for v in variants:
        assert v.content
        assert isinstance(v.hashtags, list)
        assert v.first_comment


def test_variants_are_distinct(fresh_db):
    variants = captions_mod.generate(req=_req())
    contents = {v.content for v in variants}
    assert len(contents) == len(variants)


def test_banned_words_filter_out_offending_variants(fresh_db):
    """Find a variant whose content includes a banned term, then verify the
    filter removes it on a re-run with that word in ``banned_words``."""
    # Run many seeds until we get a variant containing "disrupt" (bold tone uses it).
    found = None
    for tone in ("bold",):
        for brand_id in range(1, 30):
            req = captions_mod.CaptionRequest(
                product={"id": brand_id, "name": f"Item {brand_id}", "price": 50.0},
                template={"id": 7, "name": "Minimal Launch"},
                brand={"id": 1, "name": "Gachakingdoms", "voice": tone},
                platform="instagram",
            )
            for v in captions_mod.generate(req=req):
                if "disrupt" in v.content.lower():
                    found = v
                    break
            if found:
                break
        if found:
            break
    assert found is not None, "expected at least one variant with 'disrupt' (bold bank)"

    # Now ban "disrupt" with the same key and verify the variant disappears.
    req2 = captions_mod.CaptionRequest(
        product={"id": 1, "name": "Cyan Sneaker", "price": 99.0},
        template={"id": 7, "name": "Minimal Launch"},
        brand={"id": 1, "name": "Gachakingdoms", "voice": "bold",
               "banned_words": ["disrupt"]},
        platform="instagram",
    )
    # Different cache key (brand payload differs), so we always re-generate.
    variants = captions_mod.generate(req=req2)
    assert all("disrupt" not in v.content.lower() for v in variants)
    # We get at least one variant (a fallback when all are filtered).
    assert len(variants) >= 1


def test_cache_returns_same_variants_within_ttl(fresh_db):
    first = captions_mod.generate(req=_req())
    again = captions_mod.generate(req=_req())
    assert [v.content for v in again] == [v.content for v in first]


def test_cache_key_changes_with_brand_voice(fresh_db):
    req = _req(tone="bold")
    a = captions_mod.generate(req=req)
    # Change voice — fresh variants.
    req.brand = {**req.brand, "voice": "minimal"}
    b = captions_mod.generate(req=req)
    assert [v.content for v in a] != [v.content for v in b]


def test_llm_model_falls_back_to_heuristic_without_api_key(
    fresh_db, monkeypatch
):
    monkeypatch.delenv("FAL_API_KEY", raising=False)
    req = _req()
    req.model = "llm"
    variants = captions_mod.generate(req=req)
    assert len(variants) == 3
    assert all(v.content for v in variants)


def test_unknown_platform_raises(fresh_db):
    req = _req()
    req.platform = "myspace"
    with pytest.raises(ValueError):
        captions_mod.generate(req=req)


def test_persist_selection_writes_row(fresh_db):
    req = _req()
    variants = captions_mod.generate(req=req)
    caption_id = captions_mod.persist_selection(
        output_id=0,
        variant=variants[0],
        platform="instagram",
        brand_id=1,
        template_id=7,
        product_id=1,
    )
    assert caption_id > 0


def test_list_for_output_returns_persisted_captions(fresh_db):
    from app import db as app_db
    now = time.time()
    # Seed an outputs row so the FK constraint is satisfied.
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("TestBrand", now, now),
        )
        bid = c.execute("SELECT id FROM brands WHERE name='TestBrand'").fetchone()[0]
        c.execute(
            "INSERT INTO outputs (brand_id, type, file_path, status, created_at) "
            "VALUES (?, 'image', '/tmp/x.jpg', 'rendered', ?)",
            (bid, now),
        )
        out_id = int(c.execute("SELECT id FROM outputs ORDER BY id DESC LIMIT 1").fetchone()[0])

    req = _req()
    variants = captions_mod.generate(req=req)
    captions_mod.persist_selection(
        output_id=out_id,
        variant=variants[0],
        platform="instagram",
        brand_id=bid,
    )
    rows = captions_mod.list_for_output(out_id)
    assert len(rows) == 1
    assert rows[0]["is_selected"] is True
    assert rows[0]["content"] == variants[0].content