"""Every file skillcheck reads from disk is bounded by one shared guard.

Only the ingest path was capped before: `--ingest-critique` checked its payload
against MAX_INGEST_BYTES while the SKILL.md, the history ledger, and
skillcheck.toml were read with a bare `path.read_text()`. In the case that
matters, CI running skillcheck over a fork's pull request, all three arrive
from the branch under test, so an oversized one was read fully into memory
before any rule ran.

These tests write real oversized files rather than mocking `stat`, because the
guard's whole job is to measure what is actually on disk.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from skillcheck.config_loader import ConfigError, load_config
from skillcheck.core.history import LedgerError
from skillcheck.core.history_io import load_ledger
from skillcheck.io_limits import (
    MAX_CONFIG_BYTES,
    MAX_INGEST_BYTES,
    MAX_LEDGER_BYTES,
    MAX_SKILL_BYTES,
    enforce_size_cap,
)
from skillcheck.parser import ParseError, parse


class _Boom(Exception):
    pass


def _write_bytes(path: Path, size: int) -> Path:
    path.write_bytes(b"x" * size)
    return path


# ---------------------------------------------------------------------------
# The guard itself
# ---------------------------------------------------------------------------


def test_file_over_the_cap_raises_the_callers_error_type(tmp_path: Path) -> None:
    target = _write_bytes(tmp_path / "big.txt", 101)
    with pytest.raises(_Boom) as exc:
        enforce_size_cap(target, 100, _Boom, "Thing")
    message = str(exc.value)
    assert "Thing" in message
    assert "101 bytes" in message
    assert "100-byte limit" in message
    assert str(target) in message


def test_file_exactly_at_the_cap_is_accepted(tmp_path: Path) -> None:
    """The cap is inclusive, so a file of exactly max_bytes must not be refused."""
    target = _write_bytes(tmp_path / "exact.txt", 100)
    enforce_size_cap(target, 100, _Boom, "Thing")


def test_empty_file_is_accepted(tmp_path: Path) -> None:
    enforce_size_cap(_write_bytes(tmp_path / "empty.txt", 0), 100, _Boom, "Thing")


def test_missing_file_defers_to_the_caller(tmp_path: Path) -> None:
    """A path that cannot be stat'ed is the caller's error to report, not ours.

    Each reader already raises a typed error naming the path when its own read
    fails; pre-empting that with a size error would replace a precise message
    with a misleading one.
    """
    enforce_size_cap(tmp_path / "absent.txt", 100, _Boom, "Thing")


def test_caps_are_ordered_by_how_large_each_file_legitimately_gets() -> None:
    """Config is the smallest, the ledger grows per run, so it is the largest."""
    assert MAX_CONFIG_BYTES < MAX_SKILL_BYTES < MAX_INGEST_BYTES < MAX_LEDGER_BYTES


# ---------------------------------------------------------------------------
# Each reader is wired to it
# ---------------------------------------------------------------------------


def test_oversized_skill_is_refused_before_it_is_read(tmp_path: Path) -> None:
    skill = _write_bytes(tmp_path / "SKILL.md", MAX_SKILL_BYTES + 1)
    with pytest.raises(ParseError) as exc:
        parse(skill)
    assert "SKILL.md" in str(exc.value)
    assert "over the" in str(exc.value)


def test_normal_skill_still_parses(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: demo\ndescription: A demo skill.\n---\n\nBody.\n", encoding="utf-8")
    assert parse(skill).frontmatter["name"] == "demo"


def test_oversized_ledger_is_refused(tmp_path: Path) -> None:
    ledger = _write_bytes(tmp_path / ".skillcheck-history.json", MAX_LEDGER_BYTES + 1)
    with pytest.raises(LedgerError) as exc:
        load_ledger(ledger)
    assert "Ledger" in str(exc.value)
    assert "over the" in str(exc.value)


def test_oversized_config_is_refused(tmp_path: Path) -> None:
    config = _write_bytes(tmp_path / "skillcheck.toml", MAX_CONFIG_BYTES + 1)
    with pytest.raises(ConfigError) as exc:
        load_config(config)
    assert "Config" in str(exc.value)
    assert "over the" in str(exc.value)


def test_normal_config_still_loads(tmp_path: Path) -> None:
    config = tmp_path / "skillcheck.toml"
    config.write_text('[frontmatter]\nextension_fields = ["x-team"]\n', encoding="utf-8")
    assert load_config(config).extension_fields == frozenset({"x-team"})


def test_missing_ledger_still_returns_none(tmp_path: Path) -> None:
    """The cap sits after the existence check, so absence is still not an error."""
    assert load_ledger(tmp_path / ".skillcheck-history.json") is None
