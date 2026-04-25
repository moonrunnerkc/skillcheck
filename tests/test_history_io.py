"""Tests for ledger I/O: load_ledger, save_ledger, append_run."""

from __future__ import annotations

import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from skillcheck.core.history import (
    Ledger,
    LedgerEntry,
    LedgerError,
    ResultCounts,
    RunAgents,
    ValidationModes,
    append_run,
    build_entry,
    load_ledger,
    save_ledger,
)
from skillcheck.parser import ParsedSkill
from skillcheck.result import ValidationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill(path: Path, raw: str = "---\nname: t\ndescription: Does x.\n---\n") -> ParsedSkill:
    return ParsedSkill(
        path=path,
        frontmatter={"name": "t", "description": "Does x."},
        body="",
        body_lines=0,
        raw_text=raw,
    )


def _make_result(path: Path, valid: bool = True) -> ValidationResult:
    return ValidationResult(path=path, diagnostics=[])


def _fixed_entry(path: Path, ts: str = "2026-04-24T10:00:00Z") -> LedgerEntry:
    skill = _make_skill(path)
    result = _make_result(path)
    now = datetime(2026, 4, 24, 10, 0, 0, tzinfo=timezone.utc)
    return build_entry(
        skill,
        result,
        ValidationModes(symbolic=True, critique=False, graph=False),
        RunAgents(critique_agent=None, graph_agent=None),
        exit_code=0,
        version="0.2.0",
        now=now,
    )


# ---------------------------------------------------------------------------
# load_ledger
# ---------------------------------------------------------------------------


def test_load_returns_none_for_missing_file(tmp_path: Path):
    lp = tmp_path / ".skillcheck-history.json"
    assert load_ledger(lp) is None


def test_load_raises_on_malformed_json(tmp_path: Path):
    lp = tmp_path / ".skillcheck-history.json"
    lp.write_text("{ not valid json }", encoding="utf-8")
    with pytest.raises(LedgerError, match="not valid JSON"):
        load_ledger(lp)


def test_load_raises_on_missing_top_level_field(tmp_path: Path):
    lp = tmp_path / ".skillcheck-history.json"
    lp.write_text('{"version": 1, "runs": []}', encoding="utf-8")
    with pytest.raises(LedgerError):
        load_ledger(lp)


def test_load_raises_error_includes_path(tmp_path: Path):
    lp = tmp_path / ".skillcheck-history.json"
    lp.write_text("bad json!", encoding="utf-8")
    with pytest.raises(LedgerError, match=str(lp)):
        load_ledger(lp)


def test_load_from_fixture_one_run():
    lp = Path(__file__).parent / "fixtures" / "history" / "ledger_one_run.json"
    ledger = load_ledger(lp)
    assert ledger is not None
    assert ledger.version == 1
    assert len(ledger.runs) == 1
    assert ledger.runs[0].result.valid


def test_load_from_fixture_multi_run():
    lp = Path(__file__).parent / "fixtures" / "history" / "ledger_multi_run_passing.json"
    ledger = load_ledger(lp)
    assert ledger is not None
    assert len(ledger.runs) == 3
    assert all(r.result.valid for r in ledger.runs)


def test_load_from_fixture_malformed_raises():
    lp = Path(__file__).parent / "fixtures" / "history" / "ledger_malformed.json"
    with pytest.raises(LedgerError):
        load_ledger(lp)


# ---------------------------------------------------------------------------
# save_ledger (atomic write)
# ---------------------------------------------------------------------------


def test_save_writes_valid_json(tmp_path: Path):
    import json
    skill_path = tmp_path / "SKILL.md"
    entry = _fixed_entry(skill_path)
    ledger = Ledger(version=1, skill_path="SKILL.md", runs=(entry,))
    lp = tmp_path / ".skillcheck-history.json"
    save_ledger(lp, ledger)
    raw = lp.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["version"] == 1
    assert data["skill_path"] == "SKILL.md"
    assert len(data["runs"]) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="chmod restrictions differ on Windows")
def test_save_atomic_original_intact_on_failure(tmp_path: Path):
    """Original ledger survives a failed write (read-only directory)."""
    import json

    skill_path = tmp_path / "SKILL.md"
    entry = _fixed_entry(skill_path)
    ledger = Ledger(version=1, skill_path="SKILL.md", runs=(entry,))
    lp = tmp_path / ".skillcheck-history.json"
    save_ledger(lp, ledger)

    original_content = lp.read_text(encoding="utf-8")

    # Make the directory read-only so a new write attempt will fail.
    old_mode = tmp_path.stat().st_mode
    try:
        os.chmod(tmp_path, stat.S_IRUSR | stat.S_IXUSR)
        entry2 = _fixed_entry(skill_path)
        ledger2 = Ledger(version=1, skill_path="SKILL.md", runs=(entry, entry2))
        with pytest.raises(LedgerError):
            save_ledger(lp, ledger2)
    finally:
        os.chmod(tmp_path, old_mode)

    # Original file must be intact.
    assert lp.read_text(encoding="utf-8") == original_content


def test_save_field_order_matches_schema(tmp_path: Path):
    """Serialized field order follows dataclass declaration order, not sort_keys."""
    import json
    skill_path = tmp_path / "SKILL.md"
    entry = _fixed_entry(skill_path)
    ledger = Ledger(version=1, skill_path="SKILL.md", runs=(entry,))
    lp = tmp_path / ".skillcheck-history.json"
    save_ledger(lp, ledger)
    raw = lp.read_text(encoding="utf-8")
    # Top-level key order
    data = json.loads(raw)
    keys = list(data.keys())
    assert keys == ["version", "skill_path", "runs"]
    # Run key order
    run_keys = list(data["runs"][0].keys())
    expected = ["timestamp_utc", "skillcheck_version", "skill_content_hash",
                "validation_modes", "agents", "result", "exit_code"]
    assert run_keys == expected


# ---------------------------------------------------------------------------
# append_run
# ---------------------------------------------------------------------------


def test_append_run_initializes_new_ledger(tmp_path: Path):
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("---\nname: t\ndescription: D.\n---\n", encoding="utf-8")
    skill = _make_skill(skill_path)
    entry = _fixed_entry(skill_path)
    lp = tmp_path / ".skillcheck-history.json"

    ledger = append_run(lp, skill, entry)
    assert ledger.version == 1
    assert len(ledger.runs) == 1
    assert ledger.runs[0] == entry


def test_append_run_preserves_prior_runs(tmp_path: Path):
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("---\nname: t\ndescription: D.\n---\n", encoding="utf-8")
    skill = _make_skill(skill_path)
    lp = tmp_path / ".skillcheck-history.json"

    e1 = _fixed_entry(skill_path)
    append_run(lp, skill, e1)

    e2 = build_entry(
        skill,
        _make_result(skill_path),
        ValidationModes(symbolic=True, critique=False, graph=False),
        RunAgents(critique_agent=None, graph_agent=None),
        exit_code=0,
        version="0.2.0",
        now=datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc),
    )
    ledger = append_run(lp, skill, e2)
    assert len(ledger.runs) == 2
    assert ledger.runs[0] == e1
    assert ledger.runs[1] == e2


def test_append_run_mismatched_skill_path_raises(tmp_path: Path):
    skill_path_a = tmp_path / "SKILL.md"
    skill_path_a.write_text("---\nname: a\ndescription: A.\n---\n", encoding="utf-8")
    skill_a = _make_skill(skill_path_a)
    lp = tmp_path / ".skillcheck-history.json"
    e1 = _fixed_entry(skill_path_a)
    append_run(lp, skill_a, e1)

    # Now try to append with a skill from a different directory.
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    skill_path_b = other_dir / "SKILL.md"
    skill_path_b.write_text("---\nname: b\ndescription: B.\n---\n", encoding="utf-8")
    skill_b = _make_skill(skill_path_b)
    e2 = _fixed_entry(skill_path_b)

    with pytest.raises(LedgerError, match="skill was renamed"):
        append_run(lp, skill_b, e2)
