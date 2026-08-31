"""Tests for Phase 4 optimization scripts (variant_generator, reweight_references, ab_test).

Run: `python -m pytest tests/test_optimization.py -v`
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from scripts.ab_test import (
    POST_PROCESS_VARIANTS,
    AUDIO_VARIANTS,
    DURATION_VARIANTS,
    assign,
    is_test_active,
    activate_test,
    deactivate_test,
)
from scripts.reweight_references import compute_engagement_rate, reweight
from scripts.variant_generator import (
    VARIANT_RECIPES,
    generate_variant_prompts,
    get_variants,
)


# ---------- variant_generator ----------

class TestVariantGenerator:
    def test_get_variants_returns_three(self):
        variants = get_variants()
        assert len(variants) == 3

    def test_canonical_aspect_ratios(self):
        variants = get_variants()
        ratios = {v.aspect_ratio for v in variants}
        assert ratios == {"1:1", "9:16", "16:9"}

    def test_canonical_dimensions(self):
        variants = get_variants()
        # All variants are valid pixel counts
        for v in variants:
            assert v.width > 0
            assert v.height > 0
            assert v.width * v.height >= 768 * 768

    def test_generate_variants_returns_three(self):
        result = generate_variant_prompts("base prompt", ["cinematic"], rng=random.Random(0))
        assert len(result) == 3

    def test_each_variant_has_distinct_aspect(self):
        result = generate_variant_prompts("base", [], rng=random.Random(0))
        aspects = [v["aspect_ratio"] for v in result]
        assert len(set(aspects)) == 3

    def test_base_prompt_preserved_in_each_variant(self):
        result = generate_variant_prompts("base prompt", [], rng=random.Random(0))
        for v in result:
            assert "base prompt" in v["prompt"]

    def test_base_style_tags_preserved(self):
        result = generate_variant_prompts("base", ["cinematic", "dark"], rng=random.Random(0))
        for v in result:
            # All variants inherit the base style tags + their own
            assert "cinematic" in v["style_tags"]
            assert "dark" in v["style_tags"]

    def test_caption_suffix_varies(self):
        result = generate_variant_prompts("base", [], rng=random.Random(0))
        suffixes = [v["caption_suffix"] for v in result]
        # Variant 0 has empty suffix; variants 1 and 2 have hashtags
        assert suffixes[0] == ""
        assert "#" in suffixes[1]
        assert "#" in suffixes[2]

    def test_vertical_variant_has_vertical_composition(self):
        result = generate_variant_prompts("base", [], rng=random.Random(0))
        vertical = next(v for v in result if v["aspect_ratio"] == "9:16")
        assert "vertical" in vertical["prompt"].lower()

    def test_horizontal_variant_has_wide_composition(self):
        result = generate_variant_prompts("base", [], rng=random.Random(0))
        horizontal = next(v for v in result if v["aspect_ratio"] == "16:9")
        assert "wide" in horizontal["prompt"].lower() or "cinematic" in horizontal["prompt"].lower()

    def test_reproducibility(self):
        a = generate_variant_prompts("base", ["x"], rng=random.Random(42))
        b = generate_variant_prompts("base", ["x"], rng=random.Random(42))
        assert a == b


# ---------- reweight_references ----------

class TestReweightReferences:
    def test_engagement_rate_basic(self):
        metrics = {"avg_likes": 100, "avg_shares": 10, "avg_comments": 5, "avg_impressions": 1000}
        assert compute_engagement_rate(metrics) == pytest.approx(0.115)

    def test_engagement_rate_zero_impressions(self):
        metrics = {"avg_likes": 0, "avg_shares": 0, "avg_comments": 0, "avg_impressions": 0}
        assert compute_engagement_rate(metrics) == 0.0

    def test_reweight_no_references(self, tmp_path: Path):
        summary = reweight(ready_dir=tmp_path / "nope", dry_run=True)
        assert summary.get("error") or summary.get("processed") == 0

    def test_reweight_empty_dir(self, tmp_path: Path):
        ready = tmp_path / "ready"
        ready.mkdir()
        archived = tmp_path / "archived"
        summary = reweight(ready_dir=ready, archived_dir=archived, dry_run=True)
        assert summary["processed"] == 0

    def test_reweight_counts_tiers(self, tmp_path: Path):
        ready = tmp_path / "ready"
        ready.mkdir()
        # 2 A-tier, 1 B-tier
        (ready / "a1.json").write_text(json.dumps({"engagement_tier": "A"}))
        (ready / "a2.json").write_text(json.dumps({"engagement_tier": "A"}))
        (ready / "b1.json").write_text(json.dumps({"engagement_tier": "B"}))
        summary = reweight(ready_dir=ready, archived_dir=tmp_path / "archived", dry_run=True)
        assert summary["processed"] == 3
        assert summary["tiers"]["A"] == 2
        assert summary["tiers"]["B"] == 1


# ---------- ab_test ----------

class TestABTestAssignment:
    def test_assignment_is_deterministic(self):
        a = assign("post_process", "post-123")
        b = assign("post_process", "post-123")
        assert a.variant == b.variant
        assert a.bucket == b.bucket

    def test_assignment_uses_one_of_known_variants(self):
        for post_id in ["post-1", "post-2", "post-3", "post-4", "post-5"]:
            a = assign("post_process", post_id)
            assert a.variant in POST_PROCESS_VARIANTS

    def test_assignment_distributes_roughly_evenly(self):
        """With 100 post_ids, both variants should appear (statistical test)."""
        counts: dict[str, int] = {}
        for i in range(100):
            a = assign("post_process", f"post-{i}")
            counts[a.variant] = counts.get(a.variant, 0) + 1
        # Both should appear at least 25 times (probabilistic)
        assert all(v >= 25 for v in counts.values())

    def test_audio_test_has_two_variants(self):
        for post_id in ["a", "b", "c", "d", "e"]:
            a = assign("audio", post_id)
            assert a.variant in AUDIO_VARIANTS

    def test_duration_test_has_three_variants(self):
        for post_id in ["a", "b", "c", "d", "e", "f", "g"]:
            a = assign("duration", post_id)
            assert a.variant in DURATION_VARIANTS


class TestABTestActivation:
    def test_inactive_by_default(self, tmp_path: Path, monkeypatch):
        from scripts import ab_test
        monkeypatch.setattr(ab_test, "STATE_FILE", tmp_path / "ab.json")
        assert is_test_active("post_process", state_path=tmp_path / "ab.json") is False

    def test_activate_then_check(self, tmp_path: Path, monkeypatch):
        from scripts import ab_test
        monkeypatch.setattr(ab_test, "STATE_FILE", tmp_path / "ab.json")
        activate_test("post_process", state_path=tmp_path / "ab.json")
        assert is_test_active("post_process", state_path=tmp_path / "ab.json") is True

    def test_deactivate(self, tmp_path: Path, monkeypatch):
        from scripts import ab_test
        monkeypatch.setattr(ab_test, "STATE_FILE", tmp_path / "ab.json")
        activate_test("audio", state_path=tmp_path / "ab.json")
        assert is_test_active("audio", state_path=tmp_path / "ab.json") is True
        deactivate_test("audio", state_path=tmp_path / "ab.json")
        assert is_test_active("audio", state_path=tmp_path / "ab.json") is False


class TestABTestCLI:
    def test_assigns_when_active(self, tmp_path: Path, monkeypatch, capsys):
        from scripts import ab_test
        monkeypatch.setattr(ab_test, "STATE_FILE", tmp_path / "ab.json")
        activate_test("post_process", state_path=tmp_path / "ab.json")
        monkeypatch.setattr(
            "sys.argv",
            ["ab_test.py", "--test", "post_process", "--post-id", "post-x"],
        )
        rc = ab_test._cli()
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["test"] == "post_process"
        assert parsed["variant"] in POST_PROCESS_VARIANTS

    def test_skips_when_inactive(self, tmp_path: Path, monkeypatch, capsys):
        from scripts import ab_test
        monkeypatch.setattr(ab_test, "STATE_FILE", tmp_path / "ab.json")
        monkeypatch.setattr(
            "sys.argv",
            ["ab_test.py", "--test", "post_process", "--post-id", "post-x"],
        )
        rc = ab_test._cli()
        assert rc == 0
        out = capsys.readouterr().out
        # Should print skip message
        assert "not active" in out
