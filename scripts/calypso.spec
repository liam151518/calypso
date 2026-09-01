# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Calypso desktop sidecar.

Build:    pyinstaller scripts/calypso.spec --noconfirm --clean
Output:   dist/calypso-sidecar (or .exe on Windows)

Single-file build for easy distribution. The `--collect-all app` flag ensures
every module under `app/` (including extensions like Phase A pipelines,
Phase C agents, Phase D extensions) is bundled correctly.
"""

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).parent  # PyInstaller sets SPECPATH to the spec file dir.
APP_DIR = ROOT / "app"

datas = [
    # The built SPA. Served by Flask from web/dist/ at runtime.
    (str(ROOT / "web" / "dist"), "web/dist"),
    # Brand and reference assets. These are user-editable but we ship
    # them by default so the app has something to show on first boot.
    (str(ROOT / "brand"), "brand"),
    (str(ROOT / "references"), "references"),
]

hiddenimports = [
    "app",
    "app.server",
    "app.db",
    "app.refs",
    "app.drafts",
    "app.brand",
    "app.jobs",
    "app.image_jobs",
    "app.models",
    "app.settings",
    "app.pipelines",
    "app.pipeline_nodes",
    "app.node_schema",
]

a = Analysis(
    [str(ROOT / "scripts" / "calypso_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="calypso-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
