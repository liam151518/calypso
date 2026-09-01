"""Tests for app/image_jobs.py — image generation registry and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import image_jobs, settings, server


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch):
    """Point OUTPUTS_DIR + .env at temp paths so tests are hermetic."""
    monkeypatch.setattr(settings, "ENV_PATH", tmp_path / ".env")
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(image_jobs, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(image_jobs, "_IMAGE_JOBS", {})
    return tmp_path


def test_create_image_job_minimal(isolated):
    job = image_jobs.create_image_job("a hero shot of a samurai helmet")
    assert job.status == "queued"
    assert job.prompt == "a hero shot of a samurai helmet"
    assert job.aspect_ratio == "1:1"
    assert job.num_images == 1


def test_create_image_job_persists_in_registry(isolated):
    j1 = image_jobs.create_image_job("one")
    j2 = image_jobs.create_image_job("two", model="imagen-3", num_images=2)
    assert image_jobs.get_image_job(j1.job_id) is j1
    assert image_jobs.get_image_job(j2.job_id) is j2
    listing = image_jobs.list_image_jobs()
    assert {j.job_id for j in listing} == {j1.job_id, j2.job_id}


def test_to_dict_shape(isolated):
    job = image_jobs.create_image_job(
        "test",
        model="flux-pro/v1.1",
        aspect_ratio="16:9",
        num_images=2,
    )
    data = job.to_dict()
    assert data["prompt"] == "test"
    assert data["model"] == "flux-pro/v1.1"
    assert data["aspect_ratio"] == "16:9"
    assert data["num_images"] == 2
    assert data["status"] == "queued"
    assert "output_rel" in data


def test_extract_image_urls_handles_dict_list():
    result = {"images": [{"url": "https://x/a.png"}, {"url": "https://x/b.png"}]}
    assert image_jobs._extract_image_urls(result) == [
        "https://x/a.png",
        "https://x/b.png",
    ]


def test_extract_image_urls_handles_singular_image():
    result = {"image": {"url": "https://x/single.png"}}
    assert image_jobs._extract_image_urls(result) == ["https://x/single.png"]


def test_extract_image_urls_empty_when_unrecognised():
    assert image_jobs._extract_image_urls({"foo": "bar"}) == []
    assert image_jobs._extract_image_urls({}) == []


def test_guess_ext():
    assert image_jobs._guess_ext("https://x/y.png") == "png"
    assert image_jobs._guess_ext("https://x/y.JPG") == "jpg"
    assert image_jobs._guess_ext("https://x/y.jpeg?cache=1") == "jpg"
    assert image_jobs._guess_ext("https://x/y") == "png"


def test_rel_for_first_returns_none_when_empty():
    assert image_jobs._rel_for_first([]) is None


def test_rel_for_first_builds_url(isolated):
    path = str(image_jobs.OUTPUTS_DIR / "abc123" / "image-1.png")
    rel = image_jobs._rel_for_first([path])
    assert rel == "/outputs/file/abc123/image-1.png"


def test_run_image_job_fails_without_fal_key(isolated):
    job = image_jobs.create_image_job("no key here")
    image_jobs.run_image_job(job)
    assert job.status == "failed"
    assert job.error is not None
    assert "FAL_API_KEY" in job.error


def test_read_fal_key_uses_settings(isolated):
    # Empty .env → empty key
    assert image_jobs._read_fal_key() == ""
    # .env with a value
    (isolated / ".env").write_text("FAL_API_KEY=abc123\n")
    assert image_jobs._read_fal_key() == "abc123"
