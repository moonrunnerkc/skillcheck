"""Tests for history data model: compute_skill_hash, build_entry, frozen types."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from skillcheck.core.history import (
    Ledger,
    LedgerEntry,
    ResultCounts,
    RunAgents,
    ValidationModes,
    build_entry,
    compute_skill_hash,
    ledger_path_for,
    load_ledger,
    save_ledger,
)
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity, ValidationResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _make_skill(raw_text: str = "---\nname: test-skill\ndescription: Does a thing.\n---\nBody.\n") -> ParsedSkill:
    return ParsedSkill(
        path=Path("/tmp/SKILL.md"),
        frontmatter={"name": "test-skill", "description": "Does a thing."},
        body="Body.\n",
        body_lines=1,
        raw_text=raw_text,
    )


def _make_result(valid: bool = True, diagnostics: list[Diagnostic] | None = None) -> ValidationResult:
    diags = diagnostics or []
    return ValidationResult(path=Path("/tmp/SKILL.md"), diagnostics=diags)


def _make_modes(symbolic: bool = True, critique: bool = False, graph: bool = False) -> ValidationModes:
    return ValidationModes(symbolic=symbolic, critique=critique, graph=graph)


def _make_agents(critique: str | None = None, graph: str | None = None) -> RunAgents:
    return RunAgents(critique_agent=critique, graph_agent=graph)


def _make_entry(
    skill: ParsedSkill | None = None,
    result: ValidationResult | None = None,
    exit_code: int = 0,
    now: datetime | None = None,
) -> LedgerEntry:
    s = skill or _make_skill()
    r = result or _make_result()
    fixed_now = now or datetime(2026, 4, 24, 15, 30, 0, tzinfo=timezone.utc)
    return build_entry(s, r, _make_modes(), _make_agents(), exit_code, "0.2.0", now=fixed_now)


# ---------------------------------------------------------------------------
# compute_skill_hash
# ---------------------------------------------------------------------------


def test_hash_is_16_hex_chars():
    skill = _make_skill()
    h = compute_skill_hash(skill)
    assert len(h) == 16
    assert re.fullmatch(r"[0-9a-f]{16}", h), f"Not hex: {h!r}"


def test_hash_is_deterministic():
    skill = _make_skill("some content")
    assert compute_skill_hash(skill) == compute_skill_hash(skill)


def test_hash_differs_with_different_content():
    a = compute_skill_hash(_make_skill("content A"))
    b = compute_skill_hash(_make_skill("content B"))
    assert a != b


def test_hash_is_lowercase():
    h = compute_skill_hash(_make_skill())
    assert h == h.lower()


# ---------------------------------------------------------------------------
# build_entry timestamp format
# ---------------------------------------------------------------------------


def test_build_entry_timestamp_format():
    entry = _make_entry(now=datetime(2026, 4, 24, 15, 30, 0, tzinfo=timezone.utc))
    assert _TS_RE.match(entry.timestamp_utc), f"Bad timestamp: {entry.timestamp_utc!r}"


def test_build_entry_timestamp_no_microseconds():
    entry = _make_entry(now=datetime(2026, 4, 24, 9, 5, 3, 123456, tzinfo=timezone.utc))
    # Must be exactly "2026-04-24T09:05:03Z" -- no fractional seconds
    assert entry.timestamp_utc == "2026-04-24T09:05:03Z"


def test_build_entry_uses_injected_now():
    fixed = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(now=fixed)
    assert entry.timestamp_utc == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# build_entry counts and fields
# ---------------------------------------------------------------------------


def test_build_entry_counts_diagnostics():
    diags = [
        Diagnostic(rule="x.a", severity=Severity.ERROR, message="e"),
        Diagnostic(rule="x.b", severity=Severity.WARNING, message="w"),
        Diagnostic(rule="x.c", severity=Severity.WARNING, message="w2"),
        Diagnostic(rule="x.d", severity=Severity.INFO, message="i"),
    ]
    result = ValidationResult(path=Path("/tmp/SKILL.md"), diagnostics=diags)
    entry = _make_entry(result=result, exit_code=1)
    assert entry.result.error == 1
    assert entry.result.warning == 2
    assert entry.result.info == 1
    assert not entry.result.valid


def test_build_entry_valid_reflects_result():
    result = _make_result(valid=True)
    entry = _make_entry(result=result, exit_code=0)
    assert entry.result.valid
    assert entry.exit_code == 0


def test_build_entry_version_recorded():
    entry = _make_entry()
    assert entry.skillcheck_version == "0.2.0"


def test_build_entry_hash_matches_skill():
    skill = _make_skill("unique content xyz")
    entry = _make_entry(skill=skill)
    assert entry.skill_content_hash == compute_skill_hash(skill)


# ---------------------------------------------------------------------------
# Frozen / hashable dataclasses
# ---------------------------------------------------------------------------


def test_ledger_entry_is_frozen():
    entry = _make_entry()
    with pytest.raises(AttributeError):
        entry.exit_code = 99  # type: ignore[misc]


def test_ledger_is_frozen():
    entry = _make_entry()
    ledger = Ledger(version=1, skill_path="SKILL.md", runs=(entry,))
    with pytest.raises(AttributeError):
        ledger.version = 2  # type: ignore[misc]


def test_result_counts_is_frozen():
    rc = ResultCounts(error=0, warning=0, info=0, valid=True)
    with pytest.raises(AttributeError):
        rc.error = 1  # type: ignore[misc]


def test_validation_modes_is_frozen():
    vm = ValidationModes(symbolic=True, critique=False, graph=False)
    with pytest.raises(AttributeError):
        vm.symbolic = False  # type: ignore[misc]


def test_ledger_entry_is_hashable():
    entry = _make_entry()
    s = {entry}
    assert entry in s


def test_ledger_is_hashable():
    entry = _make_entry()
    ledger = Ledger(version=1, skill_path="SKILL.md", runs=(entry,))
    s = {ledger}
    assert ledger in s


# ---------------------------------------------------------------------------
# ledger_path_for
# ---------------------------------------------------------------------------


def test_ledger_path_for_returns_sibling():
    skill_path = Path("/home/user/skills/my-skill/SKILL.md")
    expected = Path("/home/user/skills/my-skill/.skillcheck-history.json")
    assert ledger_path_for(skill_path) == expected


def test_ledger_path_for_is_pure():
    p = Path("/some/path/SKILL.md")
    assert ledger_path_for(p) == ledger_path_for(p)


# ---------------------------------------------------------------------------
# Round-trip: save then load equals the original
# ---------------------------------------------------------------------------


def test_round_trip_single_entry(tmp_path: Path):
    entry = _make_entry()
    ledger = Ledger(version=1, skill_path="SKILL.md", runs=(entry,))
    lp = tmp_path / ".skillcheck-history.json"
    save_ledger(lp, ledger)
    loaded = load_ledger(lp)
    assert loaded is not None
    assert loaded == ledger


def test_round_trip_multiple_entries(tmp_path: Path):
    e1 = _make_entry(now=datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc))
    e2 = _make_entry(now=datetime(2026, 4, 2, 0, 0, 0, tzinfo=timezone.utc))
    ledger = Ledger(version=1, skill_path="SKILL.md", runs=(e1, e2))
    lp = tmp_path / ".skillcheck-history.json"
    save_ledger(lp, ledger)
    loaded = load_ledger(lp)
    assert loaded == ledger
    assert len(loaded.runs) == 2


def test_round_trip_with_agent_fields(tmp_path: Path):
    entry = build_entry(
        _make_skill(),
        _make_result(),
        ValidationModes(symbolic=True, critique=True, graph=True),
        RunAgents(critique_agent="claude", graph_agent="codex"),
        exit_code=0,
        version="0.2.0",
        now=datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
    )
    ledger = Ledger(version=1, skill_path="SKILL.md", runs=(entry,))
    lp = tmp_path / ".skillcheck-history.json"
    save_ledger(lp, ledger)
    loaded = load_ledger(lp)
    assert loaded == ledger
    assert loaded.runs[0].agents.critique_agent == "claude"
    assert loaded.runs[0].agents.graph_agent == "codex"
