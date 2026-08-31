"""Smoke tests for the video pipeline JSON workflows.

Run: `python -m pytest tests/test_video_pipeline.py -v`
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEO_N8N = REPO_ROOT / "workflows" / "02-video-generation.json"
COMFYUI_H3 = REPO_ROOT / "comfyui" / "02-h3-reference-to-video.json"


class TestVideoN8nWorkflow:
    def test_file_exists(self):
        assert VIDEO_N8N.exists()

    def test_valid_json(self):
        json.loads(VIDEO_N8N.read_text())

    def test_has_cron_trigger(self):
        data = json.loads(VIDEO_N8N.read_text())
        triggers = [n for n in data["nodes"] if "scheduleTrigger" in n["type"]]
        assert len(triggers) == 1

    def test_connections_are_linear(self):
        data = json.loads(VIDEO_N8N.read_text())
        connections = data["connections"]
        incoming: dict[str, list[str]] = {}
        for source_name, output_map in connections.items():
            for output_type, edge_groups in output_map.items():
                for edge_group in edge_groups:
                    for edge in edge_group:
                        incoming.setdefault(edge["node"], []).append(source_name)
        for node in data["nodes"]:
            if "scheduleTrigger" in node["type"]:
                continue
            assert node["name"] in incoming, f"{node['name']} is disconnected"

    def test_includes_router_node(self):
        data = json.loads(VIDEO_N8N.read_text())
        node_names = {n["name"] for n in data["nodes"]}
        assert "Generation Router" in node_names

    def test_includes_spend_recording(self):
        data = json.loads(VIDEO_N8N.read_text())
        node_names = {n["name"] for n in data["nodes"]}
        assert "Record Spend" in node_names

    def test_timezone_is_johannesburg(self):
        data = json.loads(VIDEO_N8N.read_text())
        assert data["settings"]["timezone"] == "Africa/Johannesburg"


class TestComfyUIH3Template:
    def test_file_exists(self):
        assert COMFYUI_H3.exists()

    def test_valid_json(self):
        json.loads(COMFYUI_H3.read_text())

    def test_uses_native_h3_nodes(self):
        data = json.loads(COMFYUI_H3.read_text())
        node_types = {n["type"] for n in data["nodes"]}
        # Must use at least one of the official H3 native nodes
        h3_nodes = {t for t in node_types if "MiniMax" in t}
        assert len(h3_nodes) >= 2

    def test_marks_phase_4_local_benchmark(self):
        data = json.loads(COMFYUI_H3.read_text())
        # The template is for Phase 4 — not used in production video generation
        assert data["metadata"]["phase"] == "4 — local H3 benchmark only"

    def test_documents_vram_requirements(self):
        data = json.loads(COMFYUI_H3.read_text())
        meta = data["metadata"]
        assert "vram_estimate_gb_int4" in meta
        assert meta["vram_estimate_gb_int4"] <= 12, "int4 quantization should fit in 5070's 12 GB"


class TestEndToEndVideoSmoke:
    """Test the full chain without network: pick ref → build prompt → route → record."""

    def test_full_chain(self, tmp_path: Path, monkeypatch):
        import random
        from scripts import prompt_builder
        from scripts.generation_router import GenerationRouter, RoutingDecision, SpendState

        # 1. Fake reference
        reference = {
            "theme": "pull_reaction",
            "style_tags": ["dark_moody", "cinematic"],
            "composition": "phone_in_hand",
            "audio_trend": "trending_sound_v3",
            "format": "video",
        }
        # 2. Build prompt with motion
        prompt = prompt_builder.build(reference, rng=random.Random(0), include_motion=True)
        assert prompt.motion is not None
        # 3. Route
        monkeypatch.setattr("scripts.generation_router.SPEND_FILE", tmp_path / "spend.json")
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=0.0, cap_usd=30.0))
        decision = router.route(duration_seconds=8, resolution="768p")
        assert decision.backend == "h3_cloud"
        # 4. Record spend
        router.record_spend(decision)
        # Reload state and verify persistence
        new_router = GenerationRouter(SpendState.load(tmp_path / "spend.json"))
        assert new_router.spend.requests == 1
        assert new_router.spend.spend_usd > 0

    def test_routing_cost_aware_fallback(self, tmp_path: Path, monkeypatch):
        from scripts.generation_router import GenerationRouter, SpendState

        # At 80% of cap
        monkeypatch.setattr("scripts.generation_router.SPEND_FILE", tmp_path / "spend.json")
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=24.0, cap_usd=30.0))
        decision = router.route(duration_seconds=8, resolution="768p")
        assert decision.backend == "ltx_falai"
        assert decision.tier == "fallback"

    def test_routing_hero_promotion(self, tmp_path: Path, monkeypatch):
        from scripts.generation_router import GenerationRouter, SpendState

        monkeypatch.setattr("scripts.generation_router.SPEND_FILE", tmp_path / "spend.json")
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=5.0, cap_usd=30.0))
        decision = router.route(duration_seconds=8, resolution="768p", is_hero=True)
        assert decision.backend == "kling_falai"
        assert decision.tier == "hero"


class TestAntiSlopVideoChecks:
    """Encode the anti-slop rules in test form (per the plan's hard gate)."""

    def test_no_banned_words_in_video_prompt(self):
        from scripts import prompt_builder
        import random
        for _ in range(20):
            reference = {"theme": "pull_reaction", "style_tags": [], "composition": "", "audio_trend": ""}
            prompt = prompt_builder.build(reference, rng=random.Random(0), include_motion=True)
            for banned in ["gambling", "casino", "jackpot"]:
                assert banned not in prompt.positive.lower()

    def test_motion_descriptions_are_brand_safe(self):
        from scripts.prompt_builder import _build_motion
        import random
        for _ in range(20):
            m = _build_motion("pull_reaction", rng=random.Random(0))
            assert "gambling" not in m.lower()
            assert "casino" not in m.lower()
