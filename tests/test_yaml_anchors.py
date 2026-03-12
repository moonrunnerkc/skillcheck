"""Tests for Fix 6: YAML anchor/alias detection in frontmatter."""

import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.frontmatter import check_yaml_anchors


def test_anchor_and_alias_detected(tmp_path):
    """Using &anchor on name and *anchor on description triggers a warning."""
    content = (
        "---\n"
        "name: &name my-skill\n"
        "description: *name\n"
        "---\n"
        "Body text.\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_yaml_anchors(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.yaml-anchors"
    assert diagnostics[0].severity == Severity.WARNING
    assert "name" in diagnostics[0].message


def test_anchor_only_detected(tmp_path):
    """An anchor without an alias is still flagged (unused anchors are suspicious)."""
    content = (
        "---\n"
        "name: &anchor my-skill\n"
        "description: Validates something.\n"
        "---\n"
        "Body.\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_yaml_anchors(skill)
    assert len(diagnostics) == 1
    assert "anchor" in diagnostics[0].message


def test_no_anchors_passes(tmp_path):
    """Normal frontmatter without anchors produces no diagnostics."""
    content = (
        "---\n"
        "name: my-skill\n"
        "description: A normal description.\n"
        "---\n"
        "Body.\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_yaml_anchors(skill)
    assert diagnostics == []


def test_no_frontmatter_passes(tmp_path):
    """File without frontmatter produces no yaml-anchor diagnostics."""
    f = tmp_path / "SKILL.md"
    f.write_text("Just a body, no frontmatter.\n")
    skill = parse(f)
    diagnostics = check_yaml_anchors(skill)
    assert diagnostics == []


def test_alias_in_body_not_flagged(tmp_path):
    """A '*' in the body (e.g. markdown list) should NOT trigger."""
    content = (
        "---\n"
        "name: my-skill\n"
        "description: No anchors here.\n"
        "---\n"
        "* item one\n"
        "* item two\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_yaml_anchors(skill)
    assert diagnostics == []
