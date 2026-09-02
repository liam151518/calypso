"""Tests for app/upscale.py + the upscale API endpoint."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest


# ---- PIL fallback: a tiny "upscale" via Lanczos resize ---------------------


def _make_tiny_png(path: Path, w: int = 64, h: int = 64) -> None:
    """Write a real PNG so PIL / Real-ESRGAN can read it."""
    from PIL import Image
    Image.new("RGB", (w, h), color=(180, 90, 200)).save(path, "PNG")


# ---- upscale.upscale() ------------------------------------------------


class TestUpscaleValidation:
    def test_invalid_scale_raises(self, tmp_path):
        from app import upscale as up
        src = tmp_path / "in.png"
        _make_tiny_png(src)
        with pytest.raises(ValueError, match="scale must be 2 or 4"):
            up.upscale(str(src), scale=3)

    def test_missing_file_raises(self, tmp_path):
        from app import upscale as up
        with pytest.raises(FileNotFoundError):
            up.upscale(str(tmp_path / "nope.png"))

    def test_unknown_model_raises(self, tmp_path):
        from app import upscale as up
        src = tmp_path / "in.png"
        _make_tiny_png(src)
        with pytest.raises(ValueError, match="unknown model"):
            up.upscale(str(src), model="not_a_thing")


class TestUpscaleRealesrganFallback:
    """When the local binary is missing, `realesrgan` must transparently
    fall back to fal.ai. Tests bypass both by mocking the fal path."""

    def test_falls_back_to_fal_when_no_binary(
            self, tmp_path, monkeypatch):
        from app import upscale as up

        src = tmp_path / "in.png"
        _make_tiny_png(src)

        # Force "binary missing"
        monkeypatch.setattr(up, "_realesrgan_binary", lambda: None)
        monkeypatch.setattr(up, "_upscale_realesrgan",
                            lambda *a, **kw: (_ for _ in ()).throw(
                                RuntimeError("not installed")))
        monkeypatch.setattr(up, "_upscale_fal",
                            lambda src, **kw: up.UpscaleResult(
                                file_path=str(tmp_path / "out.png"),
                                cost_usd=0.04, scale=4,
                                model_used="fal", width=256, height=256,
                            ))

        result = up.upscale(str(src), scale=4, model="realesrgan")
        assert result.model_used == "fal"
        assert result.scale == 4
        assert len(result.warnings or []) == 1
        assert "local realesrgan failed" in result.warnings[0]

    def test_raises_when_both_backends_fail(
            self, tmp_path, monkeypatch):
        from app import upscale as up

        src = tmp_path / "in.png"
        _make_tiny_png(src)
        monkeypatch.setattr(up, "_upscale_realesrgan",
                            lambda *a, **kw: (_ for _ in ()).throw(
                                RuntimeError("not installed")))
        monkeypatch.setattr(up, "_upscale_fal",
                            lambda *a, **kw: (_ for _ in ()).throw(
                                RuntimeError("api down")))

        with pytest.raises(RuntimeError, match="both upscalers failed"):
            up.upscale(str(src), scale=4, model="realesrgan")


class TestUpscaleFalDirect:
    """When model='fal' we go straight to the cloud path. We mock it to
    avoid network calls."""

    def test_fal_returns_result(self, tmp_path, monkeypatch):
        from app import upscale as up

        src = tmp_path / "in.png"
        _make_tiny_png(src)

        def fake_fal(src, **kw):
            out = src.with_name("out.png")
            _make_tiny_png(out, w=256, h=256)
            return up.UpscaleResult(
                file_path=str(out), cost_usd=0.02, scale=4,
                model_used="fal", width=256, height=256,
                face_enhance=kw.get("face_enhance", False),
            )

        monkeypatch.setattr(up, "_upscale_fal", fake_fal)
        result = up.upscale(str(src), scale=4, model="fal", face_enhance=True)
        assert result.model_used == "fal"
        assert result.face_enhance is True
        assert result.cost_usd == 0.02


class TestUpscaleRealesrganDirect:
    """When the binary IS present, we shell out to it."""

    def test_shells_out_to_realesrgan(self, tmp_path, monkeypatch):
        from app import upscale as up

        src = tmp_path / "in.png"
        _make_tiny_png(src)

        out_path = tmp_path / "in_x4.png"
        # Real-ESRGAN ncnn uses args -i IN -o OUT -s SCALE -n MODEL.
        # The 4th positional arg is the output path.
        fake_bin = tmp_path / "fake-realesrgan.sh"
        fake_bin.write_text("#!/bin/sh\n# $1=-i $2=in $3=-o $4=out $5=-s ...\n"
                            f"cp \"$2\" \"{out_path}\"\n")
        fake_bin.chmod(0o755)

        monkeypatch.setattr(up, "_realesrgan_binary", lambda: str(fake_bin))
        result = up.upscale(str(src), scale=4, model="realesrgan")
        assert result.file_path == str(out_path)
        assert result.model_used == "realesrgan"
        assert result.cost_usd == 0.0

    def test_handles_binary_failure_falls_back_to_fal(
            self, tmp_path, monkeypatch):
        """When the binary errors out, upscale() transparently falls back
        to the fal path (or its offline PIL equivalent)."""
        from app import upscale as up

        src = tmp_path / "in.png"
        _make_tiny_png(src)

        fake_bin = tmp_path / "broken.sh"
        fake_bin.write_text("#!/bin/sh\nexit 1\n")
        fake_bin.chmod(0o755)

        monkeypatch.setattr(up, "_realesrgan_binary", lambda: str(fake_bin))
        # monkeypatch.delenv ensures the PIL fallback path inside _upscale_fal
        # is exercised instead of the real fal-client call.
        monkeypatch.delenv("FAL_API_KEY", raising=False)
        result = up.upscale(str(src), scale=4, model="realesrgan")
        assert result.model_used == "fal_fallback"
        assert any("local realesrgan failed" in w for w in result.warnings)


# ---- upscale_output() -------------------------------------------------


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    from app import db as app_db
    target = tmp_path / "up.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


@pytest.fixture
def seeded_output(fresh_db, tmp_path):
    """Create an output row whose file_path actually exists on disk."""
    from app import db as app_db
    now = time.time()
    image_path = tmp_path / "orig.png"
    _make_tiny_png(image_path, w=64, h=64)
    with app_db.connect() as c:
        c.execute(
            "INSERT INTO brands (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("UpscaleBrand", now, now),
        )
        bid = c.execute(
            "SELECT id FROM brands WHERE name='UpscaleBrand'"
        ).fetchone()[0]
        c.execute(
            "INSERT INTO outputs (brand_id, type, file_path, status, "
            "created_at, layers_json, filter_settings) "
            "VALUES (?, 'image', ?, 'draft', ?, '[]', '{}')",
            (bid, str(image_path), now),
        )
        oid = c.execute(
            "SELECT id FROM outputs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    return oid, image_path


def test_upscale_output_writes_version(fresh_db, seeded_output,
                                       monkeypatch):
    from app import refinement as refine
    from app import upscale as up

    oid, src = seeded_output

    def fake_fal(src, **kw):
        out = Path(src).with_name("up.png")
        _make_tiny_png(out, w=256, h=256)
        return up.UpscaleResult(
            file_path=str(out), cost_usd=0.03, scale=4,
            model_used="fal", width=256, height=256,
        )
    monkeypatch.setattr(up, "_upscale_fal", fake_fal)

    result = refine.upscale_output(oid, scale=4, model="fal")
    assert result["upscale"].model_used == "fal"
    assert Path(result["version"]["file_path"]).exists()
    assert "upscale x4" in result["version"]["notes"]

    # New version was recorded
    versions = refine.list_versions(oid)
    assert len(versions) == 1
    assert versions[0]["file_path"] == result["version"]["file_path"]


def test_upscale_output_unknown_output_raises(fresh_db):
    from app import refinement as refine
    with pytest.raises(ValueError, match="not found"):
        refine.upscale_output(999999, scale=4)


def test_upscale_output_no_file_raises(fresh_db, seeded_output, tmp_path):
    """Output references a file that no longer exists on disk."""
    from app import refinement as refine
    oid, src = seeded_output
    # Delete the file
    src.unlink()
    with pytest.raises(ValueError, match="no file on disk"):
        refine.upscale_output(oid, scale=4)


# ---- API endpoint -----------------------------------------------------


@pytest.fixture
def app_with_db(fresh_db):
    from app.server import create_app
    return create_app()


@pytest.fixture
def client(app_with_db):
    return app_with_db.test_client()


def test_api_upscale_returns_version(client, seeded_output, monkeypatch):
    from app import upscale as up
    oid, src = seeded_output

    def fake_fal(src, **kw):
        out = Path(src).with_name("api_up.png")
        _make_tiny_png(out, w=256, h=256)
        return up.UpscaleResult(
            file_path=str(out), cost_usd=0.03, scale=4,
            model_used="fal", width=256, height=256,
            face_enhance=kw.get("face_enhance", False),
        )
    monkeypatch.setattr(up, "_upscale_fal", fake_fal)

    res = client.post(f"/api/outputs/{oid}/upscale", json={
        "scale": 4, "model": "fal", "face_enhance": True,
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["upscale"]["model_used"] == "fal"
    assert data["upscale"]["face_enhance"] is True
    assert data["version"]["file_path"].endswith("api_up.png")


def test_api_upscale_invalid_scale_returns_400(client, seeded_output):
    oid, _ = seeded_output
    res = client.post(f"/api/outputs/{oid}/upscale", json={"scale": 3})
    assert res.status_code == 400


def test_api_upscale_unknown_output_returns_404(client):
    res = client.post("/api/outputs/999999/upscale", json={"scale": 4})
    assert res.status_code == 404
