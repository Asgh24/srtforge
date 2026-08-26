"""Token estimator tests."""

from __future__ import annotations

from srtforge.translate.estimator import estimate_tokens


def test_empty_string() -> None:
    assert estimate_tokens("") == 0


def test_known_short_text_has_positive_count() -> None:
    assert estimate_tokens("Hello world") >= 1


def test_longer_text_has_more_tokens() -> None:
    short = estimate_tokens("hi")
    long = estimate_tokens("hello " * 50)
    assert long > short


def test_cjk_density() -> None:
    """CJK text should tokenise more densely than Latin."""
    latin = "a" * 100
    cjk = "中" * 100
    assert estimate_tokens(cjk) > estimate_tokens(latin) * 2
