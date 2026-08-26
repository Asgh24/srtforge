"""Translation engine.

Imports the most-used names so callers can do
``from srtforge.translate import LLMClient, chunk, ModelInfo``.
"""

from __future__ import annotations

from srtforge.translate.chunker import Chunk, chunk
from srtforge.translate.client import APIError, CompletionResult, LLMClient
from srtforge.translate.models import ModelInfo, list_models

__all__ = [
    "APIError",
    "Chunk",
    "CompletionResult",
    "LLMClient",
    "ModelInfo",
    "chunk",
    "list_models",
]
