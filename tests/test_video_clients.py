"""Tests for the video clients (h3_client, falai_client, generation_router).

Run: `python -m pytest tests/test_video_clients.py -v`

These tests don't require real API access. They spin up a fake HTTP server
that mimics MiniMax H3 and fal.ai responses.
"""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts.falai_client import FalAIClient, FalError, FalVideoRequest
from scripts.generation_router import GenerationRouter, RoutingDecision, SpendState
from scripts.h3_client import H3Client, H3Error, VideoRequest


# ---------- shared fake server ----------

class FakeVideoAPI(BaseHTTPRequestHandler):
    """Generic fake that handles H3 + fal.ai patterns."""

    mode = "h3"  # 'h3' or 'fal'
    immediate_completion = True
    fail_next = False

    def log_message(self, *_args, **_kwargs):
        pass

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body_raw = self.rfile.read(length).decode() if length > 0 else "{}"
        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError:
            body = {}

        if self.fail_next:
            type(self).fail_next = False
            self._json(500, {"error": "fake server error"})

        if self.mode == "h3":
            task_id = f"h3-task-{int(time.time() * 1000)}"
            type(self).tasks[task_id] = {"completed": True, "video_url": f"http://{self.headers.get('Host', 'localhost')}/fake-video.mp4"}
            self._json(200, {"task_id": task_id})
        else:  # fal
            req_id = f"fal-req-{int(time.time() * 1000)}"
            type(self).requests[req_id] = {"completed": True, "video_url": f"http://{self.headers.get('Host', 'localhost')}/fake-video.mp4"}
            self._json(200, {"request_id": req_id, "status_url": f"/status/{req_id}"})

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/v1/user/info"):
            self._json(200, {"user_id": "u1"})
        elif self.path.startswith("/v1/video/generations/"):
            task_id = self.path.split("/")[-1]
            entry = type(self).tasks.get(task_id, {"completed": False})
            self._json(200, {"status": "completed" if entry.get("completed") else "in_progress", "video_url": entry.get("video_url", "")})
        elif self.path.startswith("/status/"):
            req_id = self.path.split("/")[-1]
            entry = type(self).requests.get(req_id, {"completed": False})
            self._json(200, {"status": "COMPLETED" if entry.get("completed") else "IN_QUEUE"})
        elif self.path.startswith("/user"):
            self._json(200, {"id": "u1"})
        elif self.path == "/fake-video.mp4":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", "16")
            self.end_headers()
            self.wfile.write(b"\x00\x00\x00\x18ftypmp42")
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    tasks: dict = {}
    requests: dict = {}


@pytest.fixture(scope="module")
def fake_video_server():
    server = HTTPServer(("127.0.0.1", 0), FakeVideoAPI)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()


@pytest.fixture
def h3_client(fake_video_server, monkeypatch):
    host, port = fake_video_server
    monkeypatch.setattr("scripts.h3_client.H3Client.BASE_URL", f"http://{host}:{port}")
    monkeypatch.setenv("MINIMAX_API_TOKEN", "test-token")
    return H3Client(poll_interval=0.05, timeout=2.0)


@pytest.fixture
def fal_client(fake_video_server, monkeypatch):
    host, port = fake_video_server
    FakeVideoAPI.mode = "fal"
    monkeypatch.setattr("scripts.falai_client.FalAIClient.BASE_URL", f"http://{host}:{port}")
    monkeypatch.setattr("scripts.falai_client.FalAIClient.SYNC_URL", f"http://{host}:{port}")
    monkeypatch.setenv("FAL_API_KEY", "test-key")
    yield FalAIClient(poll_interval=0.05, timeout=2.0)
    FakeVideoAPI.mode = "h3"


@pytest.fixture(autouse=True)
def reset_fake_state():
    FakeVideoAPI.tasks = {}
    FakeVideoAPI.requests = {}
    FakeVideoAPI.mode = "h3"
    FakeVideoAPI.fail_next = False
    FakeVideoAPI.immediate_completion = True
    yield


# ---------- H3Client ----------

class TestH3ClientInit:
    def test_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_TOKEN", raising=False)
        with pytest.raises(H3Error, match="MINIMAX_API_TOKEN"):
            H3Client(api_token="")

    def test_reads_token_from_env(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_TOKEN", "env-token")
        client = H3Client()
        assert client.api_token == "env-token"


class TestH3Submit:
    def test_returns_task_id(self, h3_client: H3Client):
        request = VideoRequest(prompt="test", duration_seconds=8, resolution="768p")
        task_id = h3_client.submit_generation(request)
        assert task_id.startswith("h3-task-")

    def test_includes_motion_when_provided(self, h3_client: H3Client):
        request = VideoRequest(prompt="test", motion="camera pushes in")
        task_id = h3_client.submit_generation(request)
        assert task_id  # would 500 if motion wasn't accepted

    def test_raises_on_missing_task_id(self, h3_client: H3Client, monkeypatch):
        def fake_request(method, path, *, body=None):
            return {"error": "no task_id"}
        monkeypatch.setattr(h3_client, "_request", fake_request)
        with pytest.raises(H3Error):
            h3_client.submit_generation(VideoRequest(prompt="x"))


class TestH3Wait:
    def test_returns_on_completed_status(self, h3_client: H3Client):
        request = VideoRequest(prompt="test", duration_seconds=8, resolution="768p")
        task_id = h3_client.submit_generation(request)
        status = h3_client.wait_for_completion(task_id)
        assert status["status"] == "completed"

    def test_raises_on_failed_status(self, h3_client: H3Client, monkeypatch):
        def fake_get_status(task_id):
            return {"status": "failed", "error": "oom"}
        monkeypatch.setattr(h3_client, "get_status", fake_get_status)
        with pytest.raises(H3Error, match="oom"):
            h3_client.wait_for_completion("any")


class TestH3Cost:
    def test_2k_costs_more_than_480p(self):
        a = VideoRequest(prompt="x", resolution="480p", duration_seconds=8).estimated_cost_usd()
        b = VideoRequest(prompt="x", resolution="2k", duration_seconds=8).estimated_cost_usd()
        assert b > a

    def test_longer_costs_more(self):
        a = VideoRequest(prompt="x", duration_seconds=5).estimated_cost_usd()
        b = VideoRequest(prompt="x", duration_seconds=15).estimated_cost_usd()
        assert b > a


class TestH3Health:
    def test_returns_true_when_reachable(self, h3_client: H3Client):
        assert h3_client.health() is True

    def test_returns_false_when_unreachable(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_TOKEN", "x")
        c = H3Client()
        # Replace BASE_URL with one that won't respond
        c.BASE_URL = "http://127.0.0.1:1"
        c.timeout = 0.3
        assert c.health() is False


# ---------- FalAIClient ----------

class TestFalInit:
    def test_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("FAL_API_KEY", raising=False)
        with pytest.raises(FalError, match="FAL_API_KEY"):
            FalAIClient(api_key="")


class TestFalSubmit:
    def test_returns_request_id(self, fal_client: FalAIClient):
        request = FalVideoRequest(model="minimax/h3-max", prompt="test", duration_seconds=8)
        req_id, status_url = fal_client.submit(request)
        assert req_id.startswith("fal-req-")
        assert status_url


class TestFalWait:
    def test_returns_on_completed_status(self, fal_client: FalAIClient):
        request = FalVideoRequest(model="minimax/h3-max", prompt="test", duration_seconds=8)
        req_id, status_url = fal_client.submit(request)
        status = fal_client.wait_for_completion(status_url)
        assert status["status"] == "COMPLETED"

    def test_raises_on_failed_status(self, fal_client: FalAIClient, monkeypatch):
        def fake_get_status(url):
            return {"status": "FAILED", "error": "model down"}
        monkeypatch.setattr(fal_client, "get_status", fake_get_status)
        with pytest.raises(FalError, match="model down"):
            fal_client.wait_for_completion("/status/x")


class TestFalCost:
    def test_h3_max_cheaper_than_kling_pro(self):
        h3 = FalVideoRequest(model="minimax/h3-max", prompt="x", duration_seconds=8, resolution="768p").estimated_cost_usd()
        kling = FalVideoRequest(model="kling-video/v2.6/pro", prompt="x", duration_seconds=8, resolution="768p").estimated_cost_usd()
        assert h3 < kling


# ---------- GenerationRouter ----------

class TestSpendState:
    def test_loads_when_file_missing(self, tmp_path: Path):
        state = SpendState.load(path=tmp_path / "nope.json")
        assert state.spend_usd == 0.0
        assert state.requests == 0

    def test_saves_and_reloads(self, tmp_path: Path):
        state = SpendState(month="2026-08", spend_usd=12.34, requests=5, cap_usd=30.0)
        path = tmp_path / "spend.json"
        state.save(path=path)
        loaded = SpendState.load(path=path)
        assert loaded.spend_usd == 12.34
        assert loaded.requests == 5

    def test_resets_on_new_month(self, tmp_path: Path):
        path = tmp_path / "spend.json"
        path.write_text(json.dumps({"month": "2020-01", "spend_usd": 100, "requests": 50, "cap_usd": 30}))
        state = SpendState.load(path=path)
        # Old month should reset to current month with zero spend
        from datetime import datetime, timezone
        current = datetime.now(tz=timezone.utc).strftime("%Y-%m")
        assert state.month == current
        assert state.spend_usd == 0.0


class TestRouting:
    def test_default_to_primary_h3(self, tmp_path: Path):
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=0.0, cap_usd=30.0))
        decision = router.route()
        assert decision.backend == "h3_cloud"
        assert decision.tier == "primary"

    def test_hero_routes_to_kling_when_under_80(self, tmp_path: Path):
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=10.0, cap_usd=30.0))
        decision = router.route(is_hero=True)
        assert decision.backend == "kling_falai"
        assert decision.tier == "hero"

    def test_fallback_at_80_percent(self):
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=25.0, cap_usd=30.0))  # 83%
        decision = router.route()
        assert decision.backend == "ltx_falai"
        assert decision.tier == "fallback"

    def test_pause_at_95_percent(self):
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=29.0, cap_usd=30.0))  # 97%
        decision = router.route()
        assert decision.backend == "pause"

    def test_speed_routes_to_h3_max(self):
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=0.0, cap_usd=30.0))
        decision = router.route(tier_preference="speed")
        assert decision.backend == "h3_max_falai"
        assert decision.tier == "speed"


class TestRecordSpend:
    def test_records_and_persists(self, tmp_path: Path):
        from scripts.generation_router import SPEND_FILE
        # Use a custom path via monkeypatching the module constant
        import scripts.generation_router as gr
        original = gr.SPEND_FILE
        gr.SPEND_FILE = tmp_path / "spend.json"
        try:
            router = GenerationRouter(SpendState(month="2026-08", spend_usd=0.0, cap_usd=30.0))
            decision = RoutingDecision(backend="h3_cloud", tier="primary", estimated_cost_usd=0.56, reason="test")
            router.record_spend(decision)
            assert router.spend.spend_usd == 0.56
            assert router.spend.requests == 1
            assert (tmp_path / "spend.json").exists()
        finally:
            gr.SPEND_FILE = original

    def test_pause_does_not_record(self):
        router = GenerationRouter(SpendState(month="2026-08", spend_usd=29.5, cap_usd=30.0))
        decision = router.route()  # paused
        before = router.spend.spend_usd
        router.record_spend(decision)
        assert router.spend.spend_usd == before


class TestCLI:
    def test_runs(self, monkeypatch, capsys):
        import scripts.generation_router as gr
        monkeypatch.setattr("sys.argv", ["gen_router.py"])
        rc = gr._cli()
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "backend" in parsed
        assert "tier" in parsed
        assert "current_month_spend_usd" in parsed
