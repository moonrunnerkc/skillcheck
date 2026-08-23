#!/usr/bin/env python3
"""Score every description in a corpus of SKILL.md files.

Prints the score distribution and the per-dimension miss rate, so a scorer
change can be measured rather than argued about. Run it before and after a
change and diff the two outputs.

The corpus is whatever directory tree is passed in; every file named SKILL.md
under it is read. The repo's own `runs/` artifacts are gitignored and not
present in a fresh checkout, so point this at any tree of real skills, for
example an installed plugin cache:

    python3 scripts/score_corpus.py ~/.claude/plugins

With no argument it scores the skills and fixtures inside this repo, which is
small but always available.

Deterministic: no network, no model, no randomness. Same corpus in, same
numbers out.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillcheck.config import DESCRIPTION_SCORE_WEIGHTS  # noqa: E402
from skillcheck.parser import ParseError, parse  # noqa: E402
from skillcheck.rules.description import score_description  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent


def find_skills(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", ".venv"}]
        if "SKILL.md" in filenames:
            found.append(Path(dirpath) / "SKILL.md")
    return sorted(found)


def descriptions(paths: list[Path]) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for path in paths:
        try:
            skill = parse(path)
        except (ParseError, OSError):
            continue
        desc = skill.frontmatter.get("description")
        if isinstance(desc, str) and desc.strip():
            out.append((path, desc.strip()))
    return out


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv[1:]] or [REPO_ROOT / "skills", REPO_ROOT / "tests"]
    paths: list[Path] = []
    for root in roots:
        paths.extend(find_skills(root))

    pairs = descriptions(paths)
    if not pairs:
        print("No SKILL.md descriptions found.", file=sys.stderr)
        return 1

    scores: list[int] = []
    per_dimension: dict[str, list[int]] = {name: [] for name in DESCRIPTION_SCORE_WEIGHTS}
    rows: list[tuple[int, str, dict[str, Any]]] = []

    for _path, desc in pairs:
        total, _suggestions, breakdown = score_description(desc)
        scores.append(total)
        for name in DESCRIPTION_SCORE_WEIGHTS:
            per_dimension[name].append(breakdown.get(name, 0))
        rows.append((total, desc, breakdown))

    scores.sort()
    n = len(scores)
    median = scores[n // 2]
    mean = sum(scores) / n

    print(f"corpus: {n} descriptions from {len(paths)} SKILL.md files")
    print(f"score: min {scores[0]}  median {median}  mean {mean:.1f}  max {scores[-1]}")
    print()

    buckets = Counter((s // 10) * 10 for s in scores)
    print("distribution:")
    for lo in range(0, 101, 10):
        count = buckets.get(lo, 0)
        if count:
            print(f"  {lo:3d}-{min(lo + 9, 100):3d}  {'#' * count} ({count})")
    print()

    print("per dimension, share of corpus scoring zero:")
    for name, maximum in DESCRIPTION_SCORE_WEIGHTS.items():
        values = per_dimension[name]
        zeros = sum(1 for v in values if v == 0)
        full = sum(1 for v in values if v == maximum)
        print(
            f"  {name:12s} max {maximum:2d}  zero {zeros:3d}/{n} ({zeros / n:5.1%})  "
            f"full {full:3d}/{n} ({full / n:5.1%})  mean {sum(values) / n:5.2f}"
        )
    print()

    print("lowest 15 (candidate false negatives):")
    for total, desc, breakdown in sorted(rows, key=lambda r: r[0])[:15]:
        misses = ",".join(k for k, v in breakdown.items() if v == 0)
        print(f"  {total:3d}  [{misses}]  {desc[:96]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
