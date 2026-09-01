"""app/models.py. Registry of fal.ai models supported by Calypso.

Each entry has a `category` (video | image), a fal.ai endpoint id, a display
name, supported resolutions / aspect ratios / durations, and a per-second
cost table the SPA can use for live estimates.

The hardcoded top-10 is the source of truth for offline use; `list_models()`
also opportunistically queries fal.ai's public models endpoint to enrich the
list with anything currently available. The merged list is cached in
module-level memory so the SPA doesn't re-fetch on every request.

    Used by: app/server.py (/api/models, /api/cost-estimate), app/jobs.py.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Literal

ModelCategory = Literal["video", "image"]


@dataclass(frozen=True)
class ModelSpec:
    """Description of a single fal.ai model we can route to."""

    id: str  # fal.ai endpoint, e.g. "minimax/h3-max"
    name: str  # human display name, e.g. "MiniMax H3 Max"
    category: ModelCategory
    vendor: str  # "MiniMax", "Kuaishou", "OpenAI", ...
    description: str = ""
    # Video-specific knobs (empty for image models).
    durations: tuple[int, ...] = field(default_factory=tuple)
    resolutions: tuple[str, ...] = field(default_factory=tuple)
    # Image-specific knobs (empty for video models).
    aspect_ratios: tuple[str, ...] = field(default_factory=tuple)
    # Per-second USD cost (video). Image models use per_image_usd.
    per_second_usd: dict[str, float] = field(default_factory=dict)
    per_image_usd: float = 0.0
    # Marketing flags shown to the operator in the picker.
    badge: str = ""  # "fastest", "highest quality", "cinematic", etc.
    is_default: bool = False


# Top-10 curated list. IDs match the fal.ai endpoint paths.
TOP_MODELS: tuple[ModelSpec, ...] = (
    # ---- Video models ----
    ModelSpec(
        id="minimax/h3",
        name="MiniMax H3",
        category="video",
        vendor="MiniMax",
        description="Reference-driven cinematic video. Best for product reveals with strong brand DNA.",
        durations=(4, 6, 8, 10, 12),
        resolutions=("480p", "768p", "1080p"),
        per_second_usd={"480p": 0.025, "768p": 0.045, "1080p": 0.075},
        badge="default",
        is_default=True,
    ),
    ModelSpec(
        id="minimax/h3-max",
        name="MiniMax H3 Max",
        category="video",
        vendor="MiniMax",
        description="Higher fidelity variant of H3. Best for hero shots.",
        durations=(4, 6, 8, 10, 12),
        resolutions=("480p", "768p", "1080p"),
        per_second_usd={"480p": 0.03, "768p": 0.05, "1080p": 0.08},
        badge="cinematic",
    ),
    ModelSpec(
        id="kling-video/v2.6/pro",
        name="Kling 2.6 Pro",
        category="video",
        vendor="Kuaishou",
        description="Strong motion. Great for fight scenes, hands, cloth.",
        durations=(5, 10),
        resolutions=("480p", "768p", "1080p"),
        per_second_usd={"480p": 0.05, "768p": 0.07, "1080p": 0.10},
        badge="strong motion",
    ),
    ModelSpec(
        id="veo3",
        name="Google Veo 3",
        category="video",
        vendor="Google",
        description="Photorealistic, 8-second clips, native audio when available.",
        durations=(8,),
        resolutions=("720p", "1080p"),
        per_second_usd={"720p": 0.12, "1080p": 0.18},
        badge="photorealistic",
    ),
    ModelSpec(
        id="sora-2",
        name="OpenAI Sora 2",
        category="video",
        vendor="OpenAI",
        description="Strong world physics and prompt adherence.",
        durations=(4, 8, 12),
        resolutions=("480p", "720p", "1080p"),
        per_second_usd={"480p": 0.08, "720p": 0.10, "1080p": 0.15},
        badge="physics",
    ),
    ModelSpec(
        id="runway/gen-4-turbo",
        name="Runway Gen-4 Turbo",
        category="video",
        vendor="Runway",
        description="Fast iteration. Good for previz / pre-roll.",
        durations=(5, 10),
        resolutions=("480p", "720p", "1080p"),
        per_second_usd={"480p": 0.04, "720p": 0.06, "1080p": 0.09},
        badge="fastest",
    ),
    ModelSpec(
        id="wan/v2.1",
        name="Wan 2.1",
        category="video",
        vendor="Alibaba",
        description="Open-weights flavour, good for anime / stylized work.",
        durations=(4, 8),
        resolutions=("480p", "720p"),
        per_second_usd={"480p": 0.02, "720p": 0.035},
        badge="stylized",
    ),
    ModelSpec(
        id="ltx-video",
        name="LTX Video",
        category="video",
        vendor="Lightricks",
        description="Fast, lightweight, good for in-between cuts.",
        durations=(4, 6, 8),
        resolutions=("480p", "720p"),
        per_second_usd={"480p": 0.015, "720p": 0.025},
        badge="lightweight",
    ),
    # ---- Image models ----
    ModelSpec(
        id="flux-pro/v1.1",
        name="Flux Pro 1.1",
        category="image",
        vendor="Black Forest Labs",
        description="Photorealistic product imagery. Best default for Gacha Luka key art.",
        aspect_ratios=("1:1", "16:9", "9:16", "4:3", "3:4"),
        per_image_usd=0.05,
        badge="default",
        is_default=True,
    ),
    ModelSpec(
        id="imagen-3",
        name="Google Imagen 3",
        category="image",
        vendor="Google",
        description="Strong typography and brand-safe compositions.",
        aspect_ratios=("1:1", "16:9", "9:16", "4:3", "3:4"),
        per_image_usd=0.04,
        badge="typography",
    ),
    ModelSpec(
        id="recraft/v3",
        name="Recraft v3",
        category="image",
        vendor="Recraft",
        description="Vector-style and brand illustration work.",
        aspect_ratios=("1:1", "16:9", "9:16"),
        per_image_usd=0.03,
        badge="vector",
    ),
    ModelSpec(
        id="sdxl",
        name="SDXL",
        category="image",
        vendor="Stability",
        description="Cheapest baseline. Good for placeholder drafts.",
        aspect_ratios=("1:1", "16:9", "9:16"),
        per_image_usd=0.015,
        badge="cheapest",
    ),
)

_BY_ID: dict[str, ModelSpec] = {m.id: m for m in TOP_MODELS}

# Merge cache: when we hit the fal.ai endpoint and discover more models,
# they get appended here so subsequent calls are fast.
_MERGE_CACHE: list[ModelSpec] = []
_MERGE_TTL_SECONDS = 60 * 60  # 1 hour
_LAST_FETCH = 0.0


def _fetch_fal_models(api_key: str | None, timeout: float = 3.0) -> list[ModelSpec]:
    """Best-effort fetch of fal.ai's models endpoint.

    Returns an empty list on any failure (network, auth, parse). The hardcoded
    top-10 always remains the source of truth. Anything returned here is
    only used to enrich the picker with availability hints.
    """
    if not api_key:
        return []
    url = "https://fal.ai/api/models?categories=video,image&limit=40"
    try:
        req = urllib.request.Request(
            url, headers={"Authorization": f"Key {api_key}", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError, OSError):
        return []

    out: list[ModelSpec] = []
    for entry in data.get("models", []) if isinstance(data, dict) else []:
        endpoint = entry.get("endpoint_id") or entry.get("id")
        if not endpoint or endpoint in _BY_ID:
            continue
        category = "image" if "image" in str(entry.get("categories", "")).lower() else "video"
        out.append(
            ModelSpec(
                id=str(endpoint),
                name=str(entry.get("display_name") or entry.get("title") or endpoint),
                category=category,
                vendor=str(entry.get("publisher") or "fal.ai"),
                description=str(entry.get("description") or ""),
            )
        )
    return out[:8]  # cap enrichment so the picker doesn't explode


def _refresh_cache(api_key: str | None) -> None:
    global _MERGE_CACHE, _LAST_FETCH
    now = time.time()
    if now - _LAST_FETCH < _MERGE_TTL_SECONDS:
        return
    _MERGE_CACHE = _fetch_fal_models(api_key)
    _LAST_FETCH = now


def list_models(api_key: str | None = None) -> list[dict]:
    """Return the merged model list as plain dicts for JSON serialisation."""
    _refresh_cache(api_key)
    out = [asdict(m) for m in TOP_MODELS]
    for extra in _MERGE_CACHE:
        out.append(asdict(extra))
    return out


def get_model(model_id: str) -> ModelSpec | None:
    """Return a model by id, or None if unknown."""
    return _BY_ID.get(model_id)


def estimate_cost(
    model_id: str,
    *,
    duration: int | None = None,
    resolution: str | None = None,
    aspect_ratio: str | None = None,
    num_images: int = 1,
) -> dict:
    """Return {usd, model_id, category, inputs} for a given request.

    Falls back to a sensible default (0.05 USD) when the model or knob is
    unknown, so the SPA still renders an estimate rather than NaN.
    """
    spec = _BY_ID.get(model_id)
    if spec is None:
        return {"usd": 0.05, "model_id": model_id, "category": "video", "note": "unknown model"}

    if spec.category == "video":
        dur = duration if duration in spec.durations else (spec.durations[len(spec.durations) // 2] if spec.durations else 8)
        res = resolution if resolution in spec.resolutions else (spec.resolutions[0] if spec.resolutions else "768p")
        rate = spec.per_second_usd.get(res, 0.05)
        return {
            "usd": round(rate * dur, 4),
            "model_id": model_id,
            "category": "video",
            "duration": dur,
            "resolution": res,
        }

    # image
    ar = aspect_ratio if aspect_ratio in spec.aspect_ratios else (spec.aspect_ratios[0] if spec.aspect_ratios else "1:1")
    return {
        "usd": round(spec.per_image_usd * max(1, num_images), 4),
        "model_id": model_id,
        "category": "image",
        "aspect_ratio": ar,
        "num_images": num_images,
    }


def video_models(api_key: str | None = None) -> list[dict]:
    return [m for m in list_models(api_key) if m["category"] == "video"]


def image_models(api_key: str | None = None) -> list[dict]:
    return [m for m in list_models(api_key) if m["category"] == "image"]


def default_video_model_id() -> str:
    for m in TOP_MODELS:
        if m.category == "video" and m.is_default:
            return m.id
    return "auto"


def default_image_model_id() -> str:
    for m in TOP_MODELS:
        if m.category == "image" and m.is_default:
            return m.id
    return "flux-pro/v1.1"
