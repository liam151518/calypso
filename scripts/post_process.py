"""Post-process a generated image: watermark + text overlay + color grade.

Takes an image path, applies:
1. Optional brand color grade (push midtones toward the Gatcha pink)
2. Watermark overlay (logo at low opacity, bottom-right)
3. Optional text overlay (the post caption, large bold)

Saves the output and returns the path.

Tests: tests/test_post_process.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageColor, ImageEnhance, ImageFilter, ImageFont, ImageOps

REPO_ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = REPO_ROOT / "brand"
DEFAULT_WATERMARK = BRAND_DIR / "logo" / "GK_Logo_128.png"
DEFAULT_BRAND_PINK = "#FF5E7E"


@dataclass(frozen=True)
class WatermarkConfig:
    logo_path: Path = DEFAULT_WATERMARK
    opacity: float = 0.12
    position: str = "bottom-right"  # bottom-right | bottom-left | top-right | top-left
    margin_px: int = 24


@dataclass(frozen=True)
class TextOverlayConfig:
    text: str
    font_path: Path | None = None
    font_size: int = 56
    color: str = "#FFFFFF"
    stroke_color: str = "#1E1E2F"
    stroke_width: int = 4
    position: str = "bottom-center"  # bottom-center | top-center | center


def _load_font(font_path: Path | None, size: int) -> ImageFont.FreeTypeFont:
    """Load a font, falling back to default if not found."""
    if font_path and font_path.exists():
        return ImageFont.truetype(str(font_path), size=size)
    # Pillow's default font can't size; use load_default with a size hint
    try:
        return ImageFont.truetype("Arial.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def apply_watermark(image: Image.Image, config: WatermarkConfig | None = None) -> Image.Image:
    """Overlay the brand watermark at low opacity. Returns a new image."""
    config = config or WatermarkConfig()
    if not config.logo_path.exists():
        return image

    logo = Image.open(config.logo_path).convert("RGBA")
    # Apply opacity
    alpha = logo.split()[3]
    alpha = alpha.point(lambda p: int(p * config.opacity))
    logo.putalpha(alpha)

    # Scale logo to ~12% of image width
    target_w = max(48, int(image.width * 0.12))
    scale = target_w / logo.width
    target_h = max(48, int(logo.height * scale))
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # Compute position
    margin = config.margin_px
    if config.position == "bottom-right":
        x = image.width - logo.width - margin
        y = image.height - logo.height - margin
    elif config.position == "bottom-left":
        x = margin
        y = image.height - logo.height - margin
    elif config.position == "top-right":
        x = image.width - logo.width - margin
        y = margin
    elif config.position == "top-left":
        x = margin
        y = margin
    else:
        x = image.width - logo.width - margin
        y = image.height - logo.height - margin

    base = image.convert("RGBA")
    base.paste(logo, (x, y), logo)
    return base.convert("RGB")


def apply_text_overlay(image: Image.Image, config: TextOverlayConfig) -> Image.Image:
    """Render text with stroke. Returns a new image."""
    from PIL import ImageDraw

    font = _load_font(config.font_path, config.font_size)
    draw_image = image.convert("RGBA")
    overlay = Image.new("RGBA", draw_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Measure text
    bbox = draw.textbbox((0, 0), config.text, font=font, stroke_width=config.stroke_width)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Position
    margin = 32
    if config.position == "bottom-center":
        x = (draw_image.width - text_w) // 2
        y = draw_image.height - text_h - margin
    elif config.position == "top-center":
        x = (draw_image.width - text_w) // 2
        y = margin
    else:  # center
        x = (draw_image.width - text_w) // 2
        y = (draw_image.height - text_h) // 2

    # Draw with stroke for legibility
    draw.text(
        (x, y),
        config.text,
        font=font,
        fill=config.color,
        stroke_width=config.stroke_width,
        stroke_fill=config.stroke_color,
    )

    combined = Image.alpha_composite(draw_image, overlay)
    return combined.convert("RGB")


def apply_brand_grade(image: Image.Image, brand_color: str = DEFAULT_BRAND_PINK) -> Image.Image:
    """Subtly push midtones toward the brand color. Returns a new image."""
    # Convert hex to RGB tuple
    rgb = ImageColor.getrgb(brand_color)
    # Apply a tiny saturation boost + a color overlay at 5% opacity
    enhancer = ImageEnhance.Color(image)
    saturated = enhancer.enhance(1.05)  # +5% saturation

    # Tint overlay
    tint = Image.new("RGB", saturated.size, rgb)
    blended = Image.blend(saturated.convert("RGB"), tint, alpha=0.05)
    return blended


def process(
    image_path: Path,
    output_path: Path,
    *,
    caption: str | None = None,
    watermark: WatermarkConfig | None = None,
    brand_grade: bool = True,
    font_path: Path | None = None,
) -> Path:
    """Full pipeline: load → grade → watermark → text overlay → save."""
    image = Image.open(image_path).convert("RGB")
    if brand_grade:
        image = apply_brand_grade(image)
    image = apply_watermark(image, watermark or WatermarkConfig())
    if caption:
        image = apply_text_overlay(
            image,
            TextOverlayConfig(text=caption, font_path=font_path),
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "JPEG", quality=92)
    return output_path


# ---------- CLI ----------

def _cli() -> int:
    parser = argparse.ArgumentParser(description="Post-process a generated image.")
    parser.add_argument("input", type=Path, help="Input image path")
    parser.add_argument("output", type=Path, help="Output image path")
    parser.add_argument("--caption", help="Optional text overlay")
    parser.add_argument("--no-brand-grade", action="store_true", help="Skip brand color grade")
    parser.add_argument("--font", type=Path, help="Path to brand font file")
    args = parser.parse_args()

    result = process(
        args.input,
        args.output,
        caption=args.caption,
        brand_grade=not args.no_brand_grade,
        font_path=args.font,
    )
    print(f"saved: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
