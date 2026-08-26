"""Round-trip tests for srt/io.py."""

from __future__ import annotations

import pytest

from srtforge.srt.io import load, save
from srtforge.srt.model import SubtitleEntry


@pytest.fixture()
def sample_srt(tmp_path) -> str:
    p = tmp_path / "sample.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nHello world\n\n"
        "2\n00:00:04,500 --> 00:00:06,200\nSecond cue\nwith two lines\n",
        encoding="utf-8",
    )
    return str(p)


def test_load_parses_cues(sample_srt: str) -> None:
    entries = load(sample_srt)
    assert len(entries) == 2
    assert entries[0].index == 1
    assert entries[0].start_ms == 1000
    assert entries[0].end_ms == 3000
    assert entries[0].text == "Hello world"
    assert entries[1].text == "Second cue\nwith two lines"


def test_load_strips_html_tags(tmp_path) -> None:
    p = tmp_path / "tagged.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n<i>Italic</i> cue\n",
        encoding="utf-8",
    )
    entries = load(str(p))
    assert entries[0].text == "Italic cue"


def test_save_writes_valid_srt(tmp_path, sample_srt: str) -> None:
    entries = load(sample_srt)
    out = tmp_path / "out.srt"
    save(str(out), entries)
    text = out.read_text(encoding="utf-8")
    assert "Hello world" in text
    assert "00:00:01,000 --> 00:00:03,000" in text


def test_save_uses_translated_field(tmp_path, sample_srt: str) -> None:
    entries = load(sample_srt)
    entries[0].translated = "Bonjour le monde"
    out = tmp_path / "out.srt"
    save(str(out), entries)
    text = out.read_text(encoding="utf-8")
    assert "Bonjour le monde" in text
    assert "Hello world" not in text
