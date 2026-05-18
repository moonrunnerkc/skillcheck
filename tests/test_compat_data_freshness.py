"""Staleness test for compatibility provenance dates.

Each ``_X_DATA_DATE`` constant in ``skillcheck.rules.compat`` records when
the compatibility data for that agent was last verified. If more than 365
days have passed, the data is stale and needs re-verification.

When this test fails, update the constant(s) in compat.py to the date
you last verified the agent behavior, then re-run.
"""

import datetime

from skillcheck.rules.compat import (
    _CLAUDE_DATA_DATE,
    _CURSOR_DATA_DATE,
    _VSCODE_DATA_DATE,
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