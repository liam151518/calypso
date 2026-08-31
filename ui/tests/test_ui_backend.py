"""Tests for the FastAPI backend exposed at ui/server/app.py.

Run: `python -m pytest ui/tests/test_ui_backend.py -v`
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the server module importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app import app, PROJECT_ROOT  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


class TestOverview:
    def test_returns_expected_keys(self, client: TestClient):
        r = client.get("/overview")
        assert r.status_code == 200
        data = r.json()
        for key in ["tests_pass", "tests_total", "verify_pass", "scripts", "workflows", "brand_files"]:
            assert key in data, f"missing key {key}"

    def test_scripts_count_positive(self, client: TestClient):
        r = client.get("/overview")
        assert r.json()["scripts"] > 0

    def test_workflows_count_positive(self, client: TestClient):
        r = client.get("/overview")
        assert r.json()["workflows"] > 0


class TestPhases:
    def test_returns_list(self, client: TestClient):
        r = client.get("/phases")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 6

    def test_each_phase_has_keys(self, client: TestClient):
        for p in client.get("/phases").json():
            for key in ["id", "name", "status", "summary", "deliverables"]:
                assert key in p, f"phase {p.get('id')} missing {key}"

    def test_phase_ids_unique(self, client: TestClient):
        ids = [p["id"] for p in client.get("/phases").json()]
        assert len(ids) == len(set(ids))


class TestScripts:
    def test_returns_list(self, client: TestClient):
        r = client.get("/scripts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 5  # we have 14

    def test_each_script_has_keys(self, client: TestClient):
        for s in client.get("/scripts").json():
            for key in ["name", "path", "has_cli", "description"]:
                assert key in s

    def test_script_run_with_help(self, client: TestClient):
        # reference_picker.py supports --help
        r = client.post("/scripts/run", json={"name": "reference_picker", "args": ["--help"]})
        assert r.status_code == 200
        data = r.json()
        assert "exit_code" in data
        assert "stdout" in data

    def test_script_run_404_for_unknown(self, client: TestClient):
        r = client.post("/scripts/run", json={"name": "nonexistent_script", "args": []})
        assert r.status_code == 404


class TestBrand:
    def test_returns_list(self, client: TestClient):
        r = client.get("/brand")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_files_have_path_and_size(self, client: TestClient):
        for f in client.get("/brand").json():
            assert "path" in f
            assert "size" in f
            assert isinstance(f["size"], int)


class TestWorkflows:
    def test_returns_list(self, client: TestClient):
        r = client.get("/workflows")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 2  # at least the 2 n8n workflows

    def test_each_workflow_has_keys(self, client: TestClient):
        for w in client.get("/workflows").json():
            assert "name" in w
            assert "nodes" in w
            assert isinstance(w["nodes"], int)


class TestAccounts:
    def test_returns_list(self, client: TestClient):
        r = client.get("/accounts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 8

    def test_required_accounts_marked(self, client: TestClient):
        for a in client.get("/accounts").json():
            if a["name"] in ["MiniMax (H3)", "fal.ai", "Telegram Bot"]:
                assert a["required"] is True

    def test_env_key_present(self, client: TestClient):
        for a in client.get("/accounts").json():
            assert a["env_key"]
            assert a["env_present"] in (True, False)


class TestAdam:
    def test_status(self, client: TestClient):
        r = client.get("/adam/status")
        assert r.status_code == 200
        data = r.json()
        assert "installed_at_user_level" in data
        assert "installed_at_project_level" in data
        assert "ready" in data
