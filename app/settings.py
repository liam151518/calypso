"""app/settings.py. Read/write the local .env file.

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


@dataclass(frozen=True)
class KeyStatus:
    """One row of the settings table."""

    service: str
    env_var: str
    placeholder: str
    group: str
    required: bool
    docs_url: str | None
    description: str
    is_set: bool
    masked: str | None  # e.g. "••••abcd" (last 4 chars only)


# The keys the UI knows how to surface. Adding a new service means adding it here.
#
# Each entry:
#   env_var      — the literal .env key name (case-sensitive, must match what
#                  the rest of the app reads).
#   service      — human-readable name shown in the UI.
#   placeholder  — placeholder text inside the input.
#   group        — UI grouping ("Generation", "Publishing", "Storage", etc.).
#   required     — true if missing this key will break the core generation path.
#   docs_url     — where to obtain the credential (setup docs / signup page).
#   description  — short explanation shown below the field.
KNOWN_KEYS: list[dict[str, object]] = [
    # ---------- Generation ----------
    {
        "env_var": "FAL_API_KEY",
        "service": "fal.ai",
        "placeholder": "fal-xxxxxxxx",
        "group": "Generation",
        "required": True,
        "docs_url": "https://fal.ai/dashboard/keys",
        "description": "Primary cloud provider. MiniMax H3 Max speed tier + Kling 2.6 Pro hero tier.",
    },
    {
        "env_var": "MINIMAX_API_KEY",
        "service": "MiniMax (H3 cloud)",
        "placeholder": "sk-xxxxxxxx",
        "group": "Generation",
        "required": False,
        "docs_url": "https://platform.minimax.io",
        "description": "Used for H3 cloud primary tier if you prefer the MiniMax platform directly.",
    },
    {
        "env_var": "OPENAI_API_KEY",
        "service": "OpenAI (LLM)",
        "placeholder": "sk-xxxxxxxx",
        "group": "Generation",
        "required": False,
        "docs_url": "https://platform.openai.com/api-keys",
        "description": "LLM backend used for caption generation + prompt enhancement when LLM_PROVIDER=openai.",
    },
    {
        "env_var": "ANTHROPIC_API_KEY",
        "service": "Anthropic (LLM)",
        "placeholder": "sk-ant-xxxxxxxx",
        "group": "Generation",
        "required": False,
        "docs_url": "https://console.anthropic.com/settings/keys",
        "description": "LLM backend used when LLM_PROVIDER=anthropic.",
    },
    {
        "env_var": "LLM_PROVIDER",
        "service": "LLM provider",
        "placeholder": "openai | anthropic | MiniMax",
        "group": "Generation",
        "required": False,
        "docs_url": "https://github.com/MiniMaxio/calypso#skills",
        "description": "Which LLM backend captions/prompt-enhancement use. Default: openai.",
    },
    {
        "env_var": "ELEVENLABS_API_KEY",
        "service": "ElevenLabs",
        "placeholder": "el-xxxxxxxx",
        "group": "Generation",
        "required": False,
        "docs_url": "https://elevenlabs.io",
        "description": "Optional. Only needed for UGC-style voiceover tracks. Most audio comes from H3 native.",
    },
    {
        "env_var": "OMNI_API_KEY",
        "service": "Omni motion backend",
        "placeholder": "omni-xxxxxxxx",
        "group": "Generation",
        "required": False,
        "docs_url": "docs/omni_integration.md",
        "description": "Optional. Opt-in external motion backend. Falls back to the built-in OpenCV motion if unset.",
    },
    {
        "env_var": "CALYPSO_EXTENSION_SIGNING_KEY",
        "service": "Marketplace signing key",
        "placeholder": "hex or base64 secret",
        "group": "Generation",
        "required": False,
        "docs_url": "docs/marketplace",
        "description": "HMAC key used to sign marketplace extensions you publish. Auto-generated if missing.",
    },

    # ---------- Approvals ----------
    {
        "env_var": "TELEGRAM_BOT_TOKEN",
        "service": "Telegram bot token",
        "placeholder": "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ",
        "group": "Approvals",
        "required": False,
        "docs_url": "https://t.me/BotFather",
        "description": "Optional. Sends every generated post to a chat for Approve/Reject/Skip buttons.",
    },
    {
        "env_var": "TELEGRAM_CHAT_ID",
        "service": "Telegram chat id",
        "placeholder": "-1001234567890",
        "group": "Approvals",
        "required": False,
        "docs_url": "https://t.me/BotFather",
        "description": "Chat or channel id where the bot posts. Use getUpdates after sending /start in the chat.",
    },

    # ---------- Publishing ----------
    {
        "env_var": "X_API_KEY",
        "service": "X (Twitter) API key",
        "placeholder": "consumer key",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developer.twitter.com",
        "description": "X API v2 consumer key. 1-3 days platform approval.",
    },
    {
        "env_var": "X_API_SECRET",
        "service": "X (Twitter) API secret",
        "placeholder": "consumer secret",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developer.twitter.com",
        "description": "X API v2 consumer secret.",
    },
    {
        "env_var": "X_BEARER_TOKEN",
        "service": "X (Twitter) bearer token",
        "placeholder": "AAAAA...",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developer.twitter.com",
        "description": "X API v2 bearer token. Treat as production-grade — it can post to your account.",
    },
    {
        "env_var": "X_ACCESS_TOKEN",
        "service": "X (Twitter) access token",
        "placeholder": "access token",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developer.twitter.com",
        "description": "X API v2 access token for posting on behalf of the connected account.",
    },
    {
        "env_var": "X_ACCESS_SECRET",
        "service": "X (Twitter) access secret",
        "placeholder": "access secret",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developer.twitter.com",
        "description": "X API v2 access token secret.",
    },
    {
        "env_var": "META_APP_ID",
        "service": "Meta app id",
        "placeholder": "1234567890",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developers.facebook.com/apps",
        "description": "Meta Graph API app id. Used for Instagram publishing. 1-7 days approval.",
    },
    {
        "env_var": "META_APP_SECRET",
        "service": "Meta app secret",
        "placeholder": "abc123...",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developers.facebook.com/apps",
        "description": "Meta Graph API app secret.",
    },
    {
        "env_var": "META_ACCESS_TOKEN",
        "service": "Meta long-lived access token",
        "placeholder": "EAAxxxxxxx",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developers.facebook.com/apps",
        "description": "Long-lived user access token with instagram_content_publish scope.",
    },
    {
        "env_var": "META_IG_BUSINESS_ID",
        "service": "Instagram Business account id",
        "placeholder": "178412345678901",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developers.facebook.com/apps",
        "description": "Instagram Business account id (must be Business or Creator account).",
    },
    {
        "env_var": "TIKTOK_CLIENT_KEY",
        "service": "TikTok client key",
        "placeholder": "client_key",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developers.tiktok.com",
        "description": "TikTok Content Posting API client key. 1-3 days approval, sometimes waitlist.",
    },
    {
        "env_var": "TIKTOK_CLIENT_SECRET",
        "service": "TikTok client secret",
        "placeholder": "client_secret",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developers.tiktok.com",
        "description": "TikTok Content Posting API client secret.",
    },
    {
        "env_var": "TIKTOK_ACCESS_TOKEN",
        "service": "TikTok access token",
        "placeholder": "tt-xxxxx",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developers.tiktok.com",
        "description": "TikTok access token for posting on behalf of the connected account.",
    },
    {
        "env_var": "TIKTOK_OPEN_ID",
        "service": "TikTok open id",
        "placeholder": "open_id_xxx",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://developers.tiktok.com",
        "description": "TikTok open_id returned with the access token.",
    },
    {
        "env_var": "INSTAGRAM_USERNAME",
        "service": "Instagram username",
        "placeholder": "@yourhandle",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://www.instagram.com",
        "description": "Instagram username for the instagrapi publisher. Required for direct Instagram uploads.",
    },
    {
        "env_var": "INSTAGRAM_PASSWORD",
        "service": "Instagram password",
        "placeholder": "your-password",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://www.instagram.com",
        "description": "Instagram password. Used once to log in; the session is pickled to disk afterwards.",
    },
    {
        "env_var": "INSTAGRAM_SESSION_FILE",
        "service": "Instagram session file",
        "placeholder": "~/.calypso/instagram_session.pickle",
        "group": "Publishing",
        "required": False,
        "docs_url": "https://instagrapi.com",
        "description": "Path to the pickled instagrapi session. Avoids repeated logins / 2FA challenges.",
    },

    # ---------- Storage ----------
    {
        "env_var": "CLOUDFLARE_ACCOUNT_ID",
        "service": "Cloudflare account id",
        "placeholder": "abc123...",
        "group": "Storage",
        "required": False,
        "docs_url": "https://dash.cloudflare.com",
        "description": "Used for R2 backups of your reference library. Free tier covers 10 GB + 10M ops/mo.",
    },
    {
        "env_var": "CLOUDFLARE_R2_ACCESS_KEY",
        "service": "Cloudflare R2 access key",
        "placeholder": "access_key",
        "group": "Storage",
        "required": False,
        "docs_url": "https://dash.cloudflare.com",
        "description": "R2 access key (treat like an AWS key — it can read/write to your bucket).",
    },
    {
        "env_var": "CLOUDFLARE_R2_SECRET_KEY",
        "service": "Cloudflare R2 secret key",
        "placeholder": "secret_key",
        "group": "Storage",
        "required": False,
        "docs_url": "https://dash.cloudflare.com",
        "description": "R2 secret key.",
    },
    {
        "env_var": "CLOUDFLARE_R2_ENDPOINT",
        "service": "Cloudflare R2 endpoint",
        "placeholder": "https://<accountid>.r2.cloudflarestorage.com",
        "group": "Storage",
        "required": False,
        "docs_url": "https://dash.cloudflare.com",
        "description": "R2 S3-compatible endpoint URL.",
    },
]


def known_keys_grouped() -> list[tuple[str, list[dict[str, object]]]]:
    """Return the known keys list grouped by their `group` field, in stable order."""
    groups: dict[str, list[dict[str, object]]] = {}
    order: list[str] = []
    for entry in KNOWN_KEYS:
        g = str(entry["group"])
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(entry)
    return [(g, groups[g]) for g in order]


# Backwards-compatible set used by get_raw / save_key / delete_key when they
# validate the env_var name.
_KNOWN_ENV_VARS = {entry["env_var"] for entry in KNOWN_KEYS}


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
        raw = env.get(str(entry["env_var"]), "").strip()
        statuses.append(
            KeyStatus(
                service=str(entry["service"]),
                env_var=str(entry["env_var"]),
                placeholder=str(entry["placeholder"]),
                group=str(entry["group"]),
                required=bool(entry["required"]),
                docs_url=str(entry["docs_url"]) if entry.get("docs_url") else None,
                description=str(entry["description"]),
                is_set=bool(raw),
                masked=_mask(raw) if raw else None,
            )
        )
    return statuses


def _is_valid_env_var_name(name: str) -> bool:
    """Env-var names are ASCII letters/digits/underscores and don't start with a digit."""
    if not name or not isinstance(name, str):
        return False
    if name[0].isdigit():
        return False
    return all(c.isalnum() or c == "_" for c in name)


def list_custom_keys(env_path: Path | None = None) -> list[KeyStatus]:
    """Return any .env keys that aren't in KNOWN_KEYS but have non-empty values.

    These are typically pasted by hand by advanced operators, or left over from
    a prior version of the schema. We surface them in the UI so nothing is
    silently swallowed.
    """
    path = env_path or ENV_PATH
    env = _read_env_file(path)
    known = {str(entry["env_var"]) for entry in KNOWN_KEYS}
    custom: list[KeyStatus] = []
    for key, value in env.items():
        if key in known or not _is_valid_env_var_name(key):
            continue
        raw = value.strip()
        if not raw:
            continue
        custom.append(
            KeyStatus(
                service="Custom key",
                env_var=key,
                placeholder="",
                group="Custom",
                required=False,
                docs_url=None,
                description="Not in the preset list — edit or delete from this panel.",
                is_set=True,
                masked=_mask(raw),
            )
        )
    return sorted(custom, key=lambda k: k.env_var)


def get_raw(env_var: str, env_path: Path | None = None) -> str:
    """Get the raw (unmasked) value of a single key. Used by the generation code path.

    Accepts both KNOWN_KEYS entries and arbitrary env-var names that are valid
    identifiers — callers can read any key that's in .env.
    """
    if not _is_valid_env_var_name(env_var):
        raise ValueError(f"invalid key name: {env_var!r}")
    path = env_path or ENV_PATH
    env = _read_env_file(path)
    return env.get(env_var, "").strip()


def save_key(env_var: str, value: str, env_path: Path | None = None) -> None:
    """Write or update a key in .env, preserving comments and ordering.

    If the key already exists, its line is replaced in place.
    If it doesn't, the new line is appended at the end.

    Accepts both KNOWN_KEYS entries and arbitrary valid env-var names, so
    operators can paste custom keys without leaving the UI.
    """
    if not _is_valid_env_var_name(env_var):
        raise ValueError(f"invalid key name: {env_var!r}")
    if not value:
        raise ValueError("Value cannot be empty.")

    path = env_path or ENV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    if path.exists():
        lines = path.read_text().splitlines()
    else:
        lines = []

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
    """Remove a key from .env (does not raise if missing).

    Works for both KNOWN_KEYS entries and custom keys.
    """
    if not _is_valid_env_var_name(env_var):
        raise ValueError(f"invalid key name: {env_var!r}")
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
