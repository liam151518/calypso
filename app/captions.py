"""app/captions. Heuristic + LLM caption generator for brand-poster outputs.

Generates CaptionVariant lists for a given product / template / brand /
platform combination. The heuristic path is the default; it requires no
external API key and uses a per-tone word bank to keep the copy on-brand.

Cache key: (product_id, template_id, platform, model, brand_voice_tone, day).
24-hour TTL by default. The LLM backend is a thin wrapper around `Fal LLM`
when the API key is available; failures fall back to heuristic.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import db as app_db

log = logging.getLogger(__name__)

VALID_PLATFORMS = ("instagram", "tiktok", "x", "linkedin", "facebook")
VALID_TONES = ("bold", "playful", "luxury", "minimal", "cinematic", "casual")

# ---- Dataclass -----------------------------------------------------------


@dataclass
class CaptionVariant:
    content: str
    hashtags: list[str] = field(default_factory=list)
    first_comment: str = ""
    alt_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaptionRequest:
    product: dict[str, Any]
    template: dict[str, Any]
    brand: dict[str, Any] | None
    platform: str
    model: str = "heuristic"

    @property
    def key(self) -> str:
        product_id = self.product.get("id") or self.product.get("sku") or "anon"
        template_id = self.template.get("id") or self.template.get("name") or "tmpl"
        tone = (self.brand or {}).get("voice") or "casual"
        day = time.strftime("%Y-%m-%d")
        seed = f"{product_id}|{template_id}|{self.platform}|{self.model}|{tone}|{day}"
        return hashlib.sha1(seed.encode()).hexdigest()[:16]


# ---- Word banks ----------------------------------------------------------

_WORDBANK_DIR = Path(__file__).resolve().parent / "captions" / "wordbanks"


def _load_bank(tone: str) -> dict[str, list[str]]:
    path = _WORDBANK_DIR / f"{tone}.json"
    if not path.exists():
        # fall back to "casual" so the generator never explodes
        path = _WORDBANK_DIR / "casual.json"
    if not path.exists():
        return {"hooks": [], "bodies": [], "ctas": []}
    return json.loads(path.read_text())


def _seeded_rng(key: str) -> random.Random:
    seed = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


# ---- Heuristic generator -------------------------------------------------


def _format_price(price: Any) -> str:
    try:
        return f"${float(price):.2f}"
    except (TypeError, ValueError):
        return ""


def _product_label(product: dict[str, Any]) -> str:
    name = product.get("name") or product.get("title") or product.get("sku") or "this drop"
    return str(name).strip() or "this drop"


def _hashtags_for(brand: dict[str, Any] | None, platform: str) -> list[str]:
    base: list[str] = []
    if brand and brand.get("name"):
        tag = "#" + "".join(c for c in str(brand["name"]) if c.isalnum())
        base.append(tag)
    base.extend(["#newdrop", "#shopnow", "#smallbatch"])
    if platform == "instagram":
        base.append("#instadaily")
    elif platform == "tiktok":
        base.append("#fyp")
    elif platform == "linkedin":
        base.append("#launch")
    return base[:6]


def _apply_banned(req: CaptionRequest, variants: list[CaptionVariant]) -> list[CaptionVariant]:
    banned = set((req.brand or {}).get("banned_words") or [])
    if isinstance(banned, str):
        banned = {w.strip() for w in banned.split(",") if w.strip()}
    if not banned:
        return variants
    kept: list[CaptionVariant] = []
    for v in variants:
        if any(w.lower() in v.content.lower() for w in banned):
            continue
        kept.append(v)
    # Always return 3 if we can. If the filter removed everything we replace
    # with a single safe variant.
    if not kept:
        kept.append(
            CaptionVariant(
                content=f"{_product_label(req.product)} (rephrased to honor banned words).",
                hashtags=_hashtags_for(req.brand, req.platform),
                first_comment="",
                alt_text=_product_label(req.product),
            )
        )
    return kept


def _heuristic(req: CaptionRequest, *, count: int = 3) -> list[CaptionVariant]:
    tone = (req.brand or {}).get("voice") or "casual"
    if tone not in VALID_TONES:
        tone = "casual"
    bank = _load_bank(tone)
    product_name = _product_label(req.product)
    price = _format_price(req.product.get("price"))
    hooks = bank.get("hooks") or ["New drop."]
    bodies = bank.get("bodies") or [f"{product_name} just landed."]
    ctas = bank.get("ctas") or ["Tap the link in bio."]

    rng = _seeded_rng(req.key + tone)
    variants: list[CaptionVariant] = []
    seen: set[str] = set()

    for _ in range(count * 3):
        if len(variants) >= count:
            break
        hook = rng.choice(hooks)
        body = rng.choice(bodies)
        cta = rng.choice(ctas)
        content_parts = [hook]
        if body and body != hook:
            content_parts.append(body)
        content_parts.append(product_name)
        if price:
            content_parts.append(f"now at {price}.")
        content_parts.append(cta)
        content = " ".join(p for p in content_parts if p).strip()
        if content in seen:
            continue
        seen.add(content)

        hashtags = _hashtags_for(req.brand, req.platform)
        first_comment = f"Ask us anything about {product_name} in the comments."
        alt_text = f"{product_name} on {req.brand['name'] if req.brand and req.brand.get('name') else 'brand'} branded artwork."
        variants.append(
            CaptionVariant(
                content=content,
                hashtags=hashtags,
                first_comment=first_comment,
                alt_text=alt_text,
            )
        )

    # If heuristics produced nothing (e.g. all hits filtered by banned words),
    # fall back to a single safe variant.
    if not variants:
        variants.append(
            CaptionVariant(
                content=f"{product_name}. New from us.",
                hashtags=_hashtags_for(req.brand, req.platform),
                first_comment="",
                alt_text=f"{product_name} promo.",
            )
        )
    return variants[:count]


# ---- LLM backend (optional, on-demand) ----------------------------------


def _llm_variants(req: CaptionRequest, *, count: int = 3) -> list[CaptionVariant] | None:
    if not os.environ.get("FAL_API_KEY"):
        return None
    try:
        # Late import keeps the heuristic path dependency-free.
        import urllib.request

        prompt = (
            "Generate {n} short, distinct social captions for {platform}. "
            "Product: {product}. Tone: {tone}. Brand: {brand}. "
            "Each caption must include 1-3 hashtags."
        ).format(
            n=count,
            platform=req.platform,
                product=_product_label(req.product),
                tone=(req.brand or {}).get("voice") or "casual",
                brand=(req.brand or {}).get("name") or "Calypso",
            )
        body = json.dumps({"prompt": prompt, "max_tokens": 256}).encode()
        req_http = urllib.request.Request(
            "https://fal.run/llm",
            data=body,
            headers={
                "Authorization": f"Key {os.environ['FAL_API_KEY']}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req_http, timeout=20) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode())
        # The exact shape of the response is provider-dependent; we
        # accept any list of strings under `captions` or `text`.
        candidates = payload.get("captions") or payload.get("text") or []
        if isinstance(candidates, str):
            candidates = [c.strip() for c in candidates.split("\n\n") if c.strip()]
        if not candidates:
            return None
        variants: list[CaptionVariant] = []
        for c in candidates[:count]:
            if isinstance(c, dict):
                content = c.get("content") or c.get("text") or ""
                hashtags = c.get("hashtags") or []
            else:
                content = str(c)
                hashtags = []
            variants.append(
                CaptionVariant(
                    content=content,
                    hashtags=hashtags or _hashtags_for(req.brand, req.platform),
                    first_comment="",
                    alt_text=_product_label(req.product),
                )
            )
        return variants
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM caption path failed, falling back to heuristic: %s", exc)
        return None


# ---- Cache ----------------------------------------------------------------

_CACHE_TTL_S = 60 * 60 * 24


def _ensure_captions_table() -> None:
    """The captions table is created by app/db.py; this is a no-op shim
    that exposes the cache as a writer through the same DB connection."""
    return None


def _cache_get(key: str) -> list[dict[str, Any]] | None:
    with app_db.connect() as c:
        row = c.execute(
            "SELECT hashtags, expires_at FROM captions WHERE cache_key = ? "
            "ORDER BY id DESC LIMIT 1",
            (key,),
        ).fetchone()
    if not row:
        return None
    hashtags_json, expires_at = row[0], float(row[1] or 0)
    if expires_at and expires_at < time.time():
        return None
    try:
        return json.loads(hashtags_json or "[]")
    except json.JSONDecodeError:
        return None


def _cache_put(key: str, variants: list[CaptionVariant]) -> None:
    expires_at = time.time() + _CACHE_TTL_S
    payload = json.dumps([v.to_dict() for v in variants])
    # Reuse the existing captions table: variant_index=0, content=summary,
    # hashtags holds the JSON array of variants. cache_key makes it a
    # unique cache slot via the unique index we added in db.py.
    with app_db.connect() as c:
        c.execute(
            """INSERT INTO captions
               (cache_key, variant_index, content, hashtags,
                expires_at, created_at, is_selected)
               VALUES (?, 0, ?, ?, ?, ?, 0)
               ON CONFLICT(cache_key) DO UPDATE SET
                   content = excluded.content,
                   hashtags = excluded.hashtags,
                   expires_at = excluded.expires_at,
                   created_at = excluded.created_at""",
            (key, f"{len(variants)} variants cached", payload,
             expires_at, time.time()),
        )


# ---- Public entry point ---------------------------------------------------


def generate(req: CaptionRequest | None = None,
             *,
             product: dict[str, Any] | None = None,
             template: dict[str, Any] | None = None,
             brand: dict[str, Any] | None = None,
             platform: str = "instagram",
             model: str = "heuristic",
             count: int = 3) -> list[CaptionVariant]:
    """Generate ``count`` CaptionVariant objects for the given inputs.

    Accepts either a CaptionRequest or keyword args (the keyword form is
    exposed so callers that don't want to construct the dataclass can still
    use the generator).
    """
    if req is None:
        req = CaptionRequest(
            product=product or {},
            template=template or {},
            brand=brand,
            platform=platform,
            model=model,
        )
    if req.platform not in VALID_PLATFORMS:
        raise ValueError(f"unsupported platform: {req.platform}")

    cached = _cache_get(req.key)
    if cached:
        return _apply_banned(req, [CaptionVariant(**v) for v in cached])

    if req.model == "llm":
        variants = _llm_variants(req, count=count)
        if not variants:
            variants = _heuristic(req, count=count)
    else:
        variants = _heuristic(req, count=count)

    variants = _apply_banned(req, variants)
    _cache_put(req.key, variants)
    return variants


# ---- Persistence helpers (used by server.py to mark selections) --------


def persist_selection(*, output_id: int, variant: CaptionVariant,
                      platform: str, brand_id: int | None = None,
                      template_id: int | None = None,
                      product_id: int | None = None) -> int:
    """Insert a caption row marked as the selected one for an output."""
    with app_db.connect() as c:
        if output_id:
            c.execute(
                "UPDATE captions SET is_selected = 0 WHERE output_id = ?",
                (output_id,),
            )
        # Find the next variant_index for this output (1-based; 0 is reserved
        # for the cache row).
        next_idx = 1
        if output_id:
            row = c.execute(
                "SELECT COALESCE(MAX(variant_index), 0) FROM captions WHERE output_id = ?",
                (output_id,),
            ).fetchone()
            next_idx = int(row[0]) + 1 if int(row[0]) >= 1 else 1
        cur = c.execute(
            """INSERT INTO captions
               (output_id, platform, variant_index, content, hashtags,
                first_comment, alt_text, is_selected,
                brand_id, template_id, product_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (
                output_id or None,
                platform,
                next_idx,
                variant.content,
                json.dumps(variant.hashtags),
                variant.first_comment,
                variant.alt_text,
                brand_id,
                template_id,
                product_id,
                time.time(),
            ),
        )
    return int(cur.lastrowid)


def list_for_output(output_id: int) -> list[dict[str, Any]]:
    with app_db.connect() as c:
        rows = c.execute(
            """SELECT id, platform, variant_index, content, hashtags,
                      first_comment, alt_text, is_selected, created_at
               FROM captions WHERE output_id = ?
               ORDER BY created_at DESC""",
            (output_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": int(r[0]),
                "platform": r[1],
                "variant_index": int(r[2]),
                "content": r[3],
                "hashtags": json.loads(r[4] or "[]"),
                "first_comment": r[5],
                "alt_text": r[6],
                "is_selected": bool(r[7]),
                "created_at": float(r[8]),
            }
        )
    return out