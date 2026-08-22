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

import json
import os
from pathlib import Path, PureWindowsPath

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

_GOOD_PATH = Path("skills/good/SKILL.md")
_BAD_PATH = Path("skills/bad/SKILL.md")

# Keyed by str(Path(...)), not a POSIX literal. Both renderers look the
# breakdown up with `str(result.path)`, which is native, so a hardcoded
# forward-slash key silently misses on Windows and the breakdown vanishes from
# the report instead of failing loudly.
_BREAKDOWNS = {
    str(_GOOD_PATH): {
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
        path=_GOOD_PATH,
        diagnostics=[
            Diagnostic(
                rule="description.quality-score",
                severity=Severity.INFO,
                message="Description quality score: 95/100.",
            ),
        ],
    )
    failing = ValidationResult(
        path=_BAD_PATH,
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


_FIXTURE_PATHS = ("skills/good/SKILL.md", "skills/bad/SKILL.md")


def _to_posix_paths(text: str) -> str:
    """Rewrite native path separators in rendered output back to POSIX.

    Golden files are stored with forward slashes. Only `_format_github`
    normalizes separators itself (it has to; GitHub will not match an
    annotation to a file otherwise), so on Windows the other four renderers
    emit `skills\\good\\SKILL.md` and every comparison fails.

    The rewrite is scoped to the two fixture paths rather than a blanket
    backslash replacement, which would corrupt the markdown pipe escape
    (`docs/a\\|b.md`) that these goldens exist to pin. The JSON-escaped form is
    replaced first because it contains the raw form.
    """
    for posix in _FIXTURE_PATHS:
        native = str(Path(posix))
        if native == posix:
            continue
        text = text.replace(json.dumps(native)[1:-1], posix)
        text = text.replace(native, posix)
    return text


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
    actual = _to_posix_paths(_render(name)) + "\n"
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


def test_path_normalizer_restores_windows_separators() -> None:
    """Proves the Windows fix without a Windows runner.

    Simulates what the renderers emit when `Path` is a WindowsPath: the text
    form with single backslashes and the JSON form where json.dumps has
    doubled them. Both must come back as the POSIX form the goldens store.
    """
    win_text = str(PureWindowsPath("skills/good/SKILL.md"))
    assert win_text == "skills\\good\\SKILL.md"

    rendered_text = f"PASS  {win_text}"
    rendered_json = json.dumps({"path": win_text})

    def _normalize(text: str) -> str:
        for posix in _FIXTURE_PATHS:
            native = str(PureWindowsPath(posix))
            text = text.replace(json.dumps(native)[1:-1], posix)
            text = text.replace(native, posix)
        return text

    assert _normalize(rendered_text) == "PASS  skills/good/SKILL.md"
    assert json.loads(_normalize(rendered_json))["path"] == "skills/good/SKILL.md"


def test_path_normalizer_leaves_the_markdown_pipe_escape_alone() -> None:
    """A blanket backslash replacement would corrupt `docs/a\\|b.md`."""
    escaped = "| 41 | error | Broken reference: `docs/a\\|b.md` |"
    assert _to_posix_paths(escaped) == escaped


def test_breakdown_key_matches_what_the_renderers_look_up() -> None:
    """The lookup is `str(result.path)`, so the fixture key must be native.

    A POSIX literal here passes on Linux and macOS while silently dropping the
    --explain-score line on Windows, which is exactly how it first failed: the
    golden kept the breakdown row and the Windows run rendered without it.
    """
    good = next(r for r in _results() if r.valid)
    assert str(good.path) in _BREAKDOWNS
