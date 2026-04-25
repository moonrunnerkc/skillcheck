"""Tests for check_regression: the history.skill.regressed analyzer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from skillcheck.core.history import (
    LedgerEntry,
    ResultCounts,
    RunAgents,
    ValidationModes,
    build_entry,
    check_regression,
)
from skillcheck.parser import ParsedSkill
from skillcheck.result import Severity, ValidationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill(raw: str = "content") -> ParsedSkill:
    return ParsedSkill(
        path=Path("/tmp/SKILL.md"),
        frontmatter={"name": "test", "description": "Tests things."},
        body="",
        body_lines=0,
        raw_text=raw,
    )


def _make_result(valid: bool = True) -> ValidationResult:
    return ValidationResult(path=Path("/tmp/SKILL.md"), diagnostics=[])


_MODES = ValidationModes(symbolic=True, critique=False, graph=False)
_AGENTS = RunAgents(critique_agent=None, graph_agent=None)


def _entry(raw: str, valid: bool, ts: str) -> LedgerEntry:
    # Parse timestamp to produce the right hash and validity.
    year, month, rest = ts[:4], ts[5:7], ts[8:]
    day, time_part = rest[:2], rest[3:11]
    h, m, s = time_part[:2], time_part[3:5], time_part[6:8]
    now = datetime(int(year), int(month), int(day), int(h), int(m), int(s), tzinfo=timezone.utc)
    skill = _make_skill(raw)
    result = _make_result(valid=valid)
    entry = build_entry(skill, result, _MODES, _AGENTS, exit_code=0 if valid else 1, version="0.2.0", now=now)
    # Override the result.valid since build_entry counts diagnostics (all zero here).
    # Build a new entry with the right valid flag by patching ResultCounts.
    from dataclasses import replace  # type: ignore[attr-defined]
    patched_result = ResultCounts(
        error=0 if valid else 1,
        warning=entry.result.warning,
        info=entry.result.info,
        valid=valid,
    )
    return LedgerEntry(
        timestamp_utc=entry.timestamp_utc,
        skillcheck_version=entry.skillcheck_version,
        skill_content_hash=entry.skill_content_hash,
        validation_modes=entry.validation_modes,
        agents=entry.agents,
        result=patched_result,
        exit_code=0 if valid else 1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_prior_runs_returns_empty():
    current = _entry("content", valid=False, ts="2026-04-24T15:00:00Z")
    assert check_regression((), current) == []


def test_prior_passing_same_hash_current_failing_emits_warning():
    prior = _entry("same content", valid=True, ts="2026-04-20T10:00:00Z")
    current = _entry("same content", valid=False, ts="2026-04-24T15:00:00Z")
    diags = check_regression((prior,), current)
    assert len(diags) == 1
    assert diags[0].severity == Severity.WARNING
    assert diags[0].rule == "history.skill.regressed"
    assert "2026-04-20T10:00:00Z" in diags[0].message


def test_prior_passing_same_hash_current_passing_returns_empty():
    prior = _entry("same content", valid=True, ts="2026-04-20T10:00:00Z")
    current = _entry("same content", valid=True, ts="2026-04-24T15:00:00Z")
    assert check_regression((prior,), current) == []


def test_prior_failing_same_hash_current_failing_returns_empty():
    prior = _entry("same content", valid=False, ts="2026-04-20T10:00:00Z")
    current = _entry("same content", valid=False, ts="2026-04-24T15:00:00Z")
    assert check_regression((prior,), current) == []


def test_prior_passing_different_hash_returns_empty():
    prior = _entry("content A", valid=True, ts="2026-04-20T10:00:00Z")
    current = _entry("content B", valid=False, ts="2026-04-24T15:00:00Z")
    # Hashes differ because raw text differs.
    assert prior.skill_content_hash != current.skill_content_hash
    assert check_regression((prior,), current) == []


def test_multiple_matching_priors_emits_one_warning_with_most_recent():
    prior_old = _entry("same", valid=True, ts="2026-04-10T08:00:00Z")
    prior_recent = _entry("same", valid=True, ts="2026-04-20T12:00:00Z")
    current = _entry("same", valid=False, ts="2026-04-24T15:00:00Z")
    diags = check_regression((prior_old, prior_recent), current)
    assert len(diags) == 1
    # Most recent prior timestamp appears in the message.
    assert "2026-04-20T12:00:00Z" in diags[0].message
    assert "2026-04-10T08:00:00Z" not in diags[0].message


def test_regression_message_includes_result_counts():
    prior = _entry("same", valid=True, ts="2026-04-20T10:00:00Z")
    current = _entry("same", valid=False, ts="2026-04-24T15:00:00Z")
    diags = check_regression((prior,), current)
    msg = diags[0].message
    # Message must reference both prior and current result summaries.
    assert "prior" in msg
    assert "current" in msg


def test_recovery_does_not_trigger_regression():
    """Passing after a prior failure on same content is not a regression."""
    prior_fail = _entry("same", valid=False, ts="2026-04-20T10:00:00Z")
    current_pass = _entry("same", valid=True, ts="2026-04-24T15:00:00Z")
    assert check_regression((prior_fail,), current_pass) == []
