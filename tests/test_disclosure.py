"""Tests for Feature 4: Progressive disclosure budget validation."""

import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.disclosure import (
    check_body_bloat,
    check_body_budget,
    check_metadata_budget,
)
from tests.conftest import FIXTURES_DIR


# ---------------------------------------------------------------------------
# disclosure.metadata-budget
# ---------------------------------------------------------------------------

def test_metadata_budget_warns_for_large_frontmatter(tmp_path):
    # Build frontmatter with many fields to exceed ~100 tokens.
    fields = "\n".join(f"field-{i}: {'value ' * 10}" for i in range(30))
    content = f"---\nname: big-meta\ndescription: Large metadata.\n{fields}\n---\nBody.\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_metadata_budget(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "disclosure.metadata-budget"
    assert diagnostics[0].severity == Severity.WARNING


def test_metadata_budget_passes_for_small_frontmatter():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_metadata_budget(skill) == []


def test_metadata_budget_handles_no_frontmatter():
    skill = parse(FIXTURES_DIR / "bad_no_frontmatter.md")
    assert check_metadata_budget(skill) == []


# ---------------------------------------------------------------------------
# disclosure.body-budget
# ---------------------------------------------------------------------------

def test_body_budget_warns_for_large_body(tmp_path):
    # Build a body that exceeds 5000 tokens (~6500 words).
    body_lines = ["This is a content line with several words in it."] * 1500
    content = "---\nname: big-body\ndescription: Large body.\n---\n" + "\n".join(body_lines) + "\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_body_budget(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "disclosure.body-budget"
    assert diagnostics[0].severity == Severity.WARNING
    assert "5000" in diagnostics[0].message


def test_body_budget_passes_for_small_body():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_body_budget(skill) == []


def test_body_budget_handles_empty_body(tmp_path):
    content = "---\nname: empty-body\ndescription: No body.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    assert check_body_budget(skill) == []


# ---------------------------------------------------------------------------
# disclosure.body-bloat
# ---------------------------------------------------------------------------

def test_body_bloat_flags_large_code_block(tmp_path):
    code_lines = "\n".join(f"    line {i}" for i in range(60))
    content = (
        "---\nname: bloat-code\ndescription: Code bloat test.\n---\n"
        f"\n```python\n{code_lines}\n```\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_body_bloat(skill)
    assert any(d.rule == "disclosure.body-bloat" for d in diagnostics)
    assert any("code block" in d.message.lower() for d in diagnostics)


def test_body_bloat_flags_large_table(tmp_path):
    header = "| Col A | Col B |"
    separator = "|---|---|"
    rows = "\n".join(f"| val-{i} | data-{i} |" for i in range(25))
    content = (
        "---\nname: bloat-table\ndescription: Table bloat test.\n---\n"
        f"\n{header}\n{separator}\n{rows}\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_body_bloat(skill)
    assert any(d.rule == "disclosure.body-bloat" for d in diagnostics)
    assert any("table" in d.message.lower() for d in diagnostics)


def test_body_bloat_flags_base64(tmp_path):
    # A long base64-like string
    b64 = "A" * 100 + "=="
    content = (
        "---\nname: bloat-b64\ndescription: Base64 bloat test.\n---\n"
        f"\nEmbedded data: {b64}\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_body_bloat(skill)
    assert any(d.rule == "disclosure.body-bloat" for d in diagnostics)
    assert any("base64" in d.message.lower() for d in diagnostics)


def test_body_bloat_passes_for_clean_body():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_body_bloat(skill) == []


def test_body_bloat_handles_empty_body(tmp_path):
    content = "---\nname: empty\ndescription: No body.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    assert check_body_bloat(skill) == []
