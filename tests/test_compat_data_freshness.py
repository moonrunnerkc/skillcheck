"""Staleness test for compatibility provenance dates.

Each ``_X_DATA_DATE`` constant in ``skillcheck.rules.compat`` records when
the compatibility data for that agent was last verified. If more than 365
days have passed, the data is stale and needs re-verification.

When this test fails, update the constant(s) in compat.py to the date
you last verified the agent behavior, then re-run.
"""

import datetime
from pathlib import Path

import pytest

from skillcheck.parser import parse
from skillcheck.rules import compat
from skillcheck.rules.compat import (
    _CLAUDE_DATA_DATE,
    _CODEX_DATA_DATE,
    _CURSOR_DATA_DATE,
    _VSCODE_DATA_DATE,
    check_unverified_fields,
)

MAX_AGE_DAYS = 365


def _parse_date(date_str: str) -> datetime.date:
    return datetime.date.fromisoformat(date_str)


def test_claude_data_is_fresh():
    """Claude compatibility data must have been verified within the last 365 days."""
    verified = _parse_date(_CLAUDE_DATA_DATE)
    age = (datetime.date.today() - verified).days
    assert age <= MAX_AGE_DAYS, (
        f"Claude compat data is stale: last verified {verified} "
        f"({age} days ago). Re-verify Claude Code field behavior "
        f"and update _CLAUDE_DATA_DATE in compat.py."
    )


def test_codex_data_is_fresh():
    """Codex compatibility data must have been verified within the last 365 days."""
    verified = _parse_date(_CODEX_DATA_DATE)
    age = (datetime.date.today() - verified).days
    assert age <= MAX_AGE_DAYS, (
        f"Codex compat data is stale: last verified {verified} "
        f"({age} days ago). Re-verify Codex field behavior "
        f"and update _CODEX_DATA_DATE in compat.py."
    )


def test_codex_provenance_uses_codex_date_not_claude_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Codex provenance label must track _CODEX_DATA_DATE independently.

    Distinct sentinels prove the wiring: with the Claude and Codex dates set to
    different values, the Codex label must carry the Codex date only. The label
    previously used _CLAUDE_DATA_DATE, which this catches.
    """
    monkeypatch.setattr(compat, "_CLAUDE_DATA_DATE", "1999-01-01")
    monkeypatch.setattr(compat, "_CODEX_DATA_DATE", "2099-12-31")
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(
        "---\nname: x\ndescription: y\nallowed-tools: [Bash]\n---\nBody\n",
        encoding="utf-8",
    )
    messages = [d.message for d in check_unverified_fields(parse(skill_file))]
    codex_lines = [m for m in messages if "Codex:" in m]
    assert codex_lines, "expected a compat.unverified message mentioning Codex"
    assert "Codex: 2099-12-31" in codex_lines[0]
    assert "Codex: 1999-01-01" not in codex_lines[0]


def test_vscode_data_is_fresh():
    """VS Code compatibility data must have been verified within the last 365 days."""
    verified = _parse_date(_VSCODE_DATA_DATE)
    age = (datetime.date.today() - verified).days
    assert age <= MAX_AGE_DAYS, (
        f"VS Code compat data is stale: last verified {verified} "
        f"({age} days ago). Re-verify VS Code/Copilot field behavior "
        f"and update _VSCODE_DATA_DATE in compat.py."
    )


def test_cursor_data_is_fresh():
    """Cursor compatibility data must have been verified within the last 365 days."""
    verified = _parse_date(_CURSOR_DATA_DATE)
    age = (datetime.date.today() - verified).days
    assert age <= MAX_AGE_DAYS, (
        f"Cursor compat data is stale: last verified {verified} "
        f"({age} days ago). Re-verify Cursor field behavior "
        f"and update _CURSOR_DATA_DATE in compat.py."
    )