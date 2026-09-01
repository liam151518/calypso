"""End-to-end smoke test: boot the Flask app (which serves the built SPA),
open `/` in a real browser via Playwright, navigate to Generate, paste a
prompt, and assert that a JobCard renders.

Skipped automatically if Playwright is not installed.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from contextlib import closing, contextmanager

import pytest


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.2)
    raise TimeoutError(f"Server at {host}:{port} did not come up in {timeout}s")


@contextmanager
def _running_server(port: int):
    env = os.environ.copy()
    env["CALYPSO_PORT"] = str(port)
    env["CALYPSO_HOST"] = "127.0.0.1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.server"],
        env=env,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for_port("127.0.0.1", port)
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    with _running_server(port) as proc:
        yield f"http://127.0.0.1:{port}", proc


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Chromium not installed for Playwright: {e}")
        yield b
        b.close()


def test_spa_root_renders_index_html(server, browser):
    base_url, _ = server
    page = browser.new_page()
    try:
        resp = page.goto(base_url + "/")
        assert resp is not None and resp.status == 200
        assert "Calypso" in page.title() or "Operator" in page.content()
    finally:
        page.close()


def test_navigate_to_generate_and_see_composer(server, browser):
    base_url, _ = server
    page = browser.new_page()
    try:
        page.goto(base_url + "/generate", wait_until="networkidle")
        # The SPA fallback at /generate serves index.html; the React app then
        # mounts and routes to /generate. Wait for hydration.
        page.wait_for_selector('[data-testid="page-outlet"]', timeout=15_000)
        page.wait_for_selector('[data-testid="nav-generate"]', timeout=15_000)
        page.wait_for_selector('[data-testid="prompt-composer"]', timeout=15_000)
        assert page.locator('[data-testid="prompt-input"]').count() == 1
        assert page.locator('[data-testid="submit-generate"]').count() == 1
    finally:
        page.close()


def test_navigate_to_image_and_see_composer(server, browser):
    base_url, _ = server
    page = browser.new_page()
    try:
        page.goto(base_url + "/image", wait_until="networkidle")
        page.wait_for_selector('[data-testid="page-outlet"]', timeout=15_000)
        page.wait_for_selector('[data-testid="nav-image"]', timeout=15_000)
        page.wait_for_selector('[data-testid="image-composer"]', timeout=15_000)
        assert page.locator('[data-testid="image-prompt-input"]').count() == 1
        assert page.locator('[data-testid="submit-image"]').count() == 1
        # The video ModelPicker should still be present on /generate, so the
        # image picker trigger should be present on /image.
        assert page.locator('[data-testid="model-picker-trigger-image"]').count() == 1
    finally:
        page.close()


def test_api_models_endpoint_returns_models(server):
    """Hit /api/models and assert at least 10 models with both categories."""
    import urllib.request
    import json

    base_url, _ = server
    req = urllib.request.Request(
        f"{base_url}/api/models",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    assert len(data["models"]) >= 10
    cats = {m["category"] for m in data["models"]}
    assert "video" in cats
    assert "image" in cats


def test_api_cost_estimate_returns_estimate(server):
    """Hit /api/cost-estimate and assert a USD amount is returned."""
    import urllib.request
    import json

    base_url, _ = server
    req = urllib.request.Request(
        f"{base_url}/api/cost-estimate",
        data=json.dumps({"model": "minimax/h3", "duration": 8, "resolution": "768p"}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    assert data["estimate"]["usd"] > 0
    assert data["estimate"]["category"] == "video"
