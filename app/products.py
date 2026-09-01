"""app/products.py. Product catalog + rembg cutout (Phase A).

Products and product_variants live in SQLite. Images are stored as paths on
disk. The cutout cache lives in `outputs/cutouts/{product_id}.png` and is
generated lazily on first request via `rembg` (CPU by default, GPU if
`cutout_backend: "sam"` is set and a SAM checkpoint is reachable).

CSV import is column-driven:
    name, price, category, collection, description, image_path, launch_date, tags
`tags` may be `|`-separated. Rows missing required fields are skipped and
listed in the returned `errors` block so the operator can correct and re-run.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app import db as app_db


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CUTOUTS_DIR = PROJECT_ROOT / "outputs" / "cutouts"
CUTOUTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CutoutResult:
    product_id: int
    cutout_path: str
    cache_hit: bool
    elapsed_seconds: float


# ---- row helpers ----

def _row_to_product(row) -> dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags_json") or "[]")
    except json.JSONDecodeError:
        d["tags"] = []
    d.pop("tags_json", None)
    return d


# ---- CRUD ----

def create_product(
    brand_id: int | None,
    *,
    name: str,
    price: float | None = None,
    category: str | None = None,
    collection: str | None = None,
    description: str | None = None,
    image_path: str | None = None,
    tags: list[str] | None = None,
    launch_date: str | None = None,
) -> int:
    if not (name or "").strip():
        raise ValueError("product name is required")
    now = time.time()
    conn = app_db.get_conn()
    cur = conn.execute(
        """
        INSERT INTO products(brand_id, name, price, category, collection,
                             description, image_path, tags_json, launch_date,
                             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            brand_id, name.strip(), price, category, collection,
            description, image_path, json.dumps(tags or []),
            launch_date, now, now,
        ),
    )
    conn.commit()
    new_id = int(cur.lastrowid)
    # Phase G.2 — fire product_added hook for automation rules.
    try:
        from app import automation as automation_mod
        automation_mod.run_rules_for_event(
            "product_added",
            {
                "product_id": new_id,
                "name": name.strip(),
                "brand_id": brand_id,
                "category": category,
                "tags": tags or [],
            },
            brand_id=brand_id,
        )
    except Exception:  # noqa: BLE001
        pass
    return new_id


def update_product(product_id: int, patch: dict) -> bool:
    existing = get_product(product_id)
    if existing is None:
        return False
    merged = {**existing, **{k: v for k, v in patch.items() if k != "tags"}}
    if "tags" in patch:
        merged["tags"] = patch["tags"]
    conn = app_db.get_conn()
    conn.execute(
        """
        UPDATE products SET
            brand_id = ?, name = ?, price = ?, category = ?, collection = ?,
            description = ?, image_path = ?, tags_json = ?, launch_date = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            merged.get("brand_id"),
            merged["name"],
            merged.get("price"),
            merged.get("category"),
            merged.get("collection"),
            merged.get("description"),
            merged.get("image_path"),
            json.dumps(merged.get("tags") or []),
            merged.get("launch_date"),
            time.time(),
            product_id,
        ),
    )
    return True


def delete_product(product_id: int) -> bool:
    conn = app_db.get_conn()
    # Delete any cached cutout file first.
    cutout = CUTOUTS_DIR / f"{product_id}.png"
    if cutout.exists():
        try:
            cutout.unlink()
        except OSError:
            pass
    cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    return cur.rowcount > 0


def get_product(product_id: int) -> dict | None:
    conn = app_db.get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _row_to_product(row) if row else None


def list_products(
    *,
    brand_id: int | None = None,
    category: str | None = None,
    collection: str | None = None,
    tag: str | None = None,
    limit: int = 500,
) -> list[dict]:
    sql = "SELECT * FROM products"
    params: list[Any] = []
    clauses: list[str] = []
    if brand_id is not None:
        clauses.append("brand_id = ?")
        params.append(brand_id)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if collection:
        clauses.append("collection = ?")
        params.append(collection)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    conn = app_db.get_conn()
    rows = conn.execute(sql, params).fetchall()
    out = [_row_to_product(r) for r in rows]
    if tag:
        out = [p for p in out if tag in (p.get("tags") or [])]
    return out


# ---- variants ----

def add_variant(
    product_id: int,
    *,
    variant_name: str,
    sku: str | None = None,
    price_delta: float = 0.0,
    image_path: str | None = None,
) -> int:
    conn = app_db.get_conn()
    cur = conn.execute(
        """
        INSERT INTO product_variants(product_id, variant_name, sku, price_delta, image_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (product_id, variant_name, sku, price_delta, image_path),
    )
    return int(cur.lastrowid)


def list_variants(product_id: int) -> list[dict]:
    conn = app_db.get_conn()
    rows = conn.execute(
        "SELECT * FROM product_variants WHERE product_id = ? ORDER BY variant_name",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---- CSV import ----

CSV_COLUMNS = (
    "name", "price", "category", "collection", "description",
    "image_path", "launch_date", "tags",
)


def bulk_import(brand_id: int | None, rows: Iterable[dict]) -> dict:
    """Import products from a list of dicts. Returns {imported, skipped, errors}.

    A row is rejected (counted in `errors`) if it isn't an object, has no
    name, has a `price` field that isn't coercible to a float, or fails
    persistence for any other reason.
    """
    imported = 0
    skipped = 0
    errors: list[str] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {idx}: not an object")
            skipped += 1
            continue
        try:
            tags_raw = row.get("tags") or ""
            if isinstance(tags_raw, list):
                tags = [str(t).strip() for t in tags_raw if str(t).strip()]
            else:
                tags = [t.strip() for t in str(tags_raw).split("|") if t.strip()]
            raw_price = row.get("price")
            price = None
            if raw_price not in (None, ""):
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    raise ValueError(f"price is not a number: {raw_price!r}")
            create_product(
                brand_id,
                name=row.get("name") or "",
                price=price,
                category=row.get("category") or None,
                collection=row.get("collection") or None,
                description=row.get("description") or None,
                image_path=row.get("image_path") or None,
                tags=tags,
                launch_date=row.get("launch_date") or None,
            )
            imported += 1
        except (ValueError, sqlite3_Error()) as exc:
            errors.append(f"row {idx}: {exc}")
            skipped += 1
    return {"imported": imported, "skipped": skipped, "errors": errors}


def import_csv(brand_id: int | None, csv_text: str) -> dict:
    """Parse CSV text and import. Required column: name."""
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    for row in reader:
        rows.append({k: row.get(k, "") for k in CSV_COLUMNS})
    return bulk_import(brand_id, rows)


def _maybe_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# sqlite3.Error is needed in the except clause above; pulling lazily avoids a
# top-level import that cycles with `app.db` re-exporting sqlite3.
def sqlite3_Error():  # type: ignore[name-defined]
    import sqlite3
    return sqlite3.Error


# ---- cutout (rembg) ----

_LOCK = threading.Lock()


def _read_setting(key: str, default: str | None = None) -> str | None:
    from app.settings import _read_env_file, ENV_PATH
    env = _read_env_file(ENV_PATH)
    return env.get(key) or default


def get_cutout(product_id: int, *, regenerate: bool = False) -> str:
    """Return the path to a PNG cutout. Cached unless `regenerate=True`.

    The DB row's `cutout_path` is the source of truth: if it's set AND points
    at a file that exists AND `regenerate` is False, we return it directly
    without checking the file's location. If the row has no cutout_path but a
    cached file exists at the default location (a stale cache from a previous
    product that shared the id) we still regenerate.
    """
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"no product with id={product_id}")
    target = CUTOUTS_DIR / f"{product_id}.png"
    cached = product.get("cutout_path")
    if not regenerate and cached and Path(cached).exists():
        return cached
    with _LOCK:
        if not regenerate and cached and Path(cached).exists():
            return cached
        return _generate_cutout(product_id, target)


def _generate_cutout(product_id: int, target: Path) -> str:
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"no product with id={product_id}")
    image_path = product.get("image_path")
    if not image_path:
        raise ValueError(f"product {product_id} has no image_path")
    src = Path(image_path)
    if not src.exists():
        # Allow image_path to be relative to project root.
        alt = PROJECT_ROOT / image_path
        if alt.exists():
            src = alt
        else:
            raise FileNotFoundError(f"product image not found: {image_path}")
    # Backend selection (Phase A.6 §Q3): rembg default; SAM opt-in.
    backend = (_read_setting("CALYPSO_CUTOUT_BACKEND", "rembg") or "rembg").lower()
    started = time.monotonic()
    if backend == "rembg":
        try:
            from rembg import remove  # type: ignore
        except ImportError as exc:
            raise RuntimeError("rembg is not installed") from exc
        from PIL import Image
        img = Image.open(src).convert("RGBA")
        out = remove(img)
        target.parent.mkdir(parents=True, exist_ok=True)
        out.save(target, "PNG")
    elif backend == "sam":
        raise NotImplementedError("SAM cutout backend is not yet wired (see plan ADR)")
    else:
        raise ValueError(f"unknown cutout backend: {backend!r}")
    # Update DB row so subsequent reads know about the cutout.
    conn = app_db.get_conn()
    conn.execute(
        "UPDATE products SET cutout_path = ?, updated_at = ? WHERE id = ?",
        (str(target), time.time(), product_id),
    )
    return str(target)


def _copy_to_cache(src: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)


__all__ = [
    "create_product",
    "update_product",
    "delete_product",
    "get_product",
    "list_products",
    "add_variant",
    "list_variants",
    "bulk_import",
    "import_csv",
    "CSV_COLUMNS",
    "get_cutout",
    "CUTOUTS_DIR",
]