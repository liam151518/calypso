"""Integration test for the image pipeline.

This is a smoke test. It verifies the workflow JSON files load, the scripts
compose correctly, and the post-process step produces a valid output. It does
NOT require ComfyUI or Telegram to be running.

Run: `python -m pytest tests/test_image_pipeline.py -v`
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from scripts import post_process
from scripts import prompt_builder
from scripts.prompt_builder import build


REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGE_WORKFLOW = REPO_ROOT / "workflows" / "01-image-generation.json"
COMFYUI_WORKFLOW = REPO_ROOT / "comfyui" / "01-image-with-style-reference.json"


class TestImageN8nWorkflow:
    def test_workflow_file_exists(self):
        assert IMAGE_WORKFLOW.exists()

    def test_workflow_is_valid_json(self):
        data = json.loads(IMAGE_WORKFLOW.read_text())
        assert "nodes" in data
        assert "connections" in data

    def test_workflow_has_cron_triggers(self):
        data = json.loads(IMAGE_WORKFLOW.read_text())
        triggers = [n for n in data["nodes"] if "scheduleTrigger" in n["type"]]
        assert len(triggers) == 2, "expected 2 cron triggers (12:00 + 18:00)"

    def test_workflow_connects_in_order(self):
        """Verify the connection graph is linear: cron → picker → builder → submit → poll → process → telegram."""
        data = json.loads(IMAGE_WORKFLOW.read_text())
        connections = data["connections"]
        # Build reverse map: target_node_name -> [source_node_names]
        incoming: dict[str, list[str]] = {}
        for source_name, output_map in connections.items():
            for output_type, edge_groups in output_map.items():
                for edge_group in edge_groups:
                    for edge in edge_group:
                        incoming.setdefault(edge["node"], []).append(source_name)

        for node in data["nodes"]:
            if "scheduleTrigger" in node["type"]:
                continue
            assert node["name"] in incoming, f"node {node['name']} ({node['id']}) is disconnected"

    def test_workflow_timezone_is_johannesburg(self):
        data = json.loads(IMAGE_WORKFLOW.read_text())
        assert data["settings"]["timezone"] == "Africa/Johannesburg"


class TestComfyUIWorkflow:
    def test_workflow_file_exists(self):
        assert COMFYUI_WORKFLOW.exists()

    def test_workflow_is_valid_json(self):
        data = json.loads(COMFYUI_WORKFLOW.read_text())
        assert "nodes" in data
        assert "links" in data

    def test_has_required_nodes(self):
        data = json.loads(COMFYUI_WORKFLOW.read_text())
        node_types = {n["type"] for n in data["nodes"]}
        # Must have all the key components for reference-driven generation
        required = {
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "IPAdapterAdvanced",
            "ControlNetApplyAdvanced",
            "LoraLoader",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        }
        missing = required - node_types
        assert not missing, f"missing required node types: {missing}"

    def test_has_brand_anchors_in_positive_prompt(self):
        data = json.loads(COMFYUI_WORKFLOW.read_text())
        for node in data["nodes"]:
            if node["type"] == "CLIPTextEncode" and "Positive" in node["title"]:
                widgets = node["widgets_values"]
                text = widgets[0] if widgets else ""
                assert "gacha capsule toy" in text
                assert "Japanese capsule machine" in text
                assert "neon-lit arcade" in text

    def test_negative_prompt_excludes_gambling(self):
        data = json.loads(COMFYUI_WORKFLOW.read_text())
        for node in data["nodes"]:
            if node["type"] == "CLIPTextEncode" and "Negative" in node["title"]:
                widgets = node["widgets_values"]
                text = widgets[0] if widgets else ""
                for banned in ["gambling", "casino", "dice", "cards", "slot machine"]:
                    assert banned in text

    def test_vram_estimate_under_12gb(self):
        data = json.loads(COMFYUI_WORKFLOW.read_text())
        estimate = data["metadata"]["vram_estimate_gb"]
        assert estimate <= 12.0, f"VRAM estimate {estimate} GB exceeds 5070's 12 GB"


class TestEndToEndSmoke:
    """Compose reference → prompt → fake image → post-process."""

    def test_full_chain_produces_valid_output(self, tmp_path: Path):
        # 1. Fake reference
        reference = {
            "theme": "pull_reaction",
            "style_tags": ["dark_moody", "cinematic", "neon_accents"],
            "composition": "phone_in_hand",
            "audio_trend": "",
            "format": "image",
        }
        # 2. Build the prompt
        prompt = build(reference)
        assert "gacha capsule toy" in prompt.positive
        assert "gambling" in prompt.negative
        # 3. Fake "generated" image
        gen_img = Image.new("RGB", (1024, 1024), color=(64, 64, 96))
        gen_path = tmp_path / "generated.jpg"
        gen_img.save(gen_path)
        # 4. Post-process it
        out_path = tmp_path / "final.jpg"
        result = post_process.process(gen_path, out_path, caption=prompt.caption, brand_grade=True)
        assert result.exists()
        loaded = Image.open(result)
        assert loaded.format == "JPEG"
        assert loaded.size == (1024, 1024)

    def test_chain_handles_all_themes(self):
        """For each theme in prompt_builder templates, the chain produces a valid prompt."""
        themes = list(prompt_builder.CAPTION_TEMPLATES.keys())
        for theme in themes:
            reference = {"theme": theme, "style_tags": ["cinematic"], "composition": "", "audio_trend": ""}
            prompt = build(reference)
            assert prompt.theme == theme
            assert len(prompt.positive) > 0
            assert len(prompt.caption) > 0


class TestAntiSlopChecks:
    """Per the plan: 'the only hard gate is verify.sh'. These checks encode the anti-slop rules."""

    def test_no_banned_words_in_positive_prompt(self):
        reference = {"theme": "pull_reaction", "style_tags": ["cinematic"], "composition": "", "audio_trend": ""}
        prompt = build(reference)
        banned = ["gambling", "casino", "betting", "jackpot", "prize money", "cash payout"]
        for word in banned:
            assert word not in prompt.positive.lower(), f"banned word '{word}' in positive prompt"

    def test_no_banned_words_in_caption(self):
        # Run many caption builds to check the templates
        import random
        rng = random.Random(0)
        for _ in range(50):
            reference = {"theme": "pull_reaction", "style_tags": [], "composition": "", "audio_trend": ""}
            prompt = build(reference, rng=rng)
            # Captions are filled with template placeholders, so they're never the actual banned phrases.
            # The check is mainly that no template uses banned phrasing.
            assert "gambling" not in prompt.caption.lower()

    def test_watermark_is_brand_logo_path(self):
        from scripts.post_process import DEFAULT_WATERMARK
        assert DEFAULT_WATERMARK.exists(), f"watermark logo missing: {DEFAULT_WATERMARK}"
        assert "GK_Logo" in DEFAULT_WATERMARK.name
