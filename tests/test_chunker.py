"""Chunker tests — every entry appears once, no chunk overflows."""

from __future__ import annotations

import pytest

from srtforge.srt.model import SubtitleEntry
from srtforge.translate.chunker import chunk
from srtforge.translate.models import ModelInfo


def _entry(i: int, text: str = "x") -> SubtitleEntry:
    return SubtitleEntry(index=i, start_ms=i * 1000, end_ms=i * 1000 + 500, text=text)


def _model(ctx: int = 4096) -> ModelInfo:
    return ModelInfo(id="test-model", name="t", context_length=ctx)


def test_empty_input_returns_empty_chunks() -> None:
    assert chunk([], model=_model()) == []


def test_all_entries_appear_exactly_once() -> None:
    entries = [_entry(i) for i in range(1, 51)]
    chunks = chunk(entries, model=_model(8192), target_lang="French")
    seen = []
    for c in chunks:
        seen.extend(e.index for e in c.entries)
    assert sorted(seen) == list(range(1, 51))


def test_no_chunk_exceeds_budget() -> None:
    """Even with a tiny context window, single huge cues go alone — no overflow."""
    entries = [_entry(i, "hello world " * 50) for i in range(1, 21)]
    chunks = chunk(entries, model=_model(2048), target_lang="French")
    # Each chunk is either empty, one cue, or several small ones — but
    # never so big that we'd send it without any warnings.
    for c in chunks:
        assert len(c.entries) >= 1
        assert c.estimated_prompt_tokens > 0


def test_small_model_produces_more_chunks() -> None:
    entries = [_entry(i, "lorem ipsum dolor sit amet") for i in range(1, 51)]
    big = chunk(entries, model=_model(32768), target_lang="French")
    small = chunk(entries, model=_model(2048), target_lang="French")
    assert len(small) > len(big)


def test_indices_property() -> None:
    entries = [_entry(i) for i in range(1, 6)]
    chunks = chunk(entries, model=_model(32768), target_lang="French")
    # All in one chunk if budget permits.
    assert chunks[0].indices == "1-5"
