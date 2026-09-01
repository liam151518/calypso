"""Variant generator. One reference to multiple generation variants.

Per the Phase 4 optimization: for each pick, generate N variants with different
prompts/captions/aspect ratios. The Telegram approval message shows N
thumbnails; user picks the best. The other N-1 get archived with the reason.

Variants:
- Variant 0: original aspect ratio (1:1), standard caption
- Variant 1: 9:16 aspect (vertical, IG Stories / TikTok), shorter caption
- Variant 2: 16:9 aspect (horizontal, X), longer caption with hashtags

Tests: tests/test_variant_generator.py
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent

AspectRatio = Literal["1:1", "9:16", "16:9"]


@dataclass(frozen=True)
class Variant:
    """One variant of a generation."""

    index: int
    aspect_ratio: AspectRatio
    width: int
    height: int
    caption_suffix: str
    style_tags: list[str]
    motion_intensity: float  # 0.0 = still, 1.0 = high motion


# Canonical variant recipes per the plan
VARIANT_RECIPES = [
    Variant(
        index=0,
        aspect_ratio="1:1",
        width=1024,
        height=1024,
        caption_suffix="",
        style_tags=[],
        motion_intensity=0.5,
    ),
    Variant(
        index=1,
        aspect_ratio="9:16",
        width=768,
        height=1344,
        caption_suffix=" #gacha #capsuletoy",
        style_tags=["vertical_composition"],
        motion_intensity=0.7,
    ),
    Variant(
        index=2,
        aspect_ratio="16:9",
        width=1344,
        height=768,
        caption_suffix=" #GatchaKingdom #johannesburg",
        style_tags=["wide_composition"],
        motion_intensity=0.3,
    ),
]


def get_variants() -> list[Variant]:
    """Return the canonical 3-variant set."""
    return list(VARIANT_RECIPES)


def generate_variant_prompts(
    base_prompt: str,
    base_style_tags: list[str],
    rng: random.Random | None = None,
) -> list[dict]:
    """Generate 3 variant prompt configs based on a base prompt.

    Returns a list of dicts, each containing:
    - variant_index
    - aspect_ratio, width, height
    - prompt (modified from base)
    - style_tags (base + variant-specific)
    - caption_suffix
    """
    rng = rng or random.Random()
    variants = get_variants()
    out = []
    for v in variants:
        prompt_parts = [base_prompt]
        if v.style_tags:
            prompt_parts.append(", ".join(v.style_tags))
        # Adjust motion language based on variant
        if v.motion_intensity > 0.6:
            prompt_parts.append("dynamic motion")
        elif v.motion_intensity < 0.4:
            prompt_parts.append("subtle motion, still composition")
        # Aspect hint
        if v.aspect_ratio == "9:16":
            prompt_parts.append("vertical composition, tall frame")
        elif v.aspect_ratio == "16:9":
            prompt_parts.append("wide composition, cinematic frame")

        out.append({
            "variant_index": v.index,
            "aspect_ratio": v.aspect_ratio,
            "width": v.width,
            "height": v.height,
            "prompt": ", ".join(prompt_parts),
            "style_tags": list(base_style_tags) + list(v.style_tags),
            "caption_suffix": v.caption_suffix,
            "motion_intensity": v.motion_intensity,
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate variant prompts.")
    parser.add_argument("--base-prompt", required=True, help="Base prompt to vary")
    parser.add_argument("--style-tags", default="", help="Comma-separated style tags")
    parser.add_argument("--seed", type=int, help="Seed RNG for reproducibility")
    args = parser.parse_args()

    rng = random.Random(args.seed) if args.seed is not None else None
    style_tags = [t.strip() for t in args.style_tags.split(",") if t.strip()]
    variants = generate_variant_prompts(args.base_prompt, style_tags, rng=rng)
    print(json.dumps(variants, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
