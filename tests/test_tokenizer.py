"""Tests for Fix 1: Tokenizer lazy caching."""

from skillcheck.tokenizer import _get_tiktoken_enc, estimate_tokens


def test_tokenizer_returns_positive():
    """Basic smoke test — estimate_tokens always returns >= 1."""
    assert estimate_tokens("Hello world") >= 1


def test_tokenizer_consistent_across_calls():
    """Two identical calls return the same result (caching consistency)."""
    text = "Validates SKILL.md files for cross-agent compatibility."
    a = estimate_tokens(text)
    b = estimate_tokens(text)
    assert a == b


def test_tiktoken_enc_cached():
    """The encoding object is the same instance across calls (not re-allocated)."""
    enc1 = _get_tiktoken_enc()
    enc2 = _get_tiktoken_enc()
    # Both are either None (tiktoken not installed) or the SAME object.
    if enc1 is not None:
        assert enc1 is enc2
    else:
        assert enc2 is None


def test_empty_string_returns_one():
    """Empty string returns at least 1 (the floor)."""
    assert estimate_tokens("") >= 1
