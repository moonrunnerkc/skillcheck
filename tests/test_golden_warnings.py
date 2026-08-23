"""Golden output for the warning modes that generate the most user friction.

Unknown frontmatter fields, reserved-word name collisions, and person-voice
descriptions are the three findings authors most often argue with, so their
exact wording matters more than most. The case study records the same three as
the commonest real-world failures.

Each case is a real SKILL.md under `tests/golden/<case>/` plus an `expected.txt`
holding the full diagnostic list: rule ID, severity, line, and message, one per
line. The runner diffs actual against expected rather than asserting substrings,
so a reworded message, a shifted line number, a dropped diagnostic, or a new one
appearing all fail the same way.

The point is to freeze current behavior ahead of the scorer work: a change that
improves scoring must not quietly move an unrelated diagnostic, and if it does
move one the diff says exactly which.

Regenerate with `make regen-golden-warnings`, and read the diff.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from skillcheck.core.symbolic import validate
from skillcheck.result import Diagnostic

GOLDEN_DIR = Path(__file__).parent / "golden"

CASES = sorted(p.name for p in GOLDEN_DIR.iterdir() if (p / "SKILL.md").exists())


def _render(diagnostics: list[Diagnostic]) -> str:
    """One diagnostic per line: everything a reader would check by eye.

    Sorted by rule then line so the file is stable against rule-registration
    order, which is not part of what these cases are pinning.
    """
    rows = sorted(
        (d.rule, -1 if d.line is None else d.line, d.severity.value, d.message)
        for d in diagnostics
    )
    return "".join(
        f"{rule}\t{severity}\tline={'-' if line < 0 else line}\t{message}\n"
        for rule, line, severity, message in rows
    )


def _actual(case: str) -> str:
    skill = GOLDEN_DIR / case / "SKILL.md"
    # skip_dirname_check is off: the fixture directories are named for their
    # `name` field precisely so the dirname rule stays quiet and does not
    # crowd the output these cases exist to pin.
    result = validate(skill)
    return _render(result.diagnostics)


@pytest.mark.parametrize("case", CASES)
def test_golden_case(case: str) -> None:
    expected_path = GOLDEN_DIR / case / "expected.txt"
    actual = _actual(case)

    if os.environ.get("SKILLCHECK_REGEN_GOLDEN"):
        expected_path.write_text(actual, encoding="utf-8")
        pytest.skip(f"regenerated {case}/expected.txt")

    assert expected_path.exists(), (
        f"Missing {expected_path}. Run `make regen-golden-warnings` to create it, "
        f"then read the diff before committing."
    )
    expected = expected_path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"Diagnostics for golden case {case!r} changed.\n\n"
        f"expected:\n{expected}\nactual:\n{actual}\n"
        f"If the change is intended, run `make regen-golden-warnings` and commit it."
    )


def test_every_case_directory_has_an_expected_file() -> None:
    """A new case must arrive with its golden, not silently pass by absence."""
    missing = [c for c in CASES if not (GOLDEN_DIR / c / "expected.txt").exists()]
    assert not missing, f"golden cases without expected.txt: {missing}"


# ---------------------------------------------------------------------------
# The three friction modes are actually represented
#
# Without these, deleting a fixture would quietly shrink coverage while every
# remaining golden still passed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "rule"),
    [
        ("unknown-fields", "frontmatter.field.unknown"),
        ("unknown-fields", "frontmatter.field.ecosystem"),
        ("claude-doc-helper", "frontmatter.name.reserved-word"),
        ("person-voice-first", "frontmatter.description.person-voice"),
        ("person-voice-second", "frontmatter.description.person-voice"),
    ],
)
def test_case_still_triggers_its_rule(case: str, rule: str) -> None:
    assert rule in _actual(case), f"{case} no longer produces {rule}"


def test_clean_baseline_produces_no_warnings_or_errors() -> None:
    """The negative control: a well-formed skill stays quiet.

    Without it, a rule that fired on everything would still satisfy every
    positive case above.
    """
    result = validate(GOLDEN_DIR / "clean-baseline" / "SKILL.md")
    noisy = [d for d in result.diagnostics if d.severity.value != "info"]
    assert noisy == [], f"clean baseline emitted {[d.rule for d in noisy]}"


def test_person_voice_reports_the_offending_phrase() -> None:
    """The message quotes what it matched, which is what makes it actionable."""
    first = _actual("person-voice-first")
    assert "first-person voice ('I')" in first, first
    second = _actual("person-voice-second")
    assert "second-person voice ('You should')" in second, second
