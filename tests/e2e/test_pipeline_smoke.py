"""End-to-end smoke test for the Phase A Pipeline builder UI."""

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
        cwd=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        ),
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


@pytest.fixture(scope="module")
def context(browser):
    ctx = browser.new_context()
    yield ctx
    ctx.close()


def test_pipelines_list_page(server, context):
    base, _ = server
    page = context.new_page()
    page.goto(f"{base}/pipelines", wait_until="domcontentloaded")
    page.wait_for_selector("text=Pipelines", timeout=10_000)
    page.wait_for_selector("text=New pipeline", timeout=5_000)
    page.close()


def test_pipelines_node_schemas_api(server):
    """The /api/pipelines/node-schemas endpoint should return all 10 node types."""
    import urllib.request

    base, _ = server
    with urllib.request.urlopen(f"{base}/api/pipelines/node-schemas", timeout=5) as r:
        body = r.read().decode()
    import json
    data = json.loads(body)
    schemas = data["schemas"]
    for expected in ["trigger", "brand", "reference", "prompt", "model",
                     "cost_guard", "generate", "image", "combine", "export"]:
        assert expected in schemas, f"missing schema for {expected}"


def test_pipelines_create_and_run(server):
    """End-to-end via the JSON API: create a pipeline, run it, poll status."""
    import json
    import urllib.request

    base, _ = server

    def post(path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{base}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    p = post("/api/pipelines", {
        "name": "e2e-pipe",
        "nodes": [
            {"id": "t", "type": "trigger", "params": {"mode": "manual"}},
            {"id": "p", "type": "prompt", "params": {"mode": "inline", "body": "smoke"}},
        ],
        "edges": [],
        "max_workers": 1,
    })
    pid = p["pipeline"]["id"]

    run_resp = post(f"/api/pipelines/{pid}/run", {"triggered_by": "e2e"})
    run_id = run_resp["run"]["id"]

    deadline = time.time() + 5
    while time.time() < deadline:
        with urllib.request.urlopen(f"{base}/api/pipelines/runs/{run_id}", timeout=5) as r:
            data = json.loads(r.read())
        if data["run"]["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.2)
    assert data["run"]["status"] == "succeeded"
