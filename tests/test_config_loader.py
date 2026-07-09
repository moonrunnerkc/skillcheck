"""Tests for skillcheck.toml discovery and parsing (config_loader)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from skillcheck.config_loader import (
    ConfigError,
    _parse_without_tomllib,
    _strip_inline_comment,
    find_config,
    load_config,
)
from tests.conftest import CLI_AVAILABLE, SKILLCHECK_CMD


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_int_type_error_includes_offending_value(tmp_path: Path) -> None:
    cfg = _write(tmp_path / "skillcheck.toml", 'max-lines = "nope"\n')
    with pytest.raises(ConfigError, match=r"must be an integer \(got 'nope'\)"):
        load_config(cfg)


def test_bool_type_error_includes_offending_value(tmp_path: Path) -> None:
    cfg = _write(tmp_path / "skillcheck.toml", 'strict-vscode = "yes"\n')
    with pytest.raises(ConfigError, match=r"must be true or false \(got 'yes'\)"):
        load_config(cfg)


def test_str_type_error_includes_offending_value(tmp_path: Path) -> None:
    cfg = _write(tmp_path / "skillcheck.toml", "format = 5\n")
    with pytest.raises(ConfigError, match=r"must be a string \(got 5\)"):
        load_config(cfg)


def test_strip_inline_comment_respects_quotes() -> None:
    assert _strip_inline_comment('format = "a#b"  # trailing') == 'format = "a#b"  '
    assert _strip_inline_comment("# whole line") == ""
    assert _strip_inline_comment("bare = value") == "bare = value"


def test_fallback_parser_keeps_hash_inside_quotes() -> None:
    parsed = _parse_without_tomllib('format = "a#b"  # comment\n')
    assert parsed == {"format": "a#b"}


def test_find_config_stops_at_git_root(tmp_path: Path) -> None:
    # A config above the repo root must not be discovered from inside the repo.
    _write(tmp_path / "skillcheck.toml", "max-lines = 10\n")
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    assert find_config(nested / "SKILL.md") is None


def test_find_config_finds_config_at_git_root(tmp_path: Path) -> None:
    # A config at the repo root (alongside .git) is still found.
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    cfg = _write(repo / "skillcheck.toml", "max-lines = 10\n")
    nested = repo / "a"
    nested.mkdir()
    assert find_config(nested / "SKILL.md") == cfg


@pytest.mark.skipif(not CLI_AVAILABLE, reason="skillcheck not installed")
def test_cli_reports_loaded_config_path(tmp_path: Path) -> None:
    skill_dir = tmp_path / "cfg-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: cfg-skill\ndescription: Validates that the loaded config path is reported to stderr.\n---\nBody.\n",
        encoding="utf-8",
    )
    cfg = _write(skill_dir / "skillcheck.toml", "max-lines = 900\n")
    result = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", str(skill_dir / "SKILL.md")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert f"Loaded config from {cfg}" in result.stderr
