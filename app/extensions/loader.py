"""app/extensions/loader.py. Discovers, validates, and activates extensions.

Extension discovery walks a directory (default `~/.calypso/extensions/`,
configurable via `CALYPSO_EXTENSIONS_DIR`). Each subdirectory is treated
as one extension. Activation is opt-in via `enable()` / `disable()` so
users can keep extensions installed but turn them off.

Built-in extensions ship inside `app/extensions/builtin/` and are
auto-loaded at startup. Community extensions come from the directory
listed above.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Iterable

from .manifest import (
    ExtensionManifest,
    ManifestError,
    compute_checksum,
    parse_manifest,
    verify_signature,
)

log = logging.getLogger(__name__)

_LOCK = threading.RLock()

# --- paths -----------------------------------------------------------------

BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"
DEFAULT_EXT_DIR = Path(os.environ.get("CALYPSO_EXTENSIONS_DIR",
                                      "~/.calypso/extensions")).expanduser()


# --- state ----------------------------------------------------------------


class _Registry:
    def __init__(self) -> None:
        self.manifests: dict[str, ExtensionManifest] = {}
        self.enabled: set[str] = set()
        self.hooks: dict[str, list[Any]] = {}
        # extensions/builtin ships a state file in CALYPSO_HOME.
        self.state_path: Path | None = None

    def hook(self, name: str) -> list[Any]:
        return self.hooks.setdefault(name, [])

    def state(self) -> dict[str, Any]:
        return {"enabled": sorted(self.enabled)}


_REGISTRY = _Registry()


def registry() -> _Registry:
    return _REGISTRY


# --- discovery ------------------------------------------------------------


def discover(source: Path | None = None) -> list[ExtensionManifest]:
    """Walk the directory and parse every manifest. Returns the discovered
    set; use `registry()` to inspect or activate them."""
    dirs: list[Path] = [BUILTIN_DIR]
    if source is not None:
        dirs.insert(0, source)
    elif DEFAULT_EXT_DIR.exists():
        dirs.append(DEFAULT_EXT_DIR)
    manifests: dict[str, ExtensionManifest] = {}
    for d in dirs:
        if not d.exists():
            continue
        for child in sorted(d.iterdir()):
            if not child.is_dir():
                continue
            m_path = child / "calypso-extension.json"
            try:
                m = parse_manifest(m_path)
            except ManifestError as exc:
                log.warning("skip %s: %s", child, exc)
                continue
            # If checksum is declared, verify it. If not, auto-compute so
            # the marketplace can sign later without surprises.
            file_sum = compute_checksum(child)
            if m.checksum and m.checksum != file_sum:
                log.warning("skip %s: checksum mismatch", child)
                continue
            if not m.checksum:
                m.checksum = file_sum
            manifests[m.id] = m
    with _LOCK:
        _REGISTRY.manifests = manifests
    return list(manifests.values())


def enable(ext_id: str, *, secret: str | None = None) -> bool:
    with _LOCK:
        m = _REGISTRY.manifests.get(ext_id)
        if not m:
            return False
        if secret and m.signature and not verify_signature(m, secret):
            log.warning("refusing to enable %s: bad signature", ext_id)
            return False
        _REGISTRY.enabled.add(ext_id)
    _activate(m)
    _persist_state()
    return True


def disable(ext_id: str) -> bool:
    with _LOCK:
        if ext_id not in _REGISTRY.enabled:
            return False
        _REGISTRY.enabled.discard(ext_id)
    _persist_state()
    return True


def is_enabled(ext_id: str) -> bool:
    return ext_id in _REGISTRY.enabled


def list_extensions() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with _LOCK:
        for m in _REGISTRY.manifests.values():
            out.append({
                "id": m.id,
                "version": m.version,
                "type": m.type,
                "name": m.name,
                "author": m.author,
                "description": m.description,
                "homepage": m.homepage,
                "license": m.license,
                "checksum": m.checksum,
                "signed": bool(m.signature),
                "enabled": m.id in _REGISTRY.enabled,
            })
    return out


# --- activation ----------------------------------------------------------


def _activate(m: ExtensionManifest) -> None:
    """Import the extension's Python module (if present) and register its
    handlers with the appropriate core modules."""
    ext_py = m.path / "extension.py" if m.path else None
    if not ext_py or not ext_py.exists():
        return
    spec = importlib.util.spec_from_file_location(
        f"calypso_extension_{m.id}", ext_py,
    )
    if not spec or not spec.loader:
        log.warning("extension %s: could not load %s", m.id, ext_py)
        return
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001
        log.warning("extension %s: import failed: %s", m.id, exc)
        return
    register = getattr(mod, "register", None)
    if callable(register):
        try:
            register(_REGISTRY.hook)
        except Exception as exc:  # noqa: BLE001
            log.warning("extension %s: register() raised: %s", m.id, exc)


# --- built-in extensions -------------------------------------------------


def load_builtin_extensions() -> list[ExtensionManifest]:
    """Discover + auto-enable every built-in extension."""
    found = discover()
    auto = [m for m in found if (m.path / "extension.py").exists()
            and (m.path / "auto_enable.txt").exists()]
    for m in auto:
        enable(m.id)
    return found


# --- state persistence --------------------------------------------------


def _persist_state() -> None:
    """Save enabled-extensions list to `<CALYPSO_HOME>/extensions.json`."""
    state_path = _REGISTRY.state_path
    if state_path is None:
        home = Path(os.environ.get("CALYPSO_HOME",
                                   "~/.calypso")).expanduser()
        try:
            home.mkdir(parents=True, exist_ok=True)
            state_path = home / "extensions.json"
            _REGISTRY.state_path = state_path
        except Exception:  # noqa: BLE001
            return
    try:
        state_path.write_text(json.dumps(_REGISTRY.state(), indent=2))
    except Exception as exc:  # noqa: BLE001
        log.warning("could not persist extensions state: %s", exc)


def restore_state() -> None:
    """Re-enable every extension that was enabled at last shutdown."""
    home = Path(os.environ.get("CALYPSO_HOME", "~/.calypso")).expanduser()
    p = home / "extensions.json"
    if not p.exists():
        return
    _REGISTRY.state_path = p
    try:
        data = json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return
    for ext_id in data.get("enabled", []):
        enable(ext_id)


# --- convenience for tests -----------------------------------------------


def reset_for_tests() -> None:
    with _LOCK:
        _REGISTRY.manifests.clear()
        _REGISTRY.enabled.clear()
        _REGISTRY.hooks.clear()
        _REGISTRY.state_path = None


def iterate_hooks(name: str) -> Iterable[Any]:
    """Iterate registered handlers for `name` (e.g. 'channel.email')."""
    return list(_REGISTRY.hook(name))
