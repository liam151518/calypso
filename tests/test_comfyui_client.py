"""Tests for scripts/comfyui_client.py.

Run: `python -m pytest tests/test_comfyui_client.py -v`

These tests don't require a running ComfyUI — they use a fake HTTP server
(unix socket based) to simulate ComfyUI's responses.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts.comfyui_client import ComfyUIClient, ComfyUIError


# ---------- fake ComfyUI server ----------

class FakeComfyUI(BaseHTTPRequestHandler):
    """Minimal ComfyUI mock for tests."""

    # State shared across requests
    next_prompt_id = 1
    history: dict[str, dict] = {}
    queued_outputs: dict[str, list[dict]] = {}  # prompt_id -> list of image outputs

    def log_message(self, *_args, **_kwargs):  # silence stdout
        pass

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/system_stats"):
            self._json(200, {"system": {"comfyui_version": "0.30.0"}})
        elif self.path.startswith("/history/"):
            prompt_id = self.path.split("/")[-1]
            entry = self.history.get(prompt_id)
            if entry is None:
                self._json(200, {})
            else:
                self._json(200, {prompt_id: entry})
        elif self.path.startswith("/view?"):
            # return a tiny placeholder PNG
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", "8")
            self.end_headers()
            self.wfile.write(b"\x89PNG\r\n\x1a\n")
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path == "/prompt":
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode() or "{}")
            prompt_id = f"prompt-{self.next_prompt_id}"
            type(self).next_prompt_id += 1
            # Mark this prompt as having queued outputs
            outputs = type(self).queued_outputs.get(prompt_id, [])
            # Simulate completion immediately
            type(self).history[prompt_id] = {
                "status": {"completed": True},
                "outputs": {n: {"images": out} for n, out in enumerate(outputs)},
            }
            self._json(200, {"prompt_id": prompt_id})
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def fake_comfy_server():
    """Spin up a fake ComfyUI server in a background thread."""
    server = HTTPServer(("127.0.0.1", 0), FakeComfyUI)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()


@pytest.fixture(autouse=True)
def reset_fake_comfy_state():
    FakeComfyUI.next_prompt_id = 1
    FakeComfyUI.history = {}
    FakeComfyUI.queued_outputs = {}
    yield


# ---------- tests ----------

class TestHealth:
    def test_health_returns_true_when_reachable(self, fake_comfy_server):
        host, port = fake_comfy_server
        client = ComfyUIClient(base_url=f"http://{host}:{port}")
        assert client.health() is True

    def test_health_returns_false_when_unreachable(self):
        client = ComfyUIClient(base_url="http://127.0.0.1:1")  # nothing listens on port 1
        client.timeout = 0.5
        assert client.health() is False


class TestQueuePrompt:
    def test_returns_prompt_id(self, fake_comfy_server):
        host, port = fake_comfy_server
        client = ComfyUIClient(base_url=f"http://{host}:{port}")
        prompt_id = client.queue_prompt({"3": {"class_type": "KSampler"}})
        assert prompt_id.startswith("prompt-")

    def test_raises_on_missing_prompt_id(self, fake_comfy_server, monkeypatch):
        host, port = fake_comfy_server
        client = ComfyUIClient(base_url=f"http://{host}:{port}")

        # Monkeypatch the internal _request to return no prompt_id
        def fake_request(method, path, *, body=None):
            return {}

        monkeypatch.setattr(client, "_request", fake_request)
        with pytest.raises(ComfyUIError, match="no prompt_id"):
            client.queue_prompt({"3": {}})


class TestWaitForCompletion:
    def test_returns_history_on_completion(self, fake_comfy_server):
        host, port = fake_comfy_server
        client = ComfyUIClient(base_url=f"http://{host}:{port}", poll_interval=0.01)
        prompt_id = client.queue_prompt({"3": {}})
        entry = client.wait_for_completion(prompt_id)
        assert entry["status"]["completed"] is True

    def test_raises_on_timeout(self, fake_comfy_server, monkeypatch):
        host, port = fake_comfy_server
        client = ComfyUIClient(base_url=f"http://{host}:{port}", poll_interval=0.01, max_poll_seconds=0.1)

        def fake_get_history(prompt_id):
            return None  # never completes

        monkeypatch.setattr(client, "get_history", fake_get_history)
        with pytest.raises(ComfyUIError, match="did not complete"):
            client.wait_for_completion("fake-id")

    def test_raises_on_reported_error(self, fake_comfy_server, monkeypatch):
        host, port = fake_comfy_server
        client = ComfyUIClient(base_url=f"http://{host}:{port}", poll_interval=0.01)

        def fake_get_history(prompt_id):
            return {"status": {"completed": False, "error": "out of VRAM"}}

        monkeypatch.setattr(client, "get_history", fake_get_history)
        with pytest.raises(ComfyUIError, match="out of VRAM"):
            client.wait_for_completion("fake-id")


class TestGenerate:
    def test_end_to_end(self, fake_comfy_server, tmp_path: Path):
        host, port = fake_comfy_server
        client = ComfyUIClient(base_url=f"http://{host}:{port}", poll_interval=0.01)
        outputs = client.generate({"3": {}}, tmp_path)
        assert outputs == []  # no queued outputs in the fake by default

    def test_fetches_queued_outputs(self, fake_comfy_server, tmp_path: Path):
        host, port = fake_comfy_server
        client = ComfyUIClient(base_url=f"http://{host}:{port}", poll_interval=0.01)

        # Patch do_POST to attach outputs to the next queued prompt
        original_do_post = FakeComfyUI.do_POST

        def patched_do_post(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            _ = json.loads(self.rfile.read(length).decode() or "{}")
            # Assign the prompt_id and outputs inline (don't call original — it would re-read the body)
            prompt_id = f"prompt-{type(self).next_prompt_id}"
            type(self).next_prompt_id += 1
            outputs_for_this_prompt = {
                "9": {"images": [{"filename": "test.png", "subfolder": "", "type": "output"}]}
            }
            type(self).history[prompt_id] = {
                "status": {"completed": True},
                "outputs": outputs_for_this_prompt,
            }
            self._json(200, {"prompt_id": prompt_id})

        FakeComfyUI.do_POST = patched_do_post
        try:
            outputs = client.generate({"3": {}}, tmp_path)
        finally:
            FakeComfyUI.do_POST = original_do_post

        assert len(outputs) == 1
        assert outputs[0].name == "test.png"


class TestGetClient:
    def test_returns_singleton(self):
        from scripts import comfyui_client
        comfyui_client._default_client = None
        a = comfyui_client.get_client(base_url="http://x:1")
        b = comfyui_client.get_client(base_url="http://x:1")
        assert a is b

    def test_recreates_on_url_change(self):
        from scripts import comfyui_client
        comfyui_client._default_client = None
        a = comfyui_client.get_client(base_url="http://a:1")
        b = comfyui_client.get_client(base_url="http://b:2")
        assert a is not b
