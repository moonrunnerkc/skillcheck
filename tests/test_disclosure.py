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
    # Real base64 has mixed upper/lower characters.
    import base64
    b64 = base64.b64encode(b"\x00" * 80).decode()  # 108 chars, mixed case? No...
    # Manually craft realistic base64 (like an embedded image):
    b64 = "SGVsbG8gV29ybGQhIFRoaXMgaXMgYSByZWFsbHkgbG9uZyBiYXNlNjQgc3RyaW5nIHRoYXQgc2hvdWxkIGJlIGRldGVjdGVkIGJ5IHRoZSBibG9hdCBjaGVjaw=="
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


# ---------------------------------------------------------------------------
# base64 false-positive hardening
# ---------------------------------------------------------------------------

def test_base64_rejects_repeated_single_char(tmp_path):
    """64+ repeated 'a' chars should NOT trigger base64 detection."""
    body_str = "a" * 100
    content = (
        "---\nname: b64-repeat\ndescription: Repeated char test.\n---\n"
        f"\n{body_str}\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_body_bloat(skill)
    assert not any("base64" in d.message.lower() for d in diagnostics)


def test_base64_rejects_hex_hash(tmp_path):
    """A SHA-256 hex hash (all lowercase a-f + digits) should NOT trigger."""
    hex_hash = "a" * 32 + "0123456789abcdef" * 3  # 80 chars, lowercase hex-like
    content = (
        "---\nname: b64-hex\ndescription: Hex hash test.\n---\n"
        f"\ncommit: {hex_hash}\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_body_bloat(skill)
    assert not any("base64" in d.message.lower() for d in diagnostics)


def test_base64_rejects_all_uppercase(tmp_path):
    """64+ uppercase-only chars should NOT trigger base64 detection."""
    content = (
        "---\nname: b64-upper\ndescription: All-upper test.\n---\n"
        f"\n{'A' * 100}==\n"
    )
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_body_bloat(skill)
    assert not any("base64" in d.message.lower() for d in diagnostics)
