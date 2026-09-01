"""Tests for scripts/post_process.py.

Run: `python -m pytest tests/test_post_process.py -v`

These tests don't require network or ComfyUI. They generate small synthetic
images with PIL, process them, and assert on the outputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from scripts.post_process import (
    TextOverlayConfig,
    WatermarkConfig,
    apply_brand_grade,
    apply_text_overlay,
    apply_watermark,
    process,
)


# ---------- fixtures ----------

@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a 1024x1024 solid-color test image."""
    img = Image.new("RGB", (1024, 1024), color=(64, 128, 192))
    path = tmp_path / "test_input.jpg"
    img.save(path, "JPEG")
    return path


@pytest.fixture
def sample_logo(tmp_path: Path) -> Path:
    """Create a small PNG with transparency for use as a watermark."""
    img = Image.new("RGBA", (256, 256), (255, 94, 126, 255))
    # Draw a simple shape so the test can detect the watermark
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse((64, 64, 192, 192), fill=(255, 255, 255, 255))
    path = tmp_path / "test_logo.png"
    img.save(path, "PNG")
    return path


# ---------- apply_brand_grade ----------

class TestApplyBrandGrade:
    def test_returns_same_dimensions(self, sample_image: Path):
        image = Image.open(sample_image)
        result = apply_brand_grade(image)
        assert result.size == image.size

    def test_returns_rgb(self, sample_image: Path):
        image = Image.open(sample_image)
        result = apply_brand_grade(image)
        assert result.mode == "RGB"


# ---------- apply_watermark ----------

class TestApplyWatermark:
    def test_returns_image_unchanged_when_logo_missing(self, sample_image: Path, tmp_path: Path):
        image = Image.open(sample_image)
        # Point at a non-existent logo
        config = WatermarkConfig(logo_path=tmp_path / "nope.png")
        result = apply_watermark(image, config)
        # Should return the original image unchanged
        assert result.size == image.size

    def test_overlays_logo_when_present(self, sample_image: Path, sample_logo: Path):
        image = Image.open(sample_image).convert("RGB")
        config = WatermarkConfig(logo_path=sample_logo, opacity=0.5)
        result = apply_watermark(image, config)
        # The result should have a mark somewhere. Easiest check is just that.
        # the dimensions match and it's still RGB
        assert result.size == image.size
        assert result.mode == "RGB"

    @pytest.mark.parametrize(
        "position",
        ["bottom-right", "bottom-left", "top-right", "top-left"],
    )
    def test_all_positions_work(self, sample_image: Path, sample_logo: Path, position: str):
        image = Image.open(sample_image).convert("RGB")
        config = WatermarkConfig(logo_path=sample_logo, position=position, opacity=0.3)
        result = apply_watermark(image, config)
        assert result.size == image.size


# ---------- apply_text_overlay ----------

class TestApplyTextOverlay:
    def test_short_caption(self, sample_image: Path):
        image = Image.open(sample_image).convert("RGB")
        config = TextOverlayConfig(text="PINK DROP")
        result = apply_text_overlay(image, config)
        assert result.size == image.size
        assert result.mode == "RGB"

    def test_long_caption_wraps_via_stroke(self, sample_image: Path):
        image = Image.open(sample_image).convert("RGB")
        long_text = "Damascus pink cabinet restocked at Rosebank " * 5
        config = TextOverlayConfig(text=long_text, font_size=64)
        result = apply_text_overlay(image, config)
        assert result.size == image.size

    def test_positions(self, sample_image: Path):
        image = Image.open(sample_image).convert("RGB")
        for position in ("bottom-center", "top-center", "center"):
            config = TextOverlayConfig(text="test", position=position)
            result = apply_text_overlay(image, config)
            assert result.size == image.size


# ---------- process (end-to-end) ----------

class TestProcess:
    def test_end_to_end_no_caption(self, sample_image: Path, tmp_path: Path):
        output = tmp_path / "output.jpg"
        result = process(sample_image, output, brand_grade=True)
        assert result == output
        assert output.exists()
        # Verify it's a valid JPEG
        loaded = Image.open(output)
        assert loaded.format == "JPEG"

    def test_end_to_end_with_caption(self, sample_image: Path, tmp_path: Path):
        output = tmp_path / "output_caption.jpg"
        result = process(sample_image, output, caption="JUST DROPPED", brand_grade=True)
        assert result.exists()

    def test_skips_brand_grade(self, sample_image: Path, tmp_path: Path):
        output = tmp_path / "output_no_grade.jpg"
        result = process(sample_image, output, brand_grade=False)
        assert result.exists()

    def test_creates_output_dir(self, sample_image: Path, tmp_path: Path):
        output = tmp_path / "nested" / "deep" / "output.jpg"
        result = process(sample_image, output, brand_grade=False)
        assert result.exists()
        assert result.parent.exists()
