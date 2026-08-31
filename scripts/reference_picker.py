"""Reference picker for Folder A.

Weighted random selection over `references/ready/*.json`. A-tier references
get 3x the weight of B-tier, B-tier 3x of C-tier. The picker respects an
optional `style_filter` and `format_filter` so the pipeline can constrain
by what it needs (e.g., "give me a dark_moody video reference").

Used by:
- Phase 2 n8n workflow (image generation cron)
- Phase 3 n8n workflow (video generation cron)
- Manual `python -m scripts.reference_picker` for one-off picks during curation

Tests: tests/test_reference_picker.py
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
READY_DIR = REPO_ROOT / "references" / "ready"

# Default weighting: A-tier 3x, B-tier 1x, C-tier 0.33x, unrated 1x
DEFAULT_WEIGHTS: dict[str, float] = {
    "A": 3.0,
    "B": 1.0,
    "C": 0.33,
    "": 1.0,
}


@dataclass(frozen=True)
class Reference:
    """A single reference asset + its metadata."""

    path: Path
    asset_path: Path
    source: str
    source_url: str
    platform: str
    format: str  # image | video | carousel
    theme: str
    engagement_tier: str  # A | B | C | "" (unrated)
    style_tags: list[str] = field(default_factory=list)
    composition: str = ""
    audio_trend: str = ""

    @classmethod
    def from_json(cls, path: Path) -> "Reference":
        data = json.loads(path.read_text())
        asset_rel = data.get("asset_path") or data.get("source_url") or ""
        asset_path = (path.parent / asset_rel) if not asset_rel.startswith("http") else Path(asset_rel)
        return cls(
            path=path,
            asset_path=asset_path,
            source=data.get("source", ""),
            source_url=data.get("source_url", ""),
            platform=data.get("platform", ""),
            format=data.get("format", ""),
            theme=data.get("theme", ""),
            engagement_tier=data.get("engagement_tier", ""),
            style_tags=list(data.get("style_tags", [])),
            composition=data.get("composition", ""),
            audio_trend=data.get("audio_trend", ""),
        )


def load_references(ready_dir: Path | None = None) -> list[Reference]:
    """Load all A/B/C-tier references from references/ready/.

    `ready_dir` defaults to READY_DIR at call time (so tests can monkeypatch
    the module attribute and have it take effect).
    """
    if ready_dir is None:
        ready_dir = READY_DIR
    if not ready_dir.exists():
        return []
    refs: list[Reference] = []
    for path in sorted(ready_dir.glob("*.json")):
        try:
            refs.append(Reference.from_json(path))
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            print(f"[reference_picker] skipping {path.name}: {exc}", file=sys.stderr)
    return refs


def filter_references(
    refs: Iterable[Reference],
    *,
    format: str | None = None,
    style_tag: str | None = None,
    platform: str | None = None,
) -> list[Reference]:
    """Apply optional filters to a reference list."""
    out = list(refs)
    if format:
        out = [r for r in out if r.format == format]
    if style_tag:
        out = [r for r in out if style_tag in r.style_tags]
    if platform:
        out = [r for r in out if r.platform == platform]
    return out


def weighted_pick(
    refs: list[Reference],
    *,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    rng: random.Random | None = None,
) -> Reference:
    """Pick one reference using weighted random over engagement_tier."""
    if not refs:
        raise ValueError("no references to pick from")

    rng = rng or random.Random()
    pool = [r for r in refs if r.engagement_tier in weights]
    if not pool:
        pool = refs

    weights_list = [weights.get(r.engagement_tier, 1.0) for r in pool]
    return rng.choices(pool, weights=weights_list, k=1)[0]


def pick(
    *,
    format: str | None = None,
    style_tag: str | None = None,
    platform: str | None = None,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    rng: random.Random | None = None,
) -> Reference:
    """Top-level convenience: load + filter + pick."""
    refs = load_references()
    refs = filter_references(refs, format=format, style_tag=style_tag, platform=platform)
    return weighted_pick(refs, weights=weights, rng=rng)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Pick a Folder A reference (weighted random).")
    parser.add_argument("--format", choices=["image", "video", "carousel"], help="Filter by format")
    parser.add_argument("--style-tag", help="Filter by style tag (e.g., dark_moody)")
    parser.add_argument("--platform", choices=["x", "instagram", "tiktok", "reddit"], help="Filter by platform")
    parser.add_argument("--seed", type=int, help="Seed RNG for reproducible picks")
    args = parser.parse_args()

    rng = random.Random(args.seed) if args.seed is not None else None
    try:
        ref = pick(format=args.format, style_tag=args.style_tag, platform=args.platform, rng=rng)
    except ValueError as exc:
        print(f"[reference_picker] {exc}", file=sys.stderr)
        return 1

    print(json.dumps({
        "asset_path": str(ref.asset_path),
        "platform": ref.platform,
        "format": ref.format,
        "theme": ref.theme,
        "engagement_tier": ref.engagement_tier,
        "style_tags": ref.style_tags,
        "composition": ref.composition,
        "audio_trend": ref.audio_trend,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
