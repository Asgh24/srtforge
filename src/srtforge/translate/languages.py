"""Languages we ship in the dropdown.

The list is intentionally short — these are the most common
target languages for English-speaking learners of other languages.
The dropdown is editable: users can type any language they want.
"""

from __future__ import annotations

COMMON_LANGUAGES: list[str] = [
    "English",
    "Persian (Farsi)",
    "Arabic",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Russian",
    "Japanese",
    "Korean",
    "Chinese (Simplified)",
    "Chinese (Traditional)",
    "Hindi",
    "Turkish",
    "Dutch",
    "Polish",
    "Swedish",
    "Norwegian",
    "Danish",
    "Finnish",
    "Greek",
    "Hebrew",
    "Indonesian",
    "Vietnamese",
    "Thai",
    "Czech",
    "Hungarian",
    "Romanian",
    "Ukrainian",
]

AUTO = "auto"  # sentinel for "let the model figure it out"


def all_choices() -> list[str]:
    """Choices for the source-language dropdown (auto + every common lang)."""
    return [AUTO, *COMMON_LANGUAGES]


def is_auto(value: str) -> bool:
    return value.strip().lower() == AUTO
