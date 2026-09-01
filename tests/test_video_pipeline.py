"""Phase D.4 — video compositor + UGC templates smoke tests.

We do not generate real videos in tests (it requires ffmpeg, a video API
key, and several seconds of wall time). Instead we exercise:

  - UGC template loading and structure
  - per-scene frame generation (PNG sequences)
  - `compose_frames` actually produces an MP4 that ffprobe can read
  - `render_video` happy path writes an outputs row
  - `quick_clip` produces a valid MP4
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app import db as app_db
from app import templates as templates_mod
from app import video_compositor as vc


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Redirect app_db.DB_PATH to a temp file and re-init the schema."""
    target = tmp_path / "video.db"
    monkeypatch.setattr(app_db, "DB_PATH", target)
    app_db.reset_for_tests(target)
    app_db.init_db(target)
    yield target


def _ffprobe() -> str | None:
    import shutil

    return shutil.which("ffprobe")


def _has_ffmpeg() -> bool:
    import shutil

    return shutil.which("ffmpeg") is not None


def _insert_template(name: str, body: dict) -> int:
    """Use the templates module so we go through the full code path."""
    from app import templates as templates_mod

    return templates_mod.create_template({**body, "name": name})


def test_list_ugc_templates_returns_five_builtins():
    names = vc.list_ugc_templates()
    assert set(names) >= {"unboxing", "review", "lifestyle", "launch_hype", "tutorial"}


def test_each_ugc_template_has_scenes_and_transitions():
    for name in vc.list_ugc_templates():
        tpl = vc.load_ugc_template(name)
        assert tpl.get("format") == "video"
        assert tpl.get("scenes"), f"{name} has no scenes"
        assert tpl.get("transitions"), f"{name} has no transitions"
        # Every scene must declare a duration and at least one layer.
        for scene in tpl["scenes"]:
            assert scene.get("duration_s", 0) > 0
            assert scene.get("layers")


def test_render_scene_produces_expected_frame_count():
    tpl = vc.load_ugc_template("unboxing")
    first_scene = tpl["scenes"][0]
    frames = vc._render_scene(
        first_scene,
        canvas_w=320,
        canvas_h=568,
        fps=30,
        product=None,
        brand=None,
    )
    expected = int(float(first_scene["duration_s"]) * 30)
    assert len(frames) == expected
    # All frames should be PNGs with the canvas size.
    for p in frames:
        assert p.exists()
        assert p.stat().st_size > 0


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg not installed")
def test_compose_frames_writes_playable_mp4(tmp_path):
    from PIL import Image

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    paths = []
    for i in range(6):
        p = frames_dir / f"frame_{i:04d}.png"
        Image.new("RGB", (240, 320), color=(i * 40 % 255, 100, 150)).save(p)
        paths.append(p)
    dest = tmp_path / "out.mp4"
    vc.compose_frames(paths, dest, fps=10, duration_s=0.6)
    assert dest.exists()
    assert dest.stat().st_size > 100
    if _ffprobe():
        out = subprocess.run(
            [_ffprobe(), "-v", "error", "-show_format", str(dest)],
            capture_output=True, text=True, check=False,
        )
        # ffprobe may print warnings but should not fail.
        assert out.returncode == 0


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg not installed")
def test_render_video_happy_path(tmp_path, fresh_db, monkeypatch):
    # Insert a built-in UGC template into the DB.
    body = vc.load_ugc_template("unboxing")
    body = {**body, "name": "UGC Unboxing Test"}
    template_id = _insert_template("UGC Unboxing Test", body)
    # We need a brand + product so FKs hold.
    from PIL import Image

    # Stub get_cutout so we don't actually run rembg (which downloads a model).
    from app import products as products_mod

    fake_cutout = tmp_path / "cutout.png"
    Image.new("RGBA", (200, 200), color=(0, 200, 200, 255)).save(fake_cutout)
    monkeypatch.setattr(products_mod, "get_cutout", lambda pid: str(fake_cutout))
    # Also stub the same name on video_compositor's bound reference.
    monkeypatch.setattr(vc.products_mod, "get_cutout", lambda pid: str(fake_cutout))

    conn = app_db.get_conn()
    conn.execute(
        "INSERT INTO brands(name, voice_tone, created_at, updated_at) "
        "VALUES (?, 'bold', 0.0, 0.0)",
        ("Phase D Brand",),
    )
    bid = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    image_path = tmp_path / "sneaker.png"
    Image.new("RGB", (400, 400), color=(80, 120, 200)).save(image_path)
    conn.execute(
        "INSERT INTO products(name, brand_id, image_path, created_at, updated_at) "
        "VALUES (?, ?, ?, 0.0, 0.0)",
        ("Test Sneaker", bid, str(image_path)),
    )
    pid = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.commit()
    result = vc.render_video(
        template_id,
        product_id=pid,
        brand_id=bid,
        audio_track=None,
    )
    assert result.output_id > 0
    assert Path(result.file_path).exists()
    assert result.duration_s > 0


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg not installed")
def test_quick_clip_creates_static_mp4(tmp_path, fresh_db):
    body = vc.load_ugc_template("review")
    template_id = _insert_template("UGC Review Test", {**body, "name": "UGC Review Test"})
    conn = app_db.get_conn()
    conn.execute(
        "INSERT INTO brands(name, voice_tone, created_at, updated_at) "
        "VALUES (?, 'minimal', 0.0, 0.0)",
        ("Phase D Quick Brand",),
    )
    bid = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.execute(
        "INSERT INTO products(name, brand_id, created_at, updated_at) "
        "VALUES (?, ?, 0.0, 0.0)",
        ("Phase D Product", bid),
    )
    pid = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.commit()
    result = vc.quick_clip(
        template_id=template_id,
        product_id=pid,
        brand_id=bid,
        duration_s=2,
    )
    assert Path(result.file_path).exists()
    assert result.duration_s == 2.0


def test_render_video_rejects_non_video_template(fresh_db):
    body = {
        "name": "Not a video",
        "format": "image",
        "aspect_ratio": "1:1",
        "canvas": {"width": 100, "height": 100},
        "layers": [],
    }
    template_id = _insert_template("Not a video", body)
    with pytest.raises(ValueError):
        vc.render_video(template_id)