"""tests/test_packaging_artifacts.py. Sanity-check that Phase B packaging
artifacts exist and are well-formed."""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_present_and_runs_python():
    df = ROOT / "Dockerfile"
    assert df.exists(), "Dockerfile missing"
    text = df.read_text()
    assert "FROM python" in text
    assert "app.server" in text or "calypso" in text
    assert "EXPOSE" in text


def test_dockerfile_uses_pip_e_and_pyproject():
    text = (ROOT / "Dockerfile").read_text()
    assert "pip install -e" in text, "Dockerfile should install Calypso as a package"


def test_docker_compose_has_calypso_and_caddy():
    compose = yaml_or_text(ROOT / "docker-compose.yml")
    assert "calypso" in compose
    assert "caddy" in compose.lower()
    assert "volumes:" in compose
    assert "8080" in compose


def test_caddyfile_present():
    caddyfile = ROOT / "Caddyfile"
    assert caddyfile.exists()
    text = caddyfile.read_text()
    assert "reverse_proxy" in text
    assert "calypso:8080" in text


def test_desktop_dir_layout():
    desktop = ROOT / "desktop"
    assert (desktop / "src-tauri" / "Cargo.toml").exists()
    assert (desktop / "src-tauri" / "tauri.conf.json").exists()
    assert (desktop / "src-tauri" / "src" / "main.rs").exists()
    assert (desktop / "package.json").exists()


def test_tauri_conf_valid_json_and_has_external_bin():
    conf_path = ROOT / "desktop" / "src-tauri" / "tauri.conf.json"
    data = json.loads(conf_path.read_text())
    assert data["productName"] == "Calypso"
    assert "externalBin" in data["bundle"]
    assert any("calypso-sidecar" in s for s in data["bundle"]["externalBin"])


def test_tauri_main_rs_spawns_sidecar_and_kills_on_exit():
    rs = (ROOT / "desktop" / "src-tauri" / "src" / "main.rs").read_text()
    assert "spawn_sidecar" in rs
    assert "Command::new" in rs
    assert "RunEvent::Exit" in rs
    assert "child.kill" in rs


def test_calypso_entry_imports_app_server():
    text = (ROOT / "scripts" / "calypso_entry.py").read_text()
    assert "from app.server import create_app" in text
    assert "app.run" in text
    assert "CALYPSO_HOST" in text
    assert "CALYPSO_PORT" in text


def test_pyi_spec_includes_web_dist_and_brand():
    spec = (ROOT / "scripts" / "calypso.spec").read_text()
    assert "web/dist" in spec
    assert "brand" in spec
    assert "calypso_entry.py" in spec


def test_desktop_build_script_present_and_executable():
    script = ROOT / "scripts" / "desktop-build.sh"
    assert script.exists()
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "desktop-build.sh must be executable"


def test_self_host_script_present_and_executable():
    script = ROOT / "scripts" / "self-host.sh"
    assert script.exists()
    assert script.stat().st_mode & stat.S_IXUSR


def test_backup_script_present_and_executable():
    script = ROOT / "scripts" / "backup.sh"
    assert script.exists()
    assert script.stat().st_mode & stat.S_IXUSR


def test_backup_script_excludes_wal_shm():
    text = (ROOT / "scripts" / "backup.sh").read_text()
    assert "calypso.db-wal" in text
    assert "calypso.db-shm" in text


def test_desktop_build_uses_pyinstaller_spec():
    text = (ROOT / "scripts" / "desktop-build.sh").read_text()
    assert "pyinstaller" in text.lower()
    assert "calypso.spec" in text
    assert "Tauri" in text or "tauri" in text


# ---------- helpers ----------


def yaml_or_text(path: Path) -> str:
    """Lightweight: we don't need a YAML parser, just substring checks."""
    return path.read_text()


def test_sidecar_port_constant():
    rs = (ROOT / "desktop" / "src-tauri" / "src" / "main.rs").read_text()
    assert re.search(r"DEFAULT_PORT:\s*u16\s*=\s*\d+", rs)
