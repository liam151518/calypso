"""Prompt builder — assembles the generation prompt from a reference + brand voice.

Given a reference (style tags, theme, composition, audio trend) and a brand
voice (from brand/captions/reference_captions.json), assembles:
- A ComfyUI positive prompt (what to generate)
- A ComfyUI negative prompt (what to avoid)
- A caption for the social post (uses brand voice terms)
- Optional motion description (for video pipelines)

Tests: tests/test_prompt_builder.py
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
CAPTIONS_FILE = REPO_ROOT / "brand" / "captions" / "reference_captions.json"

# Negative prompt base — anything in here is anti-brand or low quality.
NEGATIVE_BASE = [
    "blurry", "low quality", "worst quality", "jpeg artifacts",
    "watermark", "signature", "username",
    "text", "typography", "logo overlay", "stock photo",
    "deformed hands", "extra fingers", "missing fingers",
    "bad anatomy", "twisted limbs",
    "gambling", "casino", "dice", "cards", "slot machine",
    "money", "cash", "betting odds", "jackpot", "prize", "lucky draw",
]

# Caption template fragments — pick one to anchor the structure.
CAPTION_TEMPLATES = {
    "pull_reaction": [
        "just pulled a {cabinet_color} {figure_name} I didn't even know was in this drop",
        "the {figure_name} reveal hit different",
    ],
    "cabinet_hype": [
        "{cabinet_color} cabinet restocked. someone please go pull before I burn my wallet down again",
    ],
    "tier_list": [
        "new tier list up. {take} tier is honestly fewer figures than I expected — the {figure_name} carries harder than people think",
    ],
    "set_completion": [
        "{progress} on the {drop_name} drop. {remaining} more and I can stop refreshing at 2am",
    ],
    "irl_cabinet": [
        "checked in at the {location} cabinet today. {result}",
    ],
    "restock_alert": [
        "{cabinet_color} cabinet restocked at {location}. the {figure_name} set has been sold out for {weeks} weeks. go. now",
    ],
}

CABINET_COLORS = ["pink", "blue", "damascus", "orange", "purple", "red", "white", "yellow", "black"]


@dataclass(frozen=True)
class Prompt:
    """The output of the prompt builder — fed into ComfyUI + the social caption."""

    positive: str
    negative: str
    caption: str
    theme: str
    style_tags: list[str]
    motion: str | None = None  # for video pipelines
    metadata: dict = field(default_factory=dict)


def _load_caption_examples() -> list[dict]:
    """Load curated caption examples. Falls back to empty list if file missing."""
    if not CAPTIONS_FILE.exists():
        return []
    try:
        data = json.loads(CAPTIONS_FILE.read_text())
        return data.get("captions", [])
    except (json.JSONDecodeError, OSError):
        return []


def _positive_base(reference_style_tags: Iterable[str], theme: str) -> str:
    """Build the ComfyUI positive prompt from style tags."""
    tags = list(reference_style_tags) or ["cinematic", "high quality", "sharp focus"]
    # Brand anchors — these always appear so we don't drift
    anchors = [
        "gacha capsule toy",
        "Japanese capsule machine",
        "neon-lit arcade",
        "warm white background",
        "pink and cyan accent lighting",
    ]
    # Theme-specific framing
    theme_frame = {
        "pull_reaction": "capturing the reveal moment, hand on chest reaction, excitement",
        "cabinet_hype": "hero shot of a colorful capsule machine, slight low angle, vibrant",
        "tier_list": "character ranking card, clean typography, side-by-side comparison",
        "set_completion": "collection shelf, figures arranged in a grid, completionist vibe",
        "irl_cabinet": "real cabinet in a mall setting, natural lighting, candid",
        "restock_alert": "fully stocked capsule machine, bright neon glow, \"in stock\" energy",
        "rare_drop": "single figure highlighted, dramatic rim lighting, museum shot",
        "mascot": "maneki-neko capsule toy, cute and chibi, kawaii style",
        "event_hype": "limited-edition cabinet, holographic accents, hype energy",
    }
    return ", ".join([*anchors, theme_frame.get(theme, "vibrant gacha scene"), *tags])


def _build_caption(theme: str, rng: random.Random | None = None) -> str:
    """Pick a caption template for the theme and fill with placeholders.

    The placeholders are intentionally kept as {cabinet_color} etc. so a
    later step (or Adam) can fill them in with real values. For now this
    returns a structurally complete caption.
    """
    rng = rng or random.Random()
    templates = CAPTION_TEMPLATES.get(theme, [])
    if not templates:
        return "new drop just landed. check the tier list."

    template = rng.choice(templates)
    # Fill basic placeholders with random values — Adam or the operator
    # can replace these with real, contextually-aware values later.
    return template.format(
        cabinet_color=rng.choice(CABINET_COLORS),
        figure_name=rng.choice(["Damascus figure", "pink-cabinet figure", "rare S-tier drop", "Spring drop figure"]),
        take=rng.choice(["S", "A", "B"]),
        progress=f"{rng.randint(8, 14)}/{rng.choice([16, 18, 20])}",
        drop_name=rng.choice(["Spring", "Summer", "Autumn", "Winter", "Damascus", "Anniversary"]),
        remaining=rng.randint(2, 6),
        location=rng.choice(["Rosebank", "the Sandton mall", "the Cape Town pop-up"]),
        weeks=rng.randint(2, 6),
        result=rng.choice([
            "free spin for the QR check-in. pulled something I would've skipped online",
            "the floor knows. pulled a yellow-tier figure and walked out feeling like I robbed them",
        ]),
    )


def build(
    reference: dict,
    *,
    brand_color: str = "#FF5E7E",
    rng: random.Random | None = None,
    include_motion: bool = False,
) -> Prompt:
    """Build a Prompt from a reference dict (loaded from references/ready/*.json).

    Args:
        reference: dict with keys: theme, style_tags, composition, audio_trend, format
        brand_color: hex string for color anchor
        rng: optional random number generator for reproducible picks
        include_motion: if True, populate the `motion` field for video pipelines

    Returns:
        Prompt object with positive/negative/caption/style_tags/motion
    """
    rng = rng or random.Random()
    theme = reference.get("theme", "")
    style_tags = list(reference.get("style_tags", []))
    composition = reference.get("composition", "")

    positive = _positive_base(style_tags, theme)
    # Add composition hint if present
    if composition:
        positive = f"{positive}, {composition} framing"

    negative = ", ".join(NEGATIVE_BASE + [f"{tag} only" for tag in style_tags if tag in ("low quality", "blurry")])
    caption = _build_caption(theme, rng=rng)

    motion: str | None = None
    if include_motion:
        motion = _build_motion(theme, rng=rng)

    return Prompt(
        positive=positive,
        negative=negative,
        caption=caption,
        theme=theme,
        style_tags=style_tags,
        motion=motion,
        metadata={
            "brand_color": brand_color,
            "composition": composition,
            "audio_trend": reference.get("audio_trend", ""),
        },
    )


def _build_motion(theme: str, rng: random.Random | None = None) -> str:
    """Build a motion description for video pipelines."""
    rng = rng or random.Random()
    motions = {
        "pull_reaction": "camera pushes in slowly, capsule cracks open, light burst on reveal",
        "cabinet_hype": "sweeping pan across the cabinet, lights flicker on one by one",
        "tier_list": "scroll down a ranked list, the top character zooms in",
        "set_completion": "figures slide into place on a shelf, the missing slot pulses",
        "irl_cabinet": "handheld walk toward the machine, QR scan moment, capsule drop",
        "restock_alert": "machine hums to life, capsules rattle, neon glow intensifies",
        "rare_drop": "slow-motion figure rotation with rim light, dramatic reveal",
        "mascot": "mascot waves, then bounces off-screen",
        "event_hype": "holographic text appears, cabinets rotate in a circle",
    }
    return motions.get(theme, "gentle camera push-in, soft ambient motion")


# ---------- CLI ----------

def _cli() -> int:
    parser = argparse.ArgumentParser(description="Build a generation prompt from a reference.")
    parser.add_argument("--reference", type=Path, required=True, help="Path to reference JSON")
    parser.add_argument("--seed", type=int, help="Seed RNG for reproducible prompts")
    parser.add_argument("--motion", action="store_true", help="Include motion description (for video)")
    args = parser.parse_args()

    if not args.reference.exists():
        print(f"reference file not found: {args.reference}", file=sys.stderr)
        return 1

    rng = random.Random(args.seed) if args.seed is not None else None
    reference = json.loads(args.reference.read_text())
    prompt = build(reference, rng=rng, include_motion=args.motion)

    print(json.dumps({
        "positive": prompt.positive,
        "negative": prompt.negative,
        "caption": prompt.caption,
        "theme": prompt.theme,
        "style_tags": prompt.style_tags,
        "motion": prompt.motion,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
