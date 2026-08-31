"""app/settings.py — read/write the local .env file.

We treat .env as the single source of truth for API keys. The UI lists known
services, masks current values, and writes back on save. We never log a key
in plaintext.

Used by: app/server.py (Settings routes), app/jobs.py (read keys before each gen).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Project root is two levels up from this file (app/settings.py -> app/ -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
EXAMPLE_ENV_PATH = PROJECT_ROOT / ".env.example"

# The keys the UI knows how to surface. Adding a new service means adding it here.
# `service` is the human-readable name; `env_var` is the actual .env key.
KNOWN_KEYS: list[dict[str, str]] = [
    {"service": "fal.ai", "env_var": "FAL_API_KEY", "placeholder": "fal-xxxxxxxx"},
    {"service": "MiniMax (H3 cloud)", "env_var": "MINIMAX_API_KEY", "placeholder": "sk-xxxxxxxx"},
    {"service": "Telegram bot", "env_var": "TELEGRAM_BOT_TOKEN", "placeholder": "bot token (optional)"},
]


@dataclass(frozen=True)
class KeyStatus:
    """One row of the settings table."""

    service: str
    env_var: str
    placeholder: str
    is_set: bool
    masked: str | None  # e.g. "••••abcd" — last 4 chars only


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Skips blank lines and comments."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _mask(value: str) -> str:
    """Show only the last 4 chars, masked. Returns '' for empty."""
    if not value:
        return ""
    if len(value) <= 4:
        return "•" * len(value)
    return f"{'•' * (len(value) - 4)}{value[-4:]}"


def list_keys(env_path: Path | None = None) -> list[KeyStatus]:
    """Return the status of each known key.

    A key is `set` if it exists in the .env file AND has a non-empty value.
    The displayed value is always masked; raw values never leave this module.
    """
    path = env_path or ENV_PATH
    env = _read_env_file(path)
    statuses: list[KeyStatus] = []
    for entry in KNOWN_KEYS:
        raw = env.get(entry["env_var"], "").strip()
        statuses.append(
            KeyStatus(
                service=entry["service"],
                env_var=entry["env_var"],
                placeholder=entry["placeholder"],
                is_set=bool(raw),
                masked=_mask(raw) if raw else None,
            )
        )
    return statuses


def get_raw(env_var: str, env_path: Path | None = None) -> str:
    """Get the raw (unmasked) value of a single key. Used by the generation code path."""
    if env_var not in {k["env_var"] for k in KNOWN_KEYS}:
        raise ValueError(f"unknown key: {env_var}")
    path = env_path or ENV_PATH
    env = _read_env_file(path)
    return env.get(env_var, "").strip()


def save_key(env_var: str, value: str, env_path: Path | None = None) -> None:
    """Write or update a key in .env, preserving comments and ordering.

    If the key already exists, its line is replaced in place.
    If it doesn't, the new line is appended at the end.
    """
    if env_var not in {k["env_var"] for k in KNOWN_KEYS}:
        raise ValueError(f"unknown key: {env_var}")

    path = env_path or ENV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    if path.exists():
        lines = path.read_text().splitlines()
    else:
        lines = []

    prefix = f"{env_var}="
    replaced = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        existing_key = stripped.split("=", 1)[0].strip()
        if existing_key == env_var:
            lines[i] = f"{env_var}={value}"
            replaced = True
            break

    if not replaced:
        # Append; ensure a blank line separator if file already has content
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{env_var}={value}")

    path.write_text("\n".join(lines) + "\n")

    # Also mirror to os.environ so the current process can see it immediately
    os.environ[env_var] = value


def delete_key(env_var: str, env_path: Path | None = None) -> None:
    """Remove a key from .env (does not raise if missing)."""
    if env_var not in {k["env_var"] for k in KNOWN_KEYS}:
        raise ValueError(f"unknown key: {env_var}")
    path = env_path or ENV_PATH
    if not path.exists():
        return
    lines = path.read_text().splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            existing_key = stripped.split("=", 1)[0].strip()
            if existing_key == env_var:
                continue
        out.append(line)
    path.write_text("\n".join(out).rstrip("\n") + "\n")
    os.environ.pop(env_var, None)
