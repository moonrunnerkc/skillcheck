"""The declarative mode table must reproduce the hand-written checks exactly.

tests/fixtures/mode_conflicts.json was captured from the CLI before the rules
moved into skillcheck.modes: every unordered pair of the ten mode flags, its
exit code, and its exact stderr. Refactoring a set of conditionals into a table
is only safe if the wording survives, so the fixture is replayed here rather
than the new behavior being described afresh.

Rows whose stderr is the path error are the pairs that legitimately combine.
They matter as much as the conflicting ones: a table that over-rejects would
show up here as a conflict where the CLI previously ran.

Regenerate with `python3 scripts/regen_mode_conflict_fixture.py`, and only when
a message is intentionally reworded.
"""
from __future__ import annotations

import json
import subprocess
from itertools import combinations
from pathlib import Path

import pytest

from skillcheck.cli import _build_parser
from skillcheck.modes import (
    GROUP_AUGMENT,
    GROUP_EMIT,
    GROUP_LEDGER,
    MODE_FLAGS,
    PAIRWISE_CONFLICTS,
    active_flags,
    find_mode_conflict,
)
from tests.conftest import SKILLCHECK_CMD

REPO_ROOT = Path(__file__).parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "mode_conflicts.json"

MISSING_PATH = "__does_not_exist__/SKILL.md"

# Same activation fragments the capture script uses.
_ARGV: dict[str, list[str]] = {
    "--emit-critique-prompt": ["--emit-critique-prompt"],
    "--emit-graph": ["--emit-graph"],
    "--emit-graph-prompt": ["--emit-graph-prompt"],
    "--activation-hypotheses": ["--activation-hypotheses"],
    "--agent-reason": ["--agent-reason"],
    "--ingest-critique": ["--ingest-critique", "response.json"],
    "--ingest-graph": ["--ingest-graph", "response.json"],
    "--analyze-graph": ["--analyze-graph"],
    "--history": ["--history"],
    "--show-history": ["--show-history"],
}

_ROWS = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _args(*flags: str):
    argv = [MISSING_PATH]
    for flag in flags:
        argv += _ARGV[flag]
    return _build_parser().parse_args(argv)


def _row_id(row: dict) -> str:
    return f"{row['flags'][0]}+{row['flags'][1]}"


# ---------------------------------------------------------------------------
# Byte-for-byte replay of the captured behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("row", _ROWS, ids=[_row_id(r) for r in _ROWS])
def test_pair_matches_captured_behavior(row: dict) -> None:
    flag_a, flag_b = row["flags"]
    captured = row["stderr"]
    message = find_mode_conflict(_args(flag_a, flag_b))

    if "Cannot use" in captured:
        assert message is not None, (
            f"{flag_a} + {flag_b} used to be rejected and now is not."
        )
        assert message + "\n" == captured, (
            f"{flag_a} + {flag_b} conflict wording changed.\n"
            f"captured: {captured!r}\nnow:      {message + chr(10)!r}"
        )
    else:
        assert message is None, (
            f"{flag_a} + {flag_b} used to be allowed and is now rejected with: {message!r}"
        )


def test_fixture_covers_every_pair_of_mode_flags() -> None:
    """A new mode flag must be captured, not silently left untested."""
    expected = {tuple(sorted(pair)) for pair in combinations(sorted(_ARGV), 2)}
    captured = {tuple(sorted(row["flags"])) for row in _ROWS}
    assert captured == expected


def test_activation_fragments_cover_every_declared_flag() -> None:
    assert set(_ARGV) == {mode.flag for mode in MODE_FLAGS}


# ---------------------------------------------------------------------------
# Structural invariants, so future additions cannot drift
# ---------------------------------------------------------------------------


def test_conflicts_are_symmetric() -> None:
    """If A conflicts with B, then B conflicts with A.

    Detection reads both flags off one namespace, so order cannot matter, but
    asserting it means a future checker that walks the pair in one direction
    only will fail here rather than silently letting one ordering through.
    """
    for conflict in PAIRWISE_CONFLICTS:
        forward = find_mode_conflict(_args(conflict.flag_a, conflict.flag_b))
        backward = find_mode_conflict(_args(conflict.flag_b, conflict.flag_a))
        assert forward is not None and backward is not None, (
            f"{conflict.flag_a} + {conflict.flag_b} is declared but not detected"
        )
        assert forward == backward, (
            f"{conflict.flag_a} + {conflict.flag_b} reports differently depending on argv order"
        )


def test_no_unordered_pair_is_declared_twice() -> None:
    """A second entry for the same pair is dead code; the first one always wins."""
    seen = [tuple(sorted((c.flag_a, c.flag_b))) for c in PAIRWISE_CONFLICTS]
    duplicates = {pair for pair in seen if seen.count(pair) > 1}
    assert not duplicates, f"duplicate conflict entries: {duplicates}"


def test_every_conflict_names_a_declared_flag() -> None:
    known = {mode.flag for mode in MODE_FLAGS}
    for conflict in PAIRWISE_CONFLICTS:
        assert conflict.flag_a in known, f"unknown flag {conflict.flag_a}"
        assert conflict.flag_b in known, f"unknown flag {conflict.flag_b}"


def test_every_conflict_reason_names_both_flags() -> None:
    """The message has to say which two flags clashed, or it is not actionable."""
    for conflict in PAIRWISE_CONFLICTS:
        assert conflict.flag_a in conflict.reason
        assert conflict.flag_b in conflict.reason


def test_every_mode_flag_resolves_on_the_parser() -> None:
    """The dest names are the coupling to argparse; a typo would read as False."""
    parsed = _build_parser().parse_args([MISSING_PATH])
    for mode in MODE_FLAGS:
        assert hasattr(parsed, mode.dest), f"{mode.flag} has no dest {mode.dest!r}"


def test_every_mode_flag_is_in_a_known_group() -> None:
    assert {mode.group for mode in MODE_FLAGS} == {GROUP_EMIT, GROUP_AUGMENT, GROUP_LEDGER}


def test_suppression_targets_are_declared_flags() -> None:
    known = {mode.flag for mode in MODE_FLAGS}
    for mode in MODE_FLAGS:
        for other in mode.suppressed_by:
            assert other in known, f"{mode.flag} is suppressed by unknown {other}"


# ---------------------------------------------------------------------------
# The suppression rule that makes --agent-reason two different things
# ---------------------------------------------------------------------------


def test_agent_reason_is_an_emit_mode_on_its_own() -> None:
    assert active_flags(_args("--agent-reason"))["--agent-reason"] is True


@pytest.mark.parametrize("ingest", ["--ingest-critique", "--ingest-graph"])
def test_agent_reason_stops_being_an_emit_mode_with_an_ingest_flag(ingest: str) -> None:
    """Paired with an ingest flag it modifies the ingest run instead of emitting.

    If it still counted as an emit mode the pair would be rejected, which would
    break the documented `--agent-reason --ingest-critique` workflow.
    """
    args = _args("--agent-reason", ingest)
    assert active_flags(args)["--agent-reason"] is False
    assert find_mode_conflict(args) is None


# ---------------------------------------------------------------------------
# The CLI still exits 2 and prints to stderr
# ---------------------------------------------------------------------------


def test_cli_still_exits_two_and_prints_the_message() -> None:
    result = subprocess.run(
        [*SKILLCHECK_CMD, MISSING_PATH, "--emit-graph", "--analyze-graph"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 2
    assert result.stderr == find_mode_conflict(_args("--emit-graph", "--analyze-graph")) + "\n"
    assert result.stdout == ""


def test_cli_reports_the_multi_emit_case_before_the_pairwise_table() -> None:
    """Ordering is user-visible when several conflicts apply at once."""
    result = subprocess.run(
        [*SKILLCHECK_CMD, MISSING_PATH, "--emit-graph", "--emit-graph-prompt", "--analyze-graph"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 2
    assert "Pick one emit mode." in result.stderr
