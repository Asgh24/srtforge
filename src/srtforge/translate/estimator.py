"""Token estimation.

We support two backends:

1. ``tiktoken`` — accurate for OpenAI-family models. Optional dep.
2. Heuristic ``len / 3.5`` — covers CJK (~1.5 char/token) and Latin
   (~4 char/token) reasonably well.

The backend is picked at call time so missing ``tiktoken`` is silent.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_TIKTOKEN_CACHE: dict[str, object] = {}
_TIKTOKEN_AVAILABLE: bool | None = None

# Heuristic calibration: Latin is ~4 chars/token, CJK is ~1.5 chars/token.
# 3.5 is a reasonable middle ground that's safe to use without access to
# the model's actual tokenizer. Worst case is underestimating CJK by 2x,
# which the safety margin in chunker.py absorbs.
DEFAULT_CHARS_PER_TOKEN = 3.5


def _tiktoken_available() -> bool:
    global _TIKTOKEN_AVAILABLE
    if _TIKTOKEN_AVAILABLE is None:
        try:
            import tiktoken  # noqa: F401

            _TIKTOKEN_AVAILABLE = True
        except ImportError:
            _TIKTOKEN_AVAILABLE = False
            log.debug("tiktoken not installed; using heuristic estimator")
    return _TIKTOKEN_AVAILABLE


def _encoding_for_model(model_id: str | None) -> object | None:
    if not model_id or not _tiktoken_available():
        return None
    # Map common prefixes to known tokenizers.
    mid = model_id.lower()
    if "gpt-4" in mid or "gpt-3.5" in mid or "o1" in mid or "o3" in mid:
        key = "cl100k_base"  # gpt-4 / gpt-3.5-turbo
    elif "claude" in mid or "anthropic" in mid:
        # Anthropic doesn't ship a public tokenizer; fall through to heuristic.
        return None
    elif "gemini" in mid:
        return None
    else:
        return None

    if key in _TIKTOKEN_CACHE:
        return _TIKTOKEN_CACHE[key]
    try:
        import tiktoken

        enc = tiktoken.get_encoding(key)
        _TIKTOKEN_CACHE[key] = enc
        return enc
    except Exception as exc:  # noqa: BLE001
        log.debug("tiktoken load failed for %s: %s", key, exc)
        return None


# Rough CJK detection — a string with CJK chars tokens more densely.
_CJK_RE = re.compile(r"[　-鿿豈-﫿]")


def estimate_tokens(text: str, model_id: str | None = None) -> int:
    """Best-effort token count for ``text``.

    Tries ``tiktoken`` first when the model is recognisable, otherwise
    uses a heuristic that weights CJK content higher.
    """
    if not text:
        return 0

    enc = _encoding_for_model(model_id)
    if enc is not None:
        try:
            return len(enc.encode(text))  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass

    # Heuristic path.
    cjk_count = len(_CJK_RE.findall(text))
    latin_count = len(text) - cjk_count
    cjk_tokens = cjk_count / 1.5
    latin_tokens = latin_count / 4.0
    return max(1, int(cjk_tokens + latin_tokens))


def estimate_messages_tokens(
    messages: list[dict[str, str]], model_id: str | None = None
) -> int:
    """Sum of per-message content tokens plus a 4-token-per-message overhead."""
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""), model_id)
        total += 4  # role / name framing
    total += 2  # reply priming
    return total
