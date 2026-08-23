#!/usr/bin/env python3
"""Measure the offline token heuristic against tiktoken across a corpus.

The README used to quote error bands taken from a comment in tokenizer.py that
nobody had re-measured. This produces them: relative error per text, then the
median, the p95, and the direction of the bias.

Relative error is (heuristic - tiktoken) / tiktoken, signed, so the sign says
whether the heuristic runs high or low. A skill sized just under a budget by an
estimator that runs low is the case that matters, which an absolute-error
summary would hide.

Three text spans are measured because three rules use them: the whole file
(sizing.total-tokens), the frontmatter block (disclosure.metadata-budget), and
the body (disclosure.body-budget).

Requires the tiktoken extra. Deterministic given the same corpus and the same
cl100k_base vocabulary: no network beyond tiktoken's first-use vocabulary
download, no model, no randomness.

    python3 scripts/measure_token_error.py ~/.claude/plugins
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillcheck.parser import ParseError, parse  # noqa: E402
from skillcheck.tokenizer import _PUNCT_RE, _WORD_RE  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent


def heuristic_tokens(text: str) -> int:
    """The offline estimate, independent of whether tiktoken is installed.

    tokenizer.estimate_tokens prefers tiktoken when available, so calling it
    here would compare tiktoken against itself.
    """
    word_tokens = int(len(_WORD_RE.findall(text)) * 1.3)
    punct_tokens = int(len(_PUNCT_RE.findall(text)) * 1.5)
    return max(1, word_tokens + punct_tokens)


def naive_tokens(text: str) -> int:
    """The chars/4 rule of thumb the word-run heuristic replaced.

    Measured alongside so the README's comparison against it is a number rather
    than folklore.
    """
    return max(1, len(text) // 4)


def find_skills(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", ".venv"}]
        if "SKILL.md" in filenames:
            found.append(Path(dirpath) / "SKILL.md")
    return sorted(found)


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile. No numpy, and exact for the sizes involved."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * len(ordered)) - 1))
    return ordered[index]


def summarize(label: str, errors: list[float]) -> None:
    if not errors:
        print(f"  {label:12s} no samples")
        return
    absolute = [abs(e) for e in errors]
    signed_median = percentile(errors, 0.5)
    over = sum(1 for e in errors if e > 0)
    print(
        f"  {label:12s} n={len(errors):3d}  "
        f"median |err| {percentile(absolute, 0.5):5.1%}  "
        f"p95 |err| {percentile(absolute, 0.95):5.1%}  "
        f"max |err| {max(absolute):5.1%}  "
        f"signed median {signed_median:+6.1%}  "
        f"over-estimates {over}/{len(errors)}"
    )


def main(argv: list[str]) -> int:
    try:
        import tiktoken
    except ModuleNotFoundError:
        print(
            'tiktoken is required. Install it with: pip install "skillcheck[tiktoken]"',
            file=sys.stderr,
        )
        return 2

    encoder = tiktoken.get_encoding("cl100k_base")

    roots = [Path(a) for a in argv[1:]] or [REPO_ROOT / "skills", REPO_ROOT / "tests"]
    paths: list[Path] = []
    for root in roots:
        paths.extend(find_skills(root))

    spans: dict[str, list[float]] = {"whole file": [], "frontmatter": [], "body": []}
    naive: list[float] = []

    for path in paths:
        try:
            skill = parse(path)
        except (ParseError, OSError):
            continue
        raw = skill.raw_text
        frontmatter_text = raw[: raw.find(skill.body)] if skill.body and skill.body in raw else ""
        for label, text in (
            ("whole file", raw),
            ("frontmatter", frontmatter_text),
            ("body", skill.body),
        ):
            if not text.strip():
                continue
            truth = len(encoder.encode(text))
            if truth == 0:
                continue
            spans[label].append((heuristic_tokens(text) - truth) / truth)
            if label == "whole file":
                naive.append((naive_tokens(text) - truth) / truth)

    print(f"corpus: {len(paths)} SKILL.md files")
    print("offline heuristic vs tiktoken cl100k_base, relative error:")
    for label, errors in spans.items():
        summarize(label, errors)
    print()
    print("for comparison, the chars/4 rule of thumb, whole file:")
    summarize("naive", naive)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
