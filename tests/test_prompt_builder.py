"""Tests for scripts/prompt_builder.py.

Run: `python -m pytest tests/test_prompt_builder.py -v`
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from scripts.prompt_builder import (
    CAPTION_TEMPLATES,
    NEGATIVE_BASE,
    Prompt,
    _build_motion,
    build,
)


def _ref(**kwargs) -> dict:
    """Helper to construct a reference dict."""
    base = {
        "theme": "pull_reaction",
        "style_tags": ["dark_moody", "cinematic", "neon_accents"],
        "composition": "phone_in_hand",
        "audio_trend": "",
    }
    base.update(kwargs)
    return base


# ---------- Prompt dataclass ----------

class TestPromptDataclass:
    def test_is_frozen(self):
        p = Prompt(positive="x", negative="y", caption="z", theme="pull_reaction", style_tags=["a"])
        with pytest.raises(Exception):
            p.caption = "modified"  # type: ignore


# ---------- build() basics ----------

class TestBuild:
    def test_returns_prompt(self):
        result = build(_ref())
        assert isinstance(result, Prompt)

    def test_positive_includes_brand_anchors(self):
        result = build(_ref())
        assert "gacha capsule toy" in result.positive
        assert "Japanese capsule machine" in result.positive
        assert "neon-lit arcade" in result.positive

    def test_positive_includes_theme_frame(self):
        result = build(_ref(theme="pull_reaction"))
        assert "reveal moment" in result.positive

    def test_positive_includes_style_tags(self):
        result = build(_ref(style_tags=["dark_moody", "cinematic", "neon_accents"]))
        assert "dark_moody" in result.positive
        assert "cinematic" in result.positive
        assert "neon_accents" in result.positive

    def test_negative_excludes_gambling(self):
        result = build(_ref())
        for banned in ["gambling", "casino", "dice", "cards", "slot machine"]:
            assert banned in result.negative

    def test_caption_is_non_empty(self):
        result = build(_ref())
        assert len(result.caption) > 0

    def test_style_tags_round_trip(self):
        result = build(_ref(style_tags=["a", "b", "c"]))
        assert result.style_tags == ["a", "b", "c"]

    def test_includes_composition_hint_when_present(self):
        result = build(_ref(composition="phone_in_hand"))
        assert "phone_in_hand" in result.positive

    def test_omits_composition_when_absent(self):
        ref = _ref()
        del ref["composition"]
        result = build(ref)
        assert "framing" not in result.positive


# ---------- motion ----------

class TestMotion:
    def test_motion_none_when_not_requested(self):
        result = build(_ref(), include_motion=False)
        assert result.motion is None

    def test_motion_populated_when_requested(self):
        result = build(_ref(), include_motion=True)
        assert result.motion is not None
        assert len(result.motion) > 0

    def test_motion_differs_per_theme(self):
        a = build(_ref(theme="pull_reaction"), include_motion=True, rng=random.Random(0))
        b = build(_ref(theme="irl_cabinet"), include_motion=True, rng=random.Random(0))
        assert a.motion != b.motion


# ---------- anti-slop guards ----------

class TestAntiSlop:
    @pytest.mark.parametrize("banned_word", ["gambling", "casino", "betting odds", "slot machine", "jackpot"])
    def test_negative_prompt_contains_banned_word(self, banned_word):
        result = build(_ref())
        assert banned_word in result.negative

    def test_brand_anchors_in_positive(self):
        result = build(_ref())
        # Brand anchors that should always be present
        for anchor in ["gacha capsule toy", "Japanese capsule machine", "neon-lit arcade"]:
            assert anchor in result.positive


# ---------- reproducibility ----------

class TestReproducibility:
    def test_same_seed_same_output(self):
        ref = _ref()
        a = build(ref, rng=random.Random(42))
        b = build(ref, rng=random.Random(42))
        assert a.positive == b.positive
        assert a.caption == b.caption
        assert a.motion == b.motion

    def test_different_seeds_different_captions(self):
        ref = _ref()
        a = build(ref, rng=random.Random(1))
        b = build(ref, rng=random.Random(2))
        # Captions involve random.choice, so they should usually differ
        # (probabilistically, the same template is picked only ~10% of the time)
        assert a.caption != b.caption or a.positive != b.positive


# ---------- caption templates ----------

class TestCaptionTemplates:
    @pytest.mark.parametrize("theme", list(CAPTION_TEMPLATES.keys()))
    def test_every_theme_has_at_least_one_template(self, theme):
        assert len(CAPTION_TEMPLATES[theme]) >= 1

    def test_unknown_theme_falls_back(self):
        result = build(_ref(theme="totally_unknown_xyz"))
        # Should not crash and should return a non-empty caption
        assert len(result.caption) > 0


# ---------- CLI integration (smoke test) ----------

class TestCLI:
    def test_cli_runs(self, tmp_path: Path, monkeypatch, capsys):
        ref_path = tmp_path / "ref.json"
        ref_path.write_text(json.dumps(_ref()))
        from scripts import prompt_builder
        monkeypatch.setattr("sys.argv", ["prompt_builder.py", "--reference", str(ref_path), "--motion", "--seed", "5"])
        rc = prompt_builder._cli()
        assert rc == 0
        captured = capsys.readouterr()
        # Should print JSON with positive, negative, caption, motion
        parsed = json.loads(captured.out)
        assert "positive" in parsed
        assert "caption" in parsed
        assert parsed["motion"] is not None

    def test_cli_errors_on_missing_reference(self, tmp_path: Path, monkeypatch):
        from scripts import prompt_builder
        monkeypatch.setattr("sys.argv", ["prompt_builder.py", "--reference", str(tmp_path / "nope.json")])
        rc = prompt_builder._cli()
        assert rc == 1
