"""Pure data model for one subtitle cue."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubtitleEntry:
    """A single subtitle cue.

    ``text`` is plain text with ``\n`` separators. Styling (``<i>``,
    ``{\\an8}`` etc.) is stripped before translation and re-applied on
    output by the writer, so the LLM only ever sees plain text.
    """

    index: int
    start_ms: int
    end_ms: int
    text: str
    style: str = ""  # raw style tags for restoration, if any

    # Translation bookkeeping (not serialised to the .srt itself)
    translated: str | None = field(default=None, repr=False)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms
