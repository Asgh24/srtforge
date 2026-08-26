"""Prompt templates.

The default prompt is deliberately *behavioural* — it tells the model
exactly what shape of JSON to return and warns against common failure
modes (echoing indices, adding commentary, splitting cues). The
``custom_prompt`` field in settings lets power users override.
"""

from __future__ import annotations

import hashlib
from typing import Any

DEFAULT_PROMPT = """\
You are a professional subtitle translator.

Translate each cue from {source_lang} to {target_lang}. Preserve the
subtle tone of the original (formal/informal, slang, idioms, profanity,
emotional register). Do NOT censor or normalise.

Output requirements:
- Return ONLY a JSON object — no prose, no markdown fences, no commentary.
- Keep the same number of cues in the same order.
- Keep translation length similar to the original so it fits the same
  time slot. If a literal translation would overflow, summarise very
  briefly; never invent content.
- Preserve proper nouns, brand names, and technical terms (Rigidbody,
  Collider, prefab, Inspector, GameObject, etc.) when they are used
  in their original technical sense. Transliterate when the audience
  cannot read the original script (e.g. Cyrillic → Latin for an English
  audience if requested).
- Match punctuation conventions of the target language.
- Each cue may contain one or more lines separated by ``\\n`` — keep the
  line breaks where natural (one line per visible subtitle row).

JSON shape:
{{
  "translations": [
    {{"i": 1, "t": "translated line 1"}},
    {{"i": 2, "t": "translated line 2"}}
  ]
}}

Chunk {chunk_index} of {chunk_count}. Translate the following cues:

{cues_json}
"""

CUSTOM_VARIABLES = {
    "source_lang",
    "target_lang",
    "chunk_index",
    "chunk_count",
    "cues_json",
}


def render_prompt(
    template: str,
    *,
    source_lang: str,
    target_lang: str,
    chunk_index: int,
    chunk_count: int,
    cues: list[dict[str, Any]],
) -> str:
    import json

    cues_json = json.dumps(cues, ensure_ascii=False, indent=0)
    return template.format(
        source_lang=source_lang if source_lang != "auto" else "the source language",
        target_lang=target_lang,
        chunk_index=chunk_index,
        chunk_count=chunk_count,
        cues_json=cues_json,
    )


def prompt_hash(template: str) -> str:
    """Stable hash of a prompt template; used to invalidate sidecar state."""
    return "sha256:" + hashlib.sha256(template.encode("utf-8")).hexdigest()[:16]


def build_cue_payload(entries: list[Any]) -> list[dict[str, Any]]:
    """Turn subtitle entries into the JSON we hand to the model.

    ``entries`` is a list of SubtitleEntry; only ``index`` and ``text``
    are sent, in a compact form.
    """
    return [{"i": e.index, "t": e.text} for e in entries]
