"""Tests for Feature 1: Full name spec compliance additions.

Covers leading/trailing hyphens, consecutive hyphens, and directory-name matching.
"""

import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.frontmatter import (
    check_name_consecutive_hyphens,
    check_name_directory_match,
    check_name_leading_trailing_hyphen,
)
from tests.conftest import FIXTURES_DIR


# ---------------------------------------------------------------------------
# name.leading-trailing-hyphen
# ---------------------------------------------------------------------------

def test_rejects_leading_hyphen():
    skill = parse(FIXTURES_DIR / "bad_name_leading_hyphen.md")
    diagnostics = check_name_leading_trailing_hyphen(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.leading-trailing-hyphen"
    assert diagnostics[0].severity == Severity.ERROR
    assert "starts with a hyphen" in diagnostics[0].message


def test_rejects_trailing_hyphen():
    skill = parse(FIXTURES_DIR / "bad_name_trailing_hyphen.md")
    diagnostics = check_name_leading_trailing_hyphen(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.leading-trailing-hyphen"
    assert diagnostics[0].severity == Severity.ERROR
    assert "ends with a hyphen" in diagnostics[0].message


def test_rejects_both_leading_and_trailing_hyphen(tmp_path):
    content = "---\nname: -both-hyphens-\ndescription: Both ends.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_name_leading_trailing_hyphen(skill)
    assert len(diagnostics) == 1
    assert "starts with a hyphen" in diagnostics[0].message
    assert "ends with a hyphen" in diagnostics[0].message


def test_accepts_valid_name_no_edge_hyphens():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_name_leading_trailing_hyphen(skill) == []


def test_leading_trailing_skips_missing_name(tmp_path):
    content = "---\ndescription: No name.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    assert check_name_leading_trailing_hyphen(skill) == []


# ---------------------------------------------------------------------------
# name.consecutive-hyphens
# ---------------------------------------------------------------------------

def test_rejects_consecutive_hyphens():
    skill = parse(FIXTURES_DIR / "bad_name_consecutive_hyphens.md")
    diagnostics = check_name_consecutive_hyphens(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.consecutive-hyphens"
    assert diagnostics[0].severity == Severity.ERROR
    assert "consecutive hyphens" in diagnostics[0].message


def test_accepts_single_hyphens():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_name_consecutive_hyphens(skill) == []


def test_consecutive_skips_missing_name(tmp_path):
    content = "---\ndescription: No name.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    assert check_name_consecutive_hyphens(skill) == []


# ---------------------------------------------------------------------------
# name.directory-mismatch
# ---------------------------------------------------------------------------

def test_directory_mismatch_fires_when_different(tmp_path):
    skill_dir = tmp_path / "wrong-dir"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Mismatched dir.\n---\n")
    skill = parse(f)
    diagnostics = check_name_directory_match(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.directory-mismatch"
    assert diagnostics[0].severity == Severity.ERROR
    assert "wrong-dir" in diagnostics[0].message
    assert "my-skill" in diagnostics[0].message


def test_directory_match_passes_when_matching(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Matching dir.\n---\n")
    skill = parse(f)
    assert check_name_directory_match(skill) == []


def test_directory_match_skips_missing_name(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\ndescription: No name.\n---\n")
    skill = parse(f)
    assert check_name_directory_match(skill) == []
