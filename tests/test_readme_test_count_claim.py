"""Guards the README's test-count claim against drift.

The README states "N tests cover all rule modules, ...". That number
silently ages every time a test is added. v1.0.1 shipped a correction
from 653 -> 663, and the same drift was already creeping back in. This
test makes drift impossible: the next time the suite grows, this test
fails and CI fails until the README is updated in the same commit.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

_README_PATTERN = re.compile(r"^(\d+)\s+tests cover", re.MULTILINE)
_COLLECT_PATTERN = re.compile(r"(\d+)\s+tests? collected")


def _readme_claimed_count() -> int:
    match = _README_PATTERN.search(README.read_text(encoding="utf-8"))
    assert match, "README must contain a 'N tests cover ...' sentence"
    return int(match.group(1))


def _collected_test_count() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    for line in reversed(result.stdout.strip().splitlines()):
        match = _COLLECT_PATTERN.search(line)
        if match:
            return int(match.group(1))
    raise AssertionError(
        f"could not parse test count from pytest --collect-only output:\n{result.stdout!r}"
    )


def test_readme_test_count_matches_collected_count() -> None:
    claimed = _readme_claimed_count()
    collected = _collected_test_count()
    assert claimed == collected, (
        f"README claims {claimed} tests, pytest --collect-only reports "
        f"{collected}. Update the README's 'N tests cover ...' line in the "
        f"same commit that changes the suite size."
    )
