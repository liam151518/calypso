"""Tests for scripts/reference_picker.py.

Per the Adam rules, the high-level agent (Adam) writes these. Builders make
them green. Do not edit test files during slice execution — if a test is
wrong, file it as a finding and let Adam fix the test or rewrite the script.

Run: `python -m pytest tests/test_reference_picker.py -v`
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from scripts.reference_picker import (
    DEFAULT_WEIGHTS,
    Reference,
    filter_references,
    load_references,
    pick,
    weighted_pick,
)


# ---------- helpers ----------

def _write_ref(
    directory: Path,
    name: str,
    *,
    tier: str = "A",
    fmt: str = "image",
    platform: str = "x",
    theme: str = "pull_reaction",
    style_tags: list[str] | None = None,
    asset_path: str = "asset.png",
) -> Path:
    """Helper to write a minimal reference JSON."""
    path = directory / f"{name}.json"
    path.write_text(json.dumps({
        "source": "test",
        "source_url": f"https://test.example/{name}",
        "platform": platform,
        "format": fmt,
        "theme": theme,
        "engagement_tier": tier,
        "style_tags": style_tags or ["dark_moody"],
        "composition": "phone_in_hand",
        "audio_trend": "",
        "asset_path": asset_path,
    }))
    return path


# ---------- Reference.from_json ----------

class TestReferenceFromJson:
    def test_loads_minimal_json(self, tmp_path: Path):
        path = _write_ref(tmp_path, "minimal")
        ref = Reference.from_json(path)
        assert ref.platform == "x"
        assert ref.format == "image"
        assert ref.engagement_tier == "A"
        assert ref.style_tags == ["dark_moody"]

    def test_skips_unparseable_json(self, tmp_path: Path, caplog):
        (tmp_path / "broken.json").write_text("{not valid json")
        refs = load_references(ready_dir=tmp_path)
        assert refs == []


# ---------- load_references ----------

class TestLoadReferences:
    def test_returns_empty_when_dir_missing(self, tmp_path: Path):
        refs = load_references(ready_dir=tmp_path / "nope")
        assert refs == []

    def test_loads_all_json_files(self, tmp_path: Path):
        _write_ref(tmp_path, "a")
        _write_ref(tmp_path, "b")
        _write_ref(tmp_path, "c")
        refs = load_references(ready_dir=tmp_path)
        assert len(refs) == 3

    def test_skips_non_json_files(self, tmp_path: Path):
        _write_ref(tmp_path, "a")
        (tmp_path / "README.md").write_text("not a ref")
        refs = load_references(ready_dir=tmp_path)
        assert len(refs) == 1


# ---------- filter_references ----------

class TestFilterReferences:
    def test_filter_by_format(self, tmp_path: Path):
        _write_ref(tmp_path, "img", fmt="image")
        _write_ref(tmp_path, "vid", fmt="video")
        refs = load_references(ready_dir=tmp_path)
        videos = filter_references(refs, format="video")
        assert len(videos) == 1
        assert videos[0].format == "video"

    def test_filter_by_style_tag(self, tmp_path: Path):
        _write_ref(tmp_path, "dark", style_tags=["dark_moody", "neon"])
        _write_ref(tmp_path, "bright", style_tags=["bright", "anime"])
        refs = load_references(ready_dir=tmp_path)
        dark = filter_references(refs, style_tag="dark_moody")
        assert len(dark) == 1
        assert "dark_moody" in dark[0].style_tags

    def test_filter_by_platform(self, tmp_path: Path):
        _write_ref(tmp_path, "x_ref", platform="x")
        _write_ref(tmp_path, "ig_ref", platform="instagram")
        refs = load_references(ready_dir=tmp_path)
        xs = filter_references(refs, platform="x")
        assert len(xs) == 1
        assert xs[0].platform == "x"

    def test_filters_compose_with_and_semantics(self, tmp_path: Path):
        _write_ref(tmp_path, "match", fmt="video", style_tags=["dark_moody"])
        _write_ref(tmp_path, "wrong_fmt", fmt="image", style_tags=["dark_moody"])
        _write_ref(tmp_path, "wrong_tag", fmt="video", style_tags=["bright"])
        refs = load_references(ready_dir=tmp_path)
        result = filter_references(refs, format="video", style_tag="dark_moody")
        assert len(result) == 1
        assert result[0].path.name == "match.json"

    def test_filter_with_no_matches_returns_empty(self, tmp_path: Path):
        _write_ref(tmp_path, "a", fmt="image")
        refs = load_references(ready_dir=tmp_path)
        result = filter_references(refs, format="video")
        assert result == []


# ---------- weighted_pick ----------

class TestWeightedPick:
    def test_picks_from_non_empty_list(self, tmp_path: Path):
        path = _write_ref(tmp_path, "only_one")
        ref = Reference.from_json(path)
        result = weighted_pick([ref], rng=random.Random(42))
        assert result is ref

    def test_raises_on_empty(self):
        with pytest.raises(ValueError, match="no references"):
            weighted_pick([])

    def test_a_tier_dominates_with_seeded_rng(self, tmp_path: Path):
        # 1 A-tier + 9 C-tier = A-tier should win ~70% of picks
        a_paths = [_write_ref(tmp_path, f"a_{i}", tier="A") for i in range(1)]
        c_paths = [_write_ref(tmp_path, f"c_{i}", tier="C") for i in range(9)]
        refs = [Reference.from_json(p) for p in a_paths + c_paths]

        rng = random.Random(123)
        a_count = 0
        trials = 1000
        for _ in range(trials):
            pick_result = weighted_pick(refs, rng=rng)
            if pick_result.engagement_tier == "A":
                a_count += 1

        # A weight = 3.0, C weight = 0.33. Expected ratio: 3.0 / (3.0 + 9*0.33) ≈ 0.503
        # So A-tier should win ~50% of the time, not 70%. Adjust expectation.
        assert 0.40 <= a_count / trials <= 0.60, f"A-tier picked {a_count}/{trials} times"

    def test_unrated_uses_default_weight(self, tmp_path: Path):
        path = _write_ref(tmp_path, "unrated", tier="")
        ref = Reference.from_json(path)
        # Should not crash and should pick the ref
        result = weighted_pick([ref], rng=random.Random(7))
        assert result is ref

    def test_unknown_tier_uses_default_weight(self, tmp_path: Path):
        path = _write_ref(tmp_path, "weird", tier="X")
        ref = Reference.from_json(path)
        # Tier "X" not in DEFAULT_WEIGHTS — falls back to 1.0 via .get()
        result = weighted_pick([ref], rng=random.Random(7))
        assert result is ref


# ---------- pick (top-level convenience) ----------

class TestPick:
    def test_pick_raises_when_no_refs(self, tmp_path: Path, monkeypatch):
        # Force load_references to find nothing by pointing READY_DIR at empty
        monkeypatch.setattr("scripts.reference_picker.READY_DIR", tmp_path / "empty")
        with pytest.raises(ValueError, match="no references"):
            pick()

    def test_pick_with_format_filter(self, tmp_path: Path, monkeypatch):
        _write_ref(tmp_path, "img1", fmt="image")
        _write_ref(tmp_path, "img2", fmt="image")
        _write_ref(tmp_path, "vid1", fmt="video")
        monkeypatch.setattr("scripts.reference_picker.READY_DIR", tmp_path)

        result = pick(format="video", rng=random.Random(0))
        assert result.format == "video"
