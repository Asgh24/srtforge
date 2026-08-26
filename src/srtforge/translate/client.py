"""LLM HTTP client.

Synchronous ``requests`` calls, so it can run inside a ``QThreadPool``
worker without bridging event loops. Retry/backoff is inline — we don't
need ``tenacity``'s state machine for 5 attempts.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import requests

from srtforge.config.profiles import APIProfile

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5
MAX_BACKOFF = 30.0
INITIAL_BACKOFF = 1.0


class APIError(Exception):
    """Non-retryable HTTP error from the upstream provider."""

    def __init__(self, status: int | str, body: str = "") -> None:
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


class APIAuthError(APIError):
    """Auth failure (401) or insufficient credits (402). Never retried."""


@dataclass
class CompletionResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict | None = None


class LLMClient:
    """A single OpenAI/Anthropic-compatible chat-completions client.

    Stateless after construction. One client per (profile, model) pair.
    """

    def __init__(
        self,
        profile: APIProfile,
        model_id: str,
        timeout: float = 120.0,
        session: requests.Session | None = None,
    ) -> None:
        self.profile = profile
        self.model_id = model_id
        self.timeout = timeout
        self._session = session or requests.Session()
        self.base = profile.base_url.rstrip("/")

    # ---- public API ----------------------------------------------------

    def complete(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        json_mode: bool = True,
    ) -> CompletionResult:
        """Send ``messages`` and return the first choice's text + token usage."""
        url = self.base + "/chat/completions"
        payload: dict = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = self._post_with_retry(url, payload)
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise APIError("malformed", str(data)[:300]) from exc
        usage = data.get("usage") or {}
        return CompletionResult(
            text=text or "",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            raw=data,
        )

    # ---- internals -----------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.profile.api_key:
            h["Authorization"] = f"Bearer {self.profile.api_key}"
        if self.profile.referer:
            h["HTTP-Referer"] = self.profile.referer
        if self.profile.app_title:
            h["X-Title"] = self.profile.app_title
        return h

    def _post_with_retry(self, url: str, payload: dict) -> dict:
        delay = INITIAL_BACKOFF
        last_exc: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                resp = self._session.post(
                    url, json=payload, headers=self._headers(), timeout=self.timeout
                )
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("Network error (attempt %d): %s", attempt, exc)
                self._sleep(delay)
                delay = min(delay * 2, MAX_BACKOFF)
                continue

            if resp.status_code in RETRYABLE_STATUS:
                last_exc = APIError(resp.status_code, resp.text)
                retry_after = _parse_retry_after(resp)
                self._sleep(retry_after or delay)
                delay = min(delay * 2, MAX_BACKOFF)
                continue

            if resp.status_code in (401, 402):
                raise APIAuthError(resp.status_code, resp.text)

            if not resp.ok:
                raise APIError(resp.status_code, resp.text)

            try:
                return resp.json()
            except json.JSONDecodeError as exc:
                raise APIError("json-decode", resp.text[:300]) from exc

        raise APIError("retry-exhausted", str(last_exc) if last_exc else "")

    def _sleep(self, seconds: float) -> None:
        # Module-level so tests can monkeypatch.
        time.sleep(max(0.0, seconds))


def _parse_retry_after(resp: requests.Response) -> float | None:
    """Parse ``Retry-After`` header (seconds, or HTTP-date)."""
    val = resp.headers.get("Retry-After")
    if not val:
        # OpenRouter uses an absolute epoch on 429.
        reset = resp.headers.get("X-RateLimit-Reset")
        if reset and reset.isdigit():
            return max(0.0, float(reset) - time.time())
        return None
    try:
        return max(0.0, float(val))
    except ValueError:
        # HTTP-date format — too obscure to bother supporting; ignore.
        return None
