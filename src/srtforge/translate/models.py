"""OpenRouter-style model metadata.

We only need three things per model:
  - id (used as the API ``model`` field)
  - context_length (max input+output tokens)
  - max_output_tokens (soft cap, from ``top_provider.max_completion_tokens``)

The OpenRouter ``/models`` endpoint returns a JSON array of objects with
a lot more fields we deliberately ignore.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    id: str
    name: str
    context_length: int
    max_output_tokens: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover — display only
        ctx = f"{self.context_length // 1024}k" if self.context_length else "?"
        return f"{self.name} ({self.id}, ctx={ctx})"


def _extract_context_length(raw: dict[str, Any]) -> int:
    """OpenRouter top-level ``context_length`` is the most reliable signal."""
    ctx = raw.get("context_length")
    if isinstance(ctx, int) and ctx > 0:
        return ctx
    top = raw.get("top_provider") or {}
    if isinstance(top, dict):
        top_ctx = top.get("context_length")
        if isinstance(top_ctx, int) and top_ctx > 0:
            return top_ctx
    return 8192  # sane default


def _extract_max_output(raw: dict[str, Any]) -> int | None:
    top = raw.get("top_provider") or {}
    if isinstance(top, dict):
        v = top.get("max_completion_tokens")
        if isinstance(v, int) and v > 0:
            return v
    return None


def parse_model(raw: dict[str, Any]) -> ModelInfo:
    return ModelInfo(
        id=str(raw.get("id", "")),
        name=str(raw.get("name") or raw.get("id") or "?"),
        context_length=_extract_context_length(raw),
        max_output_tokens=_extract_max_output(raw),
        raw=raw,
    )


def list_models(
    base_url: str, api_key: str, *, timeout: float = 30.0
) -> list[ModelInfo]:
    """GET ``{base_url}/models`` and return parsed models.

    OpenRouter returns ``{"data": [...]}``; some providers return a bare
    list. We tolerate both.
    """
    url = base_url.rstrip("/") + "/models"
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        log.error("/models request failed: %s", exc)
        raise
    if r.status_code != 200:
        raise RuntimeError(f"/models returned HTTP {r.status_code}: {r.text[:200]}")

    payload = r.json()
    if isinstance(payload, dict) and "data" in payload:
        items = payload["data"]
    elif isinstance(payload, list):
        items = payload
    else:
        items = []

    return [parse_model(m) for m in items if isinstance(m, dict)]
