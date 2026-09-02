"""Tests for the unified LLM backend in :mod:`app.llm`."""

from __future__ import annotations

import json
from typing import Any
from unittest import mock

import pytest

from app import llm
from app.llm import LLMError, get_backend, list_providers


@pytest.fixture(autouse=True)
def _clear_backend_cache():
    llm._BACKEND_CACHE.clear()
    yield
    llm._BACKEND_CACHE.clear()


def test_list_providers_returns_three():
    providers = list_providers()
    names = {p["name"] for p in providers}
    assert {"OpenAI", "Anthropic", "MiniMax"} <= names


def test_list_providers_reflects_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-xyz")
    providers = {p["name"]: p for p in list_providers()}
    assert providers["OpenAI"]["is_set"] is True
    assert providers["Anthropic"]["is_set"] is False


def test_get_backend_unknown_provider():
    with pytest.raises(LLMError, match="unknown"):
        get_backend("nope")


def test_get_backend_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        get_backend()


def test_get_backend_default_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    backend = get_backend()
    assert backend.name == "openai"


def test_get_backend_caches(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    a = get_backend("openai")
    b = get_backend("openai")
    assert a is b


def _patch_urlopen(payload: dict[str, Any]):
    """Patch urllib.request.urlopen to return a fake response with .read()."""
    body = json.dumps(payload).encode()

    class FakeResp:
        def __init__(self, _body: bytes) -> None:
            self._body = _body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(req, timeout=20):
        # Echo the URL through payload for test assertions if needed
        return FakeResp(body)

    return mock.patch("urllib.request.urlopen", fake_urlopen)


def test_openai_complete(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    payload = {"choices": [{"message": {"content": "hello"}}]}
    with _patch_urlopen(payload):
        backend = get_backend("openai")
        out = backend.complete(system="sys", user="hi", model="gpt-x")
    assert out == "hello"


def test_anthropic_complete(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    payload = {"content": [{"text": "anthropic says hi"}]}
    with _patch_urlopen(payload):
        backend = get_backend("anthropic")
        out = backend.complete(system="sys", user="hi")
    assert out == "anthropic says hi"


def test_minimax_complete(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "mm-test")
    payload = {"choices": [{"message": {"content": "MiniMax hi"}}]}
    with _patch_urlopen(payload):
        backend = get_backend("minimax")
        out = backend.complete(system="sys", user="hi")
    assert out == "MiniMax hi"


def test_minimax_complete_uppercase(monkeypatch):
    """Provider names should be case-insensitive."""
    monkeypatch.setenv("MINIMAX_API_KEY", "mm-test")
    payload = {"choices": [{"message": {"content": "ok"}}]}
    with _patch_urlopen(payload):
        backend = get_backend("MiniMax")
        assert backend.name == "MiniMax"


def test_captions_falls_back_when_no_key(monkeypatch):
    """Captions module must always return a variant (heuristic)."""
    from app.captions import generate
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("FAL_API_KEY", raising=False)
    variants = generate(
        product={"name": "Test Sneaker"},
        template={"name": "Bold Drop"},
        brand={"voice": "bold", "name": "Acme"},
        platform="instagram",
        model="heuristic",
        count=2,
    )
    assert variants
    assert len(variants) == 2


def test_captions_uses_llm_when_configured(monkeypatch):
    """When an OpenAI key is present and model='llm', we call the backend."""
    from app.captions import generate, _llm_variants

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    payload = {"choices": [{"message": {"content": json.dumps({
        "captions": [{"content": "Test caption", "hashtags": ["#x"]}]
    })}}]}

    class FakeResp:
        def __init__(self, body): self._body = body
        def read(self): return self._body
        def __enter__(self): return self
        def __exit__(self, *_): return False

    def fake_urlopen(req, timeout=20):
        return FakeResp(json.dumps(payload).encode())

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        variants = generate(
            product={"name": "Sneaker"},
            template={"name": "Bold Drop"},
            brand={"voice": "bold", "name": "Acme"},
            platform="instagram",
            model="llm",
            count=1,
        )
    assert len(variants) == 1
    assert "Test caption" in variants[0].content
