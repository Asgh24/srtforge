"""Greedy subtitle-by-subtitle chunker.

The unit of a chunk is a *whole subtitle cue* — they're authored as
natural sentence boundaries, so we never split mid-sentence. We just
accumulate cues until adding the next one would exceed the model's
input budget.

Budget = floor(model.context_length × safety_margin) − output_tokens
        − prompt_overhead
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from srtforge.srt.model import SubtitleEntry
from srtforge.translate.estimator import estimate_messages_tokens, estimate_tokens
from srtforge.translate.models import ModelInfo
from srtforge.translate.prompt import DEFAULT_PROMPT, render_prompt

# A rough estimate of the variable scaffolding in the prompt template
# (header, JSON examples, footer text) excluding the cues list itself.
PROMPT_FRAME_TOKENS = 220

# Per-cue framing overhead in the JSON list ("{i: N, t: "..."}," etc.)
PER_CUE_FRAME_TOKENS = 8


@dataclass
class Chunk:
    """A list of cues that will be sent in a single API call."""

    index: int
    entries: list[SubtitleEntry] = field(default_factory=list)
    # Estimated total prompt tokens (system + user) — useful for logging.
    estimated_prompt_tokens: int = 0

    @property
    def indices(self) -> str:
        if not self.entries:
            return "-"
        first = self.entries[0].index
        last = self.entries[-1].index
        return f"{first}-{last}" if first != last else str(first)

    @property
    def size(self) -> int:
        return len(self.entries)


def _compute_input_budget(
    model: ModelInfo,
    *,
    max_output_tokens: int,
    safety_margin: float,
    prompt_template: str,
) -> int:
    """Tokens available for the cue list inside one chunk."""
    prompt_static = estimate_tokens(prompt_template)
    # The chunk_index / chunk_count / cues_json placeholders are filled at
    # render time; we approximate the worst-case scaffolding here.
    output_cap = min(int(max_output_tokens), 1024)
    total = int(model.context_length * safety_margin)
    return max(128, total - prompt_static - output_cap - PROMPT_FRAME_TOKENS)


def _entry_tokens(entry: SubtitleEntry, model_id: str | None) -> int:
    return estimate_tokens(entry.text, model_id) + PER_CUE_FRAME_TOKENS


def chunk(
    entries: Iterable[SubtitleEntry],
    *,
    model: ModelInfo,
    max_output_tokens: int = 1024,
    safety_margin: float = 0.85,
    prompt_template: str = DEFAULT_PROMPT,
    source_lang: str = "auto",
    target_lang: str = "English",
) -> list[Chunk]:
    """Greedy subtitle-bounded chunker.

    The chunker preserves cue boundaries: a cue is either entirely in
    a chunk, or entirely on its own (with a warning) if it alone exceeds
    the budget.
    """
    budget = _compute_input_budget(
        model,
        max_output_tokens=max_output_tokens,
        safety_margin=safety_margin,
        prompt_template=prompt_template,
    )

    # Render a "fake" prompt to measure the per-chunk scaffolding we
    # can't account for statically (cues_json length, "Chunk N of M",
    # etc.). Worst case approximation.
    entry_list = list(entries)
    if not entry_list:
        return []

    # First pass: figure out total chunk count by simulating.
    sim_chunks: list[list[SubtitleEntry]] = []
    current: list[SubtitleEntry] = []
    current_tokens = 0
    for entry in entry_list:
        t = _entry_tokens(entry, model.id)
        if t > budget:
            # Single cue exceeds the entire chunk budget — emit alone.
            if current:
                sim_chunks.append(current)
                current = []
                current_tokens = 0
            sim_chunks.append([entry])
            continue
        if current and current_tokens + t > budget:
            sim_chunks.append(current)
            current = [entry]
            current_tokens = t
        else:
            current.append(entry)
            current_tokens += t
    if current:
        sim_chunks.append(current)
    total = len(sim_chunks)

    # Second pass: real Chunk objects, with rendered prompt for logging.
    chunks: list[Chunk] = []
    for idx, group in enumerate(sim_chunks, start=1):
        prompt_text = render_prompt(
            prompt_template,
            source_lang=source_lang,
            target_lang=target_lang,
            chunk_index=idx,
            chunk_count=total,
            cues=[{"i": e.index, "t": e.text} for e in group],
        )
        prompt_tokens = estimate_messages_tokens(
            [{"role": "user", "content": prompt_text}], model.id
        )
        chunks.append(
            Chunk(
                index=idx,
                entries=group,
                estimated_prompt_tokens=prompt_tokens,
            )
        )
    return chunks


def estimate_chunk_count(
    total_chars: int,
    *,
    model: ModelInfo,
    max_output_tokens: int = 1024,
    safety_margin: float = 0.85,
    prompt_template: str = DEFAULT_PROMPT,
) -> int:
    """Approximate chunk count without parsing the file.

    Used by the GUI's "Settings" preview. Average subtitle is ~50 chars
    so this is a reasonable ballpark.
    """
    avg_chars_per_cue = 50
    cues = max(1, total_chars // avg_chars_per_cue)
    avg_tokens = total_chars / 3.5
    budget = _compute_input_budget(
        model,
        max_output_tokens=max_output_tokens,
        safety_margin=safety_margin,
        prompt_template=prompt_template,
    )
    if budget <= 0:
        return cues
    return max(1, int((avg_tokens + cues * PER_CUE_FRAME_TOKENS) // budget) + 1)
