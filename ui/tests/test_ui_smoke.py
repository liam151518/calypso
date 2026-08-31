"""Smoke test: builds the Next.js UI and confirms it compiles.

Run: `python -m pytest ui/tests/test_ui_smoke.py -v`
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT  # ui/ is the Next.js root
NODE_BIN = shutil.which("node")


@pytest.mark.skipif(NODE_BIN is None, reason="node not installed")
class TestNextBuild:
    """Verify the Next.js app builds without errors."""

    def test_build_succeeds(self):
        result = subprocess.run(
            ["npx", "next", "build"],
            cwd=str(UI),
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"},
        )
        assert result.returncode == 0, f"next build failed:\nstdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
        # Confirm all the routes we expect are present in the output
        for route in ["/", "/phases", "/scripts", "/brand", "/workflows", "/tests", "/accounts", "/adam"]:
            assert route in result.stdout or route in result.stderr, f"route {route} not in build output"


class TestFileLayout:
    """Verify the UI folder is laid out correctly."""

    @pytest.mark.parametrize("path", [
        "package.json",
        "next.config.mjs",
        "tsconfig.json",
        "tailwind.config.ts",
        "postcss.config.mjs",
        "app/layout.tsx",
        "app/page.tsx",
        "app/phases/page.tsx",
        "app/scripts/page.tsx",
        "app/brand/page.tsx",
        "app/workflows/page.tsx",
        "app/tests/page.tsx",
        "app/accounts/page.tsx",
        "app/adam/page.tsx",
        "components/Sidebar.tsx",
        "components/Card.tsx",
        "components/StatCard.tsx",
        "components/Pill.tsx",
        "components/ScriptRunner.tsx",
        "components/TestRunner.tsx",
        "lib/api.ts",
        "lib/cn.ts",
        "server/app.py",
        "server/requirements.txt",
        "tests/test_ui_backend.py",
    ])
    def test_required_file_exists(self, path: str):
        assert (UI / path).exists(), f"missing: {path}"
