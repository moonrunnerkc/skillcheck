"""Tests for Feature 3: File reference validation."""

import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.references import (
    _extract_references,
    _reference_depth,
    check_broken_references,
    check_reference_depth,
)
from tests.conftest import FIXTURES_DIR


# ---------------------------------------------------------------------------
# _extract_references
# ---------------------------------------------------------------------------

def test_extracts_markdown_links():
    body = "See [config](config.yaml) and [docs](docs/setup.md)."
    refs = _extract_references(body)
    assert "config.yaml" in refs
    assert "docs/setup.md" in refs


def test_extracts_image_links():
    body = "![diagram](images/arch.png)"
    refs = _extract_references(body)
    assert "images/arch.png" in refs


def test_ignores_urls():
    body = "See [docs](https://example.com/docs) and [local](file.txt)."
    refs = _extract_references(body)
    assert "file.txt" in refs
    assert "https://example.com/docs" not in refs


def test_extracts_directive_references():
    body = "source: scripts/deploy.sh\nfile: config.yaml"
    refs = _extract_references(body)
    assert "scripts/deploy.sh" in refs
    assert "config.yaml" in refs


def test_deduplicates_references():
    body = "See [a](file.txt) and [b](file.txt)."
    refs = _extract_references(body)
    assert refs.count("file.txt") == 1


def test_empty_body_returns_no_refs():
    assert _extract_references("") == []


# ---------------------------------------------------------------------------
# _reference_depth
# ---------------------------------------------------------------------------

def test_depth_same_directory():
    assert _reference_depth("file.txt") == 0


def test_depth_one_level():
    assert _reference_depth("sub/file.txt") == 1


def test_depth_two_levels():
    assert _reference_depth("sub/deep/file.txt") == 2


def test_depth_parent_traversal():
    assert _reference_depth("../other/file.txt") == 2


# ---------------------------------------------------------------------------
# check_broken_references
# ---------------------------------------------------------------------------

def test_broken_ref_detected(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text(
        "---\nname: my-skill\ndescription: Ref test.\n---\n"
        "See [missing](does-not-exist.txt) for more.\n"
    )
    skill = parse(f)
    diagnostics = check_broken_references(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "references.broken-link"
    assert diagnostics[0].severity == Severity.ERROR
    assert "does-not-exist.txt" in diagnostics[0].message


def test_valid_ref_passes(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "config.yaml").write_text("key: value\n")
    f = skill_dir / "SKILL.md"
    f.write_text(
        "---\nname: my-skill\ndescription: Ref test.\n---\n"
        "See [config](config.yaml) for settings.\n"
    )
    skill = parse(f)
    diagnostics = check_broken_references(skill)
    assert diagnostics == []


def test_no_refs_passes(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: no-refs\ndescription: No refs.\n---\nBody.\n")
    skill = parse(f)
    assert check_broken_references(skill) == []


# ---------------------------------------------------------------------------
# check_reference_depth
# ---------------------------------------------------------------------------

def test_deep_ref_flagged(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text(
        "---\nname: my-skill\ndescription: Depth test.\n---\n"
        "See [deep](sub/deep/nested/file.txt) for more.\n"
    )
    skill = parse(f)
    diagnostics = check_reference_depth(skill)
    assert len(diagnostics) >= 1
    assert any(d.rule == "references.depth-exceeded" for d in diagnostics)


def test_parent_traversal_flagged(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text(
        "---\nname: my-skill\ndescription: Traversal test.\n---\n"
        "See [parent](../../other/file.py) for context.\n"
    )
    skill = parse(f)
    diagnostics = check_reference_depth(skill)
    assert len(diagnostics) >= 1
    assert any("traverses above" in d.message for d in diagnostics)


def test_shallow_ref_passes(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text(
        "---\nname: my-skill\ndescription: Shallow test.\n---\n"
        "See [local](resources/helper.sh) for helpers.\n"
    )
    skill = parse(f)
    diagnostics = check_reference_depth(skill)
    assert diagnostics == []


def test_no_refs_no_depth_issues(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: no-refs\ndescription: No refs.\n---\nBody.\n")
    skill = parse(f)
    assert check_reference_depth(skill) == []
