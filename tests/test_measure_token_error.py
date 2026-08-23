"""The token-error measurement script has to be right to be worth quoting.

The README quotes its output as measured fact, so the parts that could quietly
skew a number are asserted here: the heuristic it compares must be the real
offline one rather than tiktoken wearing a disguise, and the percentile must be
a percentile.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).parents[1]


def load_script() -> ModuleType:
    path = REPO_ROOT / "scripts" / "measure_token_error.py"
    spec = importlib.util.spec_from_file_location("measure_token_error", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_heuristic_matches_estimate_tokens_when_tiktoken_is_absent() -> None:
    """The script reimplements the heuristic so it can measure it directly.

    estimate_tokens prefers tiktoken when installed, so calling it would compare
    tiktoken against itself and report a flat 0% error. The reimplementation has
    to stay identical to the branch it stands in for, or the published bands
    describe something the tool does not do.
    """
    script = load_script()
    from skillcheck import tokenizer

    samples = [
        "---\nname: demo\ndescription: Validates things when asked.\n---\n\nBody text.\n",
        "A short line.",
        "code: `foo(bar)` and a list:\n- one\n- two\n",
    ]
    original = tokenizer._tiktoken_available
    try:
        # Force the offline branch regardless of whether the extra is installed.
        tokenizer._tiktoken_available = True
        tokenizer._tiktoken_enc = None
        for text in samples:
            assert script.heuristic_tokens(text) == tokenizer.estimate_tokens(text), text
    finally:
        tokenizer._tiktoken_available = original


def test_naive_is_the_chars_over_four_rule() -> None:
    script = load_script()
    assert script.naive_tokens("x" * 400) == 100
    assert script.naive_tokens("") == 1  # never zero, so it can be a denominator


def test_percentile_picks_the_nearest_rank() -> None:
    script = load_script()
    values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    assert script.percentile(values, 0.5) == 0.4
    assert script.percentile(values, 0.95) == 0.9
    assert script.percentile(values, 1.0) == 0.9


def test_percentile_handles_a_single_sample_and_none() -> None:
    script = load_script()
    assert script.percentile([0.42], 0.95) == 0.42
    assert script.percentile([], 0.5) == 0.0


def test_percentile_never_indexes_out_of_range() -> None:
    """Nearest rank rounds, so the top fraction must still land inside the list."""
    script = load_script()
    for size in range(1, 12):
        values = [float(i) for i in range(size)]
        for fraction in (0.0, 0.05, 0.5, 0.95, 1.0):
            assert script.percentile(values, fraction) in values
