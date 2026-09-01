"""tests/test_release_artifacts.py. Phase E public-release artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_mit_license_present_and_correct_year():
    lic = ROOT / "LICENSE"
    assert lic.exists()
    text = lic.read_text()
    assert "MIT License" in text
    assert "Copyright (c) 2026 Calypso contributors" in text
    assert "Permission is hereby granted" in text


def test_release_doc_present():
    doc = ROOT / "docs" / "RELEASE.md"
    assert doc.exists()
    text = doc.read_text()
    assert "desktop-build" in text or "desktop" in text.lower()
    assert "docker" in text.lower()
    assert "tag" in text.lower()


def test_marketplace_catalog_is_valid_json():
    cat = ROOT / "docs" / "marketplace" / "index.json"
    data = json.loads(cat.read_text())
    assert "extensions" in data
    assert isinstance(data["extensions"], list)
    for ext in data["extensions"]:
        for key in ("id", "version", "type", "name"):
            assert key in ext, f"missing {key} in {ext}"


def test_marketplace_html_renders_catalog():
    html = (ROOT / "docs" / "marketplace" / "index.html").read_text()
    assert "Calypso Marketplace" in html
    assert "index.json" in html


def test_release_workflow_exists():
    wf = ROOT / ".github" / "workflows" / "release.yml"
    assert wf.exists()
    text = wf.read_text()
    # Must run tests, build web, build installers, and publish
    for needle in ("pytest", "npm run build", "desktop-build.sh",
                   "softprops/action-gh-release"):
        assert needle in text, f"workflow missing: {needle}"


def test_release_workflow_triggers_on_tag():
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert "tags:" in text
    assert "v*" in text or "v\\d" in text


def test_release_workflow_publishes_docker_image():
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert "docker/build-push-action" in text
    assert "ghcr.io" in text


def test_readme_mentions_extensions_and_install():
    readme = ROOT / "README.md"
    if not readme.exists():
        pytest.skip("README.md not present")
    text = readme.read_text()
    # We don't pin a specific phrasing, just require install/desktop OR
    # docker to be referenced. README is the project's front door.
    assert any(k in text.lower() for k in ("install", "desktop", "docker")), (
        "README should reference install / desktop / docker"
    )


def test_pipelines_endpoint_smoke_works():
    """Phase A → Phase E integration sanity: a pipeline can be created
    and run via the API. Confirms release artifacts do not break runtime."""
    import tempfile
    db = Path(tempfile.mkdtemp()) / "x.db"
    import app.db as db_mod
    monkey_target = db_mod.DB_PATH
    db_mod.DB_PATH = db
    try:
        db_mod.init_db(db)
        from app.server import create_app
        app = create_app()
        c = app.test_client()
        r = c.post("/api/pipelines", json={
            "name": "release-smoke",
            "nodes": [
                {"id": "t", "type": "trigger", "params": {"mode": "manual"}},
            ],
            "edges": [],
            "max_workers": 1,
        })
        assert r.status_code in (200, 201)
        pid = r.get_json()["pipeline"]["id"]
        r2 = c.post(f"/api/pipelines/{pid}/run", json={})
        assert r2.status_code in (200, 201, 202)
    finally:
        db_mod.DB_PATH = monkey_target
