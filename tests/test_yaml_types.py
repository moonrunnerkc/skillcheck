"""Tests for YAML type coercion detection in frontmatter.

yaml.safe_load silently converts bare values:
  name: true    →  bool
  name: 123     →  int
  name: 1.5     →  float
  name: null    →  None

These produce confusing downstream errors.  The type check rules catch
them early with a clear fix (quote the value).
"""

import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.frontmatter import check_description_type, check_name_type


# ---------------------------------------------------------------------------
# frontmatter.name.type
# ---------------------------------------------------------------------------


def test_name_boolean_detected(tmp_path):
    """name: true → parsed as bool, should fire type error."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: true\ndescription: Boolean name.\n---\nBody.\n")
    skill = parse(f)
    diagnostics = check_name_type(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.type"
    assert diagnostics[0].severity == Severity.ERROR
    assert "bool" in diagnostics[0].message
    assert 'name: "True"' in diagnostics[0].message


def test_name_integer_detected(tmp_path):
    """name: 123 → parsed as int, should fire type error."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: 123\ndescription: Numeric name.\n---\nBody.\n")
    skill = parse(f)
    diagnostics = check_name_type(skill)
    assert len(diagnostics) == 1
    assert "int" in diagnostics[0].message


def test_name_float_detected(tmp_path):
    """name: 1.5 → parsed as float, should fire type error."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: 1.5\ndescription: Float name.\n---\nBody.\n")
    skill = parse(f)
    diagnostics = check_name_type(skill)
    assert len(diagnostics) == 1
    assert "float" in diagnostics[0].message


def test_name_string_passes(tmp_path):
    """name: my-skill → string, no type error."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Valid.\n---\nBody.\n")
    skill = parse(f)
    assert check_name_type(skill) == []


def test_name_none_skipped(tmp_path):
    """name absent → handled by check_name_required, not type check."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\ndescription: No name.\n---\nBody.\n")
    skill = parse(f)
    assert check_name_type(skill) == []


def test_name_quoted_true_passes(tmp_path):
    """name: "true" → stays as string, no type error."""
    f = tmp_path / "SKILL.md"
    f.write_text('---\nname: "true"\ndescription: Quoted boolean.\n---\nBody.\n')
    skill = parse(f)
    assert check_name_type(skill) == []


# ---------------------------------------------------------------------------
# frontmatter.description.type
# ---------------------------------------------------------------------------


def test_description_boolean_detected(tmp_path):
    """description: true → parsed as bool, should fire type error."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: true\n---\nBody.\n")
    skill = parse(f)
    diagnostics = check_description_type(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.description.type"
    assert diagnostics[0].severity == Severity.ERROR
    assert "bool" in diagnostics[0].message


def test_description_integer_detected(tmp_path):
    """description: 42 → parsed as int, should fire type error."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: 42\n---\nBody.\n")
    skill = parse(f)
    diagnostics = check_description_type(skill)
    assert len(diagnostics) == 1
    assert "int" in diagnostics[0].message


def test_description_string_passes(tmp_path):
    """description: Some text → string, no type error."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Validates things.\n---\nBody.\n")
    skill = parse(f)
    assert check_description_type(skill) == []


def test_description_none_skipped(tmp_path):
    """description absent → handled by check_description_required."""
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: my-skill\n---\nBody.\n")
    skill = parse(f)
    assert check_description_type(skill) == []
