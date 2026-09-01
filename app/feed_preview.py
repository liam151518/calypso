"""app/feed_preview. 3×3 feed grid showing the most recent outputs for a brand.

Used by the SPA FeedPreview page; ``grid()`` returns at most 9 items and
optionally inserts a brand-new output at the top so the operator can see
how the freshly generated post sits next to the existing feed.

The shuffle endpoint is intentionally a no-op reorder: the underlying
data is unchanged, but we return the items in a deterministic but rotated
order keyed by ``request_token`` so the UI can show variety.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from . import db as app_db

log = logging.getLogger(__name__)

GRID_LIMIT = 9


def grid(brand_id: int | None = None, *,
         new_output_id: int | None = None) -> list[dict[str, Any]]:
    """Return up to GRID_LIMIT recent outputs for the brand.

    If ``new_output_id`` is provided and exists, it's prepended and the
    list is trimmed to ``GRID_LIMIT``.
    """
    sql = (
        "SELECT id, brand_id, product_id, template_id, type, file_path, "
        "       aspect_ratio, status, filter_applied, created_at "
        "FROM outputs WHERE status IN ('rendered', 'ready', 'published') "
    )
    params: list[Any] = []
    if brand_id is not None:
        sql += " AND brand_id = ?"
        params.append(int(brand_id))
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(GRID_LIMIT)
    items = _fetch(sql, params)

    if new_output_id is not None:
        new = _fetch_one(new_output_id)
        if new:
            # Strip any duplicate (e.g. the new id was already in the top-9)
            items = [i for i in items if int(i["id"]) != int(new_output_id)]
            items.insert(0, new)

    return [_serialize(i) for i in items]


def _fetch(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    with app_db.connect() as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def _fetch_one(output_id: int) -> dict[str, Any] | None:
    with app_db.connect() as c:
        r = c.execute(
            "SELECT id, brand_id, product_id, template_id, type, file_path, "
            "       aspect_ratio, status, filter_applied, created_at "
            "FROM outputs WHERE id = ?",
            (int(output_id),),
        ).fetchone()
    if not r:
        return None
    return _row_to_dict(r)


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row[0]),
        "brand_id": row[1],
        "product_id": row[2],
        "template_id": row[3],
        "type": row[4],
        "file_path": row[5],
        "aspect_ratio": row[6],
        "status": row[7],
        "filter_applied": row[8],
        "created_at": float(row[9]),
    }


def _serialize(item: dict[str, Any]) -> dict[str, Any]:
    rel_url = _to_rel_url(item.get("file_path"))
    return {
        "id": int(item["id"]),
        "brand_id": item.get("brand_id"),
        "product_id": item.get("product_id"),
        "template_id": item.get("template_id"),
        "type": item.get("type"),
        "aspect_ratio": item.get("aspect_ratio"),
        "status": item.get("status"),
        "filter_applied": item.get("filter_applied"),
        "created_at": item.get("created_at"),
        "rel_url": rel_url,
        "thumb_url": rel_url,  # thumbnails == full image until Phase H
    }


def _to_rel_url(file_path: str | os.PathLike[str] | None) -> str | None:
    if not file_path:
        return None
    p = Path(file_path)
    name = p.name
    # /outputs/images/<file> matches the Flask route; videos use a parallel route.
    if "videos" in p.parts:
        return f"/outputs/videos/{name}"
    return f"/outputs/images/{name}"


def shuffle(brand_id: int | None = None, *,
            request_token: str | None = None) -> list[dict[str, Any]]:
    """Return a deterministically-shuffled view of the same grid."""
    items = grid(brand_id=brand_id)
    if not items:
        return items
    seed = (request_token or "").encode() or b"calypso-shuffle"
    h = hashlib.sha1(seed).hexdigest()
    # Deterministic rotation only — we never randomise the underlying data.
    shift = int(h[:4], 16) % len(items)
    return items[shift:] + items[:shift]