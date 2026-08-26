"""Subtitle file I/O built on pysubs2.

We only *write* SRT today, but ``load`` accepts anything pysubs2 can
read (srt, ass/ssa, vtt, sub, ...) so a future feature can widen the
output formats with a one-line change.
"""

from __future__ import annotations

import re
from pathlib import Path

import pysubs2

from srtforge.srt.model import SubtitleEntry

# Tag-like substrings we strip before sending text to the LLM:
#   <i>, </i>, <b>, {\\an8}, {\\pos(1,2)}, {\\i1}/{\\i0}, <font color="#fff">
# pysubs2 uses \\N for a newline in SRT text — normalise it back to \\n.
# The brace-tag variant is what pysubs2 emits for ASS/SSA styling.
_TAG_RE = re.compile(
    r"</?[a-zA-Z][^>]*>"      # HTML-style tags: <i>, <b>, <font ...>
    r"|\{[^}]*\}"            # ASS/SSA-style tags: {\i1}, {\an8}, {\pos(1,2)}
)


def _strip_tags(text: str) -> str:
    text = _TAG_RE.sub("", text)
    text = text.replace("\\N", "\n")
    return text


def load(path: Path | str) -> list[SubtitleEntry]:
    """Load a subtitle file into our model, re-indexing sequentially.

    pysubs2 normalises line endings, decodes BOM, and handles both
    ``,`` and ``.`` decimal separators in SRT timestamps.
    """
    subs = pysubs2.load(str(path), encoding="utf-8")
    entries: list[SubtitleEntry] = []
    for i, (start, end, text, _style) in enumerate(_iter_subs(subs), start=1):
        entries.append(
            SubtitleEntry(
                index=i,
                start_ms=int(start),
                end_ms=int(end),
                text=_strip_tags(text),
            )
        )
    return entries


def _iter_subs(subs: pysubs2.SSAFile):
    """Yield (start, end, text, style) per cue in a stable order."""
    for event in subs:
        if event.is_comment:
            continue
        yield event.start, event.end, event.text, getattr(event, "style", "")


def save(path: Path | str, entries: list[SubtitleEntry]) -> None:
    """Write entries to an SRT file.

    Only translated text is emitted; index numbers are regenerated
    sequentially, and the file is written with CRLF + UTF-8 so it opens
    cleanly in every player (incl. older Windows players).
    """
    subs = pysubs2.SSAFile()
    for entry in entries:
        text = entry.translated or entry.text
        subs.append(
            pysubs2.SSAEvent(
                start=entry.start_ms,
                end=entry.end_ms,
                text=text,
            )
        )
    subs.save(str(path), format_="srt", encoding="utf-8")


def renumber(entries: list[SubtitleEntry]) -> list[SubtitleEntry]:
    """Renumber indices 1..N in place (defensive; load already does this)."""
    for i, entry in enumerate(entries, start=1):
        entry.index = i
    return entries
