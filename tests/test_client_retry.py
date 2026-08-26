"""LLMClient retry/backoff tests using ``responses``."""

from __future__ import annotations

import json

import pytest
import responses

from srtforge.config.profiles import APIProfile
from srtforge.translate.client import APIAuthError, APIError, LLMClient


def _client() -> LLMClient:
    p = APIProfile(
        name="t", base_url="https://example.com/v1", api_key="sk-test"
    )
    return LLMClient(p, "test-model", timeout=5.0)


@responses.activate
def test_success_returns_text() -> None:
    responses.post(
        "https://example.com/v1/chat/completions",
        json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4},
        },
        status=200,
    )
    result = _client().complete([{"role": "user", "content": "hi"}])
    assert result.text == "ok"
    assert result.prompt_tokens == 10


@responses.activate
def test_429_retries_with_backoff(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr("srtforge.translate.client.time.sleep", lambda s: sleeps.append(s))
    responses.post(
        "https://example.com/v1/chat/completions",
        status=429,
        headers={"Retry-After": "1"},
    )
    responses.post(
        "https://example.com/v1/chat/completions",
        json={"choices": [{"message": {"content": "ok"}}]},
        status=200,
    )
    result = _client().complete([{"role": "user", "content": "hi"}])
    assert result.text == "ok"
    assert len(sleeps) >= 1


@responses.activate
def test_401_raises_api_auth_error() -> None:
    responses.post(
        "https://example.com/v1/chat/completions",
        json={"error": "invalid key"},
        status=401,
    )
    with pytest.raises(APIAuthError):
        _client().complete([{"role": "user", "content": "hi"}])


@responses.activate
def test_500_eventually_raises() -> None:
    for _ in range(6):  # 5 retries + buffer
        responses.post(
            "https://example.com/v1/chat/completions",
            status=500,
        )
    with pytest.raises(APIError):
        _client().complete([{"role": "user", "content": "hi"}])
