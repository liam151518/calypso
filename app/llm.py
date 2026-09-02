"""app/llm.py. Unified LLM backend abstraction.

Three providers with a single, narrow protocol:

    backend = get_backend("openai" | "anthropic" | "MiniMax")
    text = backend.complete(system=..., user=..., model=...)

The provider is selected via :data:`LLMProvider` (default "openai"), and the
appropriate API key is read from the local ``.env`` file. Heuristic code
paths that don't need an LLM should keep using their existing logic — this
module is intentionally small so it can be imported from anywhere without
side effects.

Each backend raises ``LLMError`` on any provider failure; callers are
expected to fall back to a heuristic / rule-based path.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when any LLM backend fails. The message is safe to log."""


class LLMBackend(Protocol):
    """Minimal interface every provider implements."""

    name: str

    def complete(self, *, system: str, user: str, model: str = "") -> str: ...


@dataclass(frozen=True)
class _Provider:
    name: str
    env_var: str
    docs_url: str
    default_model: str


# The three providers we ship with. Order matters: this is the order shown
# in the Settings dropdown. Keys are lowercased so lookups are case-insensitive.
_PROVIDERS: dict[str, _Provider] = {
    "openai": _Provider(
        name="OpenAI",
        env_var="OPENAI_API_KEY",
        docs_url="https://platform.openai.com/api-keys",
        default_model="gpt-4o-mini",
    ),
    "anthropic": _Provider(
        name="Anthropic",
        env_var="ANTHROPIC_API_KEY",
        docs_url="https://console.anthropic.com/settings/keys",
        default_model="claude-3-5-haiku-latest",
    ),
    "minimax": _Provider(
        name="MiniMax",
        env_var="MINIMAX_API_KEY",
        docs_url="https://platform.minimax.io",
        # MiniMax is OpenAI-compatible; the model id is what the user has
        # configured in their account.
        default_model="MiniMax-Text-01",
    ),
}


def list_providers() -> list[dict[str, Any]]:
    """Return the list of providers for the Settings UI."""
    return [
        {
            "name": p.name,
            "env_var": p.env_var,
            "docs_url": p.docs_url,
            "default_model": p.default_model,
            "is_set": bool(os.environ.get(p.env_var)),
        }
        for p in _PROVIDERS.values()
    ]


def provider_for_name(name: str) -> _Provider | None:
    return _PROVIDERS.get((name or "").lower())


def get_default_provider_name() -> str:
    """Read ``LLM_PROVIDER`` from env (default ``openai``)."""
    return (os.environ.get("LLM_PROVIDER") or "openai").lower()


# ---- factory ------------------------------------------------------------


_BACKEND_CACHE: dict[str, LLMBackend] = {}


def get_backend(name: str | None = None) -> LLMBackend:
    """Return a backend instance for the given provider name.

    Falls back to :func:`get_default_provider_name` when ``name`` is empty.
    Raises :class:`LLMError` if the provider is unknown or its API key is
    not configured.
    """
    if not name:
        name = get_default_provider_name()
    name = name.lower()
    if name in _BACKEND_CACHE:
        return _BACKEND_CACHE[name]
    spec = provider_for_name(name)
    if not spec:
        raise LLMError(f"unknown LLM provider: {name!r}")
    api_key = os.environ.get(spec.env_var)
    if not api_key:
        raise LLMError(
            f"{spec.name} API key not set (expected {spec.env_var} in .env)"
        )
    if name == "openai":
        backend: LLMBackend = _OpenAIBackend(api_key=api_key, spec=spec)
    elif name == "anthropic":
        backend = _AnthropicBackend(api_key=api_key, spec=spec)
    elif name == "minimax":
        backend = _MiniMaxBackend(api_key=api_key, spec=spec)
    else:
        raise LLMError(f"unsupported LLM provider: {name!r}")
    _BACKEND_CACHE[name] = backend
    return backend


# ---- HTTP helper --------------------------------------------------------


def _http_post_json(url: str, *, headers: dict[str, str],
                    body: dict[str, Any], timeout: float = 20.0) -> Any:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise LLMError(f"{url}: {exc!s}") from exc


# ---- OpenAI --------------------------------------------------------------


class _OpenAIBackend:
    name = "openai"

    def __init__(self, *, api_key: str, spec: _Provider) -> None:
        self.api_key = api_key
        self.spec = spec

    def complete(self, *, system: str, user: str, model: str = "") -> str:
        chosen = model or self.spec.default_model
        payload = _http_post_json(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            body={
                "model": chosen,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
            },
        )
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"openai: unexpected payload: {exc!s}") from exc


# ---- Anthropic -----------------------------------------------------------


class _AnthropicBackend:
    name = "anthropic"

    def __init__(self, *, api_key: str, spec: _Provider) -> None:
        self.api_key = api_key
        self.spec = spec

    def complete(self, *, system: str, user: str, model: str = "") -> str:
        chosen = model or self.spec.default_model
        payload = _http_post_json(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            body={
                "model": chosen,
                "max_tokens": 512,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        try:
            block = payload["content"][0]
            return str(block.get("text") or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"anthropic: unexpected payload: {exc!s}") from exc


# ---- MiniMax (OpenAI-compatible) ----------------------------------------


class _MiniMaxBackend:
    """MiniMax exposes an OpenAI-compatible chat endpoint, so we reuse the
    same wire format as :class:`_OpenAIBackend` but point at MiniMax's URL.
    """

    name = "MiniMax"

    def __init__(self, *, api_key: str, spec: _Provider) -> None:
        self.api_key = api_key
        self.spec = spec

    def complete(self, *, system: str, user: str, model: str = "") -> str:
        chosen = model or self.spec.default_model
        payload = _http_post_json(
            "https://api.MiniMax.io/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            body={
                "model": chosen,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
            },
        )
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"MiniMax: unexpected payload: {exc!s}") from exc
