import re
import threading
from typing import Any

# Two patterns that cover the token-relevant structure of BPE tokenization:
#   Word runs: contiguous word characters (letters, digits, underscores).
#     Each run averages ~1.3 BPE sub-tokens for English+technical content.
#     The 1.3 factor accounts for subword splits on compound words, identifiers,
#     and low-frequency terms (common words = 1 token, technical = 1-2 tokens).
#   Punctuation runs: contiguous non-word, non-space characters.
#     Each contiguous run is ~1.5 tokens: a short symbol like ":" or "-" is 1 token;
#     a longer run like "---" or "/**" is typically 2-3 tokens but not one per char.
#
# Measured against tiktoken cl100k_base over 61 real SKILL.md files with
# scripts/measure_token_error.py: 23.0% median relative error on a whole file,
# 30.7% at p95, reading high on 61 of 61. It is fully offline.
#
# This comment used to claim ~15% average error and that the approach beat the
# naive char//4 rule of thumb at ~20%. Both were wrong on that corpus, and the
# ordering was backwards: chars//4 measured 6.3% median. The estimator is left
# alone because swapping it would move every token diagnostic, which is not a
# documentation change; the measurement is recorded in the README so the choice
# can be made deliberately.
#
# Install `tiktoken` for counts from cl100k_base directly. Its own residual
# error against Claude's tokenizer is unknown, Anthropic's vocabulary not being
# published, so no figure is claimed for it here.
_WORD_RE = re.compile(r"\w+")
_PUNCT_RE = re.compile(r"[^\w\s]+")

# Lazy-cached tiktoken encoding.  The BPE merge table is allocated once on
# first use and reused for all subsequent calls, avoiding the per-call
# overhead of ``tiktoken.get_encoding()``.  The lock guards the first-init
# fast path so concurrent worker threads (editor plugins planned for
# future use) cannot both observe the untested state and race on
# ``tiktoken.get_encoding``.
_tiktoken_enc: Any | None = None
_tiktoken_available: bool | None = None  # tri-state: None = untested
_tiktoken_lock = threading.Lock()


def _get_tiktoken_enc() -> Any | None:
    """Return a cached tiktoken ``Encoding``, or *None* if unavailable."""
    global _tiktoken_enc, _tiktoken_available  # noqa: PLW0603
    if _tiktoken_available is not None:
        return _tiktoken_enc
    with _tiktoken_lock:
        # Re-check under the lock so the second arrival sees the cached value.
        if _tiktoken_available is None:
            try:
                import tiktoken
                _tiktoken_enc = tiktoken.get_encoding("cl100k_base")
                _tiktoken_available = True
            except ImportError:
                _tiktoken_available = False
        return _tiktoken_enc


def estimate_tokens(text: str) -> int:
    """Estimate the BPE token count of a text string.

    Priority:
    1. tiktoken (cl100k_base) if installed. tiktoken downloads the cl100k_base
       vocabulary from the internet on first use and caches it, so the very
       first run needs network access (or a pre-warmed cache); later runs are
       offline.
    2. Word-run + punctuation-run heuristic: 23% median error against
       cl100k_base and reading high on every file measured, no dependencies,
       always offline. See the module comment above for the measurement.

    Neither gives exact Claude token counts (Anthropic's vocabulary is not
    publicly released), which is why token-based diagnostics are WARNING
    severity. Prefer the tiktoken extra when a count lands near a budget.
    """
    enc = _get_tiktoken_enc()
    if enc is not None:
        return max(1, len(enc.encode(text)))

    word_tokens = int(len(_WORD_RE.findall(text)) * 1.3)
    punct_tokens = int(len(_PUNCT_RE.findall(text)) * 1.5)
    return max(1, word_tokens + punct_tokens)
