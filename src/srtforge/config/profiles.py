"""APIProfile — a single OpenAI/Anthropic-compatible endpoint + key."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class APIProfile:
    """A named LLM endpoint configuration.

    ``base_url`` should be the *root* of the OpenAI-compatible API,
    e.g. ``https://openrouter.ai/api/v1``. ``client.py`` appends
    ``/chat/completions`` and ``/models`` as needed.
    """

    name: str
    base_url: str
    api_key: str = ""
    referer: str = ""
    app_title: str = "SRTForge"
    anthropic_native: bool = False
    id: str = field(default_factory=_new_id)
    models_cache: list[dict[str, Any]] = field(default_factory=list)
    models_cached_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "APIProfile":
        # Be tolerant of unknown keys (forward compat).
        known = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in data.items() if k in known}
        if "id" not in clean or not clean["id"]:
            clean["id"] = _new_id()
        return cls(**clean)

    def display_summary(self) -> str:
        key = self.api_key
        if key:
            key = key[:4] + "…" + key[-2:] if len(key) > 8 else "…"
        else:
            key = "(no key)"
        return f"{self.name}  ·  {self.base_url}  ·  {key}"
