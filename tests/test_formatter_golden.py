"""Golden-file tests for the five report renderers.

formatters.py is the whole user-facing surface of skillcheck: it is what CI
logs show, what `--format json` consumers parse, and what GitHub renders as PR
annotations. It had almost no direct coverage. The existing formatter tests
check individual escaping helpers (`test_format_github.py`), which catches a
broken `_escape_data` but not a renderer that drops the context line, reorders
a JSON key, or loses the summary.

One fixed diagnostic set is rendered through every formatter and compared byte
for byte against a checked-in golden file. The set is built to exercise what
the renderers actually branch on: a passing and a failing file, all three
severities, a diagnostic with and without a line number, one with and one
without context, a message containing the characters each format has to escape
(`|` for markdown, `%`/CR/LF for GitHub data, `:` and `,` for GitHub
properties), and a score breakdown so the --explain-score path renders.

Regenerate with `make regen-golden` after an intentional renderer change, and
read the diff before committing it: a golden file that changes without a
matching change in formatters.py means something upstream moved.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from skillcheck.formatters import (
    _format_agent,
    _format_github,
    _format_json,
    _format_markdown,
    _format_text,
)
from skillcheck.result import Diagnostic, Severity, ValidationResult

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"

# Pinned so the JSON golden does not churn on every release.
_VERSION = "0.0.0-test"

_BREAKDOWNS = {
    "skills/good/SKILL.md": {
        "action": 25,
        "trigger": 20,
        "keywords": 25,
        "specificity": 15,
        "length": 10,
    }
}


def _results() -> list[ValidationResult]:
    """One passing file and one failing file, covering every renderer branch."""
    passing = ValidationResult(
        path=Path("skills/good/SKILL.md"),
        diagnostics=[
            Diagnostic(
                rule="description.quality-score",
                severity=Severity.INFO,
                message="Description quality score: 95/100.",
            ),
        ],
    )
    failing = ValidationResult(
        path=Path("skills/bad/SKILL.md"),
        diagnostics=[
            Diagnostic(
                rule="frontmatter.name.too-long",
                severity=Severity.ERROR,
                message="Name exceeds 64 characters (got 82): 'a-very-long-name'",
                line=2,
            ),
            Diagnostic(
                rule="sizing.body-lines",
                severity=Severity.WARNING,
                message="Body is 612 lines, over the 500-line threshold.",
                line=None,
                context="Split the body, or move detail behind a reference.",
            ),
            Diagnostic(
                # Exercises markdown pipe escaping and GitHub data escaping in
                # one message: a table cell separator plus a literal percent.
                rule="references.broken",
                severity=Severity.ERROR,
                message="Broken reference: `docs/a|b.md` (100% of links, comma, colon: here)",
                line=41,
            ),
            Diagnostic(
                rule="compat.unverified",
                severity=Severity.INFO,
                message="Behavior of field 'version' in codex is unverified.",
            ),
        ],
    )
    return [passing, failing]


def _render(name: str) -> str:
    results = _results()
    if name == "text":
        return _format_text(
            results,
            color=False,
            critique_source="agent:claude",
            graph_source="heuristic",
            score_breakdowns=_BREAKDOWNS,
            explain_score=True,
        )
    if name == "text_plain":
        # No sources, no breakdown: the default report shape.
        return _format_text(results, color=False)
    if name == "json":
        return _format_json(
            results,
            version=_VERSION,
            critique_source="agent:claude",
            score_breakdowns=_BREAKDOWNS,
        )
    if name == "markdown":
        return _format_markdown(results, critique_source="agent:claude", graph_source="heuristic")
    if name == "github":
        return _format_github(results)
    if name == "agent":
        return _format_agent(results, critique_source="agent:claude", graph_source="heuristic")
    raise AssertionError(f"unknown renderer {name}")


RENDERERS = ["text", "text_plain", "json", "markdown", "github", "agent"]


@pytest.mark.parametrize("name", RENDERERS)
def test_renderer_matches_golden(name: str) -> None:
    golden = GOLDEN_DIR / f"report.{name}.txt"
    actual = _render(name) + "\n"
    if os.environ.get("SKILLCHECK_REGEN_GOLDEN"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(actual, encoding="utf-8")
        pytest.skip(f"regenerated {golden.name}")
    assert golden.exists(), (
        f"Missing golden file {golden}. Run `make regen-golden` to create it, "
        f"then read the diff before committing."
    )
    assert actual == golden.read_text(encoding="utf-8"), (
        f"{name} renderer output drifted from {golden.name}. If the change is "
        f"intended, run `make regen-golden` and commit the updated file."
    )


def test_every_renderer_has_a_golden_file() -> None:
    """A new renderer must arrive with a golden file, not silently uncovered."""
    on_disk = {p.stem.split(".", 1)[1] for p in GOLDEN_DIR.glob("report.*.txt")}
    assert on_disk == set(RENDERERS)


def test_color_codes_are_absent_from_the_text_golden() -> None:
    """The golden is the --no-color form; an ANSI leak would make it unreadable."""
    assert "\033" not in (GOLDEN_DIR / "report.text.txt").read_text(encoding="utf-8")


def test_text_renderer_emits_ansi_when_color_is_on() -> None:
    """Guards the other side: --no-color must be what suppresses the codes."""
    assert "\033" in _format_text(_results(), color=True)
