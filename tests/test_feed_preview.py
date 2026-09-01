"""Phase C feed-preview tests."""

from __future__ import annotations

import time

import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    from app import db as app_db
    target = tmp_path / "feed.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


def _insert_brand(c, name: str) -> int:
    now = time.time()
    cur = c.execute(
        "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
        (name, now, now),
    )
    return int(cur.lastrowid)


def _insert_output(c, brand_id: int, created_at: float) -> int:
    cur = c.execute(
        "INSERT INTO outputs (brand_id, type, file_path, status, created_at) "
        "VALUES (?, 'image', ?, 'rendered', ?)",
        (brand_id, f"/tmp/feed_{created_at}.jpg", created_at),
    )
    return int(cur.lastrowid)


def test_grid_empty_when_no_outputs(fresh_db):
    from app import feed_preview as fp
    assert fp.grid() == []


def test_grid_returns_up_to_nine_items(fresh_db):
    from app import db as app_db
    from app import feed_preview as fp

    with app_db.connect() as c:
        bid = _insert_brand(c, "B1")
        now = time.time()
        for i in range(12):
            _insert_output(c, bid, now - i)
    items = fp.grid(brand_id=bid)
    assert len(items) == 9
    # ORDER BY created_at DESC → newest item is at index 0 (lower id, since
    # ids auto-increment in insertion order).
    assert items[0]["id"] < items[-1]["id"]  # newest first
    # Strictly descending by timestamp.
    timestamps = [item["created_at"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True)


def test_new_output_id_is_prepended(fresh_db):
    from app import db as app_db
    from app import feed_preview as fp

    with app_db.connect() as c:
        bid = _insert_brand(c, "B1")
        now = time.time()
        for i in range(3):
            _insert_output(c, bid, now - i)
    items = fp.grid(brand_id=bid, new_output_id=99)
    # new_output_id=99 doesn't exist, so no prepend happens.
    assert len(items) == 3

    # Now create the new row and call again.
    with app_db.connect() as c:
        new_id = _insert_output(c, bid, now + 1)
    items = fp.grid(brand_id=bid, new_output_id=new_id)
    assert items[0]["id"] == new_id


def test_shuffle_returns_same_items_in_different_order(fresh_db):
    from app import db as app_db
    from app import feed_preview as fp

    with app_db.connect() as c:
        bid = _insert_brand(c, "B1")
        now = time.time()
        for i in range(6):
            _insert_output(c, bid, now - i)
    base = fp.grid(brand_id=bid)
    shuffled = fp.shuffle(brand_id=bid, request_token="abc")
    assert {i["id"] for i in base} == {i["id"] for i in shuffled}
    # Different request tokens should generally produce different orderings.
    other = fp.shuffle(brand_id=bid, request_token="zzz")
    assert [i["id"] for i in shuffled] != [i["id"] for i in other] or len(base) <= 1


def test_grid_filters_by_brand(fresh_db):
    from app import db as app_db
    from app import feed_preview as fp

    with app_db.connect() as c:
        a = _insert_brand(c, "A")
        b = _insert_brand(c, "B")
        now = time.time()
        _insert_output(c, a, now)
        _insert_output(c, b, now - 1)
    items_a = fp.grid(brand_id=a)
    items_b = fp.grid(brand_id=b)
    assert all(item["brand_id"] == a for item in items_a)
    assert all(item["brand_id"] == b for item in items_b)