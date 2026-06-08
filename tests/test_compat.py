"""Tests for Feature 5: Cross-agent compatibility warnings."""

import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules import get_rules
from skillcheck.rules.compat import (
    check_claude_only_fields,
    check_cursor_description_block_scalar,
    check_cursor_description_block_scalar_warning,
    check_unverified_fields,
    check_vscode_dirname,
    make_strict_cursor_rule,
    make_strict_vscode_rule,
)
from tests.conftest import FIXTURES_DIR

# ---------------------------------------------------------------------------
# compat.claude-only
# ---------------------------------------------------------------------------

def test_claude_only_flags_model_field():
    skill = parse(FIXTURES_DIR / "claude_only_fields.md")
    diagnostics = check_claude_only_fields(skill)
    rules = [d.rule for d in diagnostics]
    assert "compat.claude-only" in rules
    messages = " ".join(d.message for d in diagnostics)
    assert "model" in messages


def test_claude_only_flags_multiple_fields():
    skill = parse(FIXTURES_DIR / "claude_only_fields.md")
    diagnostics = check_claude_only_fields(skill)
    # model, disable-model-invocation, hooks, mode are all Claude-only
    assert len(diagnostics) >= 3
    flagged_fields = set()
    for d in diagnostics:
        for field in ("model", "disable-model-invocation", "hooks", "mode"):
            if field in d.message:
                flagged_fields.add(field)
    assert "model" in flagged_fields
    assert "mode" in flagged_fields


def test_claude_only_passes_for_universal_fields():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    diagnostics = check_claude_only_fields(skill)
    assert diagnostics == []


def test_claude_only_severity_is_info():
    skill = parse(FIXTURES_DIR / "claude_only_fields.md")
    diagnostics = check_claude_only_fields(skill)
    assert all(d.severity == Severity.INFO for d in diagnostics)


# ---------------------------------------------------------------------------
# compat.vscode-dirname
# ---------------------------------------------------------------------------

def test_vscode_dirname_flags_mismatch(tmp_path):
    skill_dir = tmp_path / "wrong-dir"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Mismatch test.\n---\n")
    skill = parse(f)
    diagnostics = check_vscode_dirname(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "compat.vscode-dirname"
    assert diagnostics[0].severity == Severity.INFO
    assert "VS Code" in diagnostics[0].message


def test_vscode_dirname_passes_when_matching(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Match test.\n---\n")
    skill = parse(f)
    assert check_vscode_dirname(skill) == []


def test_vscode_dirname_skips_missing_name(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\ndescription: No name.\n---\n")
    skill = parse(f)
    assert check_vscode_dirname(skill) == []


# ---------------------------------------------------------------------------
# compat.unverified
# ---------------------------------------------------------------------------

def test_unverified_flags_fields_with_unknown_agents():
    skill = parse(FIXTURES_DIR / "claude_only_fields.md")
    diagnostics = check_unverified_fields(skill)
    assert len(diagnostics) > 0
    assert all(d.rule == "compat.unverified" for d in diagnostics)
    assert all(d.severity == Severity.INFO for d in diagnostics)
    # At least model and hooks should have unknown agents
    messages = " ".join(d.message for d in diagnostics)
    assert "unverified" in messages.lower()


def test_unverified_passes_for_universal_only_fields(tmp_path):
    # name and description are supported everywhere
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: universal\ndescription: Universal fields.\n---\n")
    skill = parse(f)
    diagnostics = check_unverified_fields(skill)
    # name and description have no "unknown" entries
    assert diagnostics == []


# ---------------------------------------------------------------------------
# make_strict_vscode_rule
# ---------------------------------------------------------------------------

def test_strict_vscode_errors_on_mismatch(tmp_path):
    skill_dir = tmp_path / "wrong-dir"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Strict test.\n---\n")
    skill = parse(f)
    rule = make_strict_vscode_rule()
    diagnostics = rule(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == Severity.ERROR
    assert diagnostics[0].rule == "compat.vscode-dirname"


def test_strict_vscode_passes_when_matching(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Strict match.\n---\n")
    skill = parse(f)
    rule = make_strict_vscode_rule()
    assert rule(skill) == []


# ---------------------------------------------------------------------------
# Duplicate diagnostic prevention & target_agent validation
# ---------------------------------------------------------------------------

def test_strict_vscode_all_emits_single_dirname_diagnostic(tmp_path):
    """strict_vscode + target_agent='all' should emit exactly one dirname
    diagnostic (ERROR), not both INFO and ERROR."""
    skill_dir = tmp_path / "wrong-dir"
    skill_dir.mkdir()
    f = skill_dir / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: Dup test.\n---\n")
    skill = parse(f)
    rules = get_rules(strict_vscode=True, target_agent="all")
    diagnostics = [d for rule in rules for d in rule(skill)]
    dirname_diags = [d for d in diagnostics if d.rule == "compat.vscode-dirname"]
    assert len(dirname_diags) == 1
    assert dirname_diags[0].severity == Severity.ERROR


def test_invalid_target_agent_raises():
    """An invalid target_agent should raise ValueError, not silently skip rules."""
    with pytest.raises(ValueError, match="Unknown target_agent"):
        get_rules(target_agent="vim")


# ---------------------------------------------------------------------------
# compat.cursor-description-block-scalar (issue #1)
# ---------------------------------------------------------------------------

_RULE_ID = "compat.cursor-description-block-scalar"


def test_cursor_block_scalar_flags_folded_keep():
    skill = parse(FIXTURES_DIR / "cursor_desc_folded_keep.md")
    diagnostics = check_cursor_description_block_scalar(skill)
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.rule == _RULE_ID
    assert d.severity == Severity.INFO
    assert "'>'" in d.message
    assert ">-" in d.message


def test_cursor_block_scalar_flags_literal():
    skill = parse(FIXTURES_DIR / "cursor_desc_literal.md")
    diagnostics = check_cursor_description_block_scalar(skill)
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.rule == _RULE_ID
    assert d.severity == Severity.INFO
    assert "'|'" in d.message
    assert ">-" in d.message


def test_cursor_block_scalar_passes_folded_strip():
    skill = parse(FIXTURES_DIR / "cursor_desc_folded_strip.md")
    assert check_cursor_description_block_scalar(skill) == []


def test_cursor_block_scalar_passes_literal_strip(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text(
        "---\nname: a\ndescription: |-\n  Strip variant.\n---\nbody\n"
    )
    skill = parse(f)
    assert check_cursor_description_block_scalar(skill) == []


def test_cursor_block_scalar_passes_inline_string(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text(
        "---\nname: a\ndescription: A plain inline string.\n---\nbody\n"
    )
    skill = parse(f)
    assert check_cursor_description_block_scalar(skill) == []


def test_cursor_block_scalar_passes_folded_keep_explicit(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text(
        "---\nname: a\ndescription: >+\n  Plus keep variant.\n---\nbody\n"
    )
    skill = parse(f)
    diagnostics = check_cursor_description_block_scalar(skill)
    assert len(diagnostics) == 1
    assert "'>+'" in diagnostics[0].message


def test_cursor_block_scalar_target_cursor_promotes_to_warning():
    skill = parse(FIXTURES_DIR / "cursor_desc_folded_keep.md")
    diagnostics = check_cursor_description_block_scalar_warning(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == Severity.WARNING
    assert diagnostics[0].rule == _RULE_ID


def test_cursor_block_scalar_strict_cursor_promotes_to_error():
    skill = parse(FIXTURES_DIR / "cursor_desc_folded_keep.md")
    rule = make_strict_cursor_rule()
    diagnostics = rule(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == Severity.ERROR
    assert diagnostics[0].rule == _RULE_ID


def test_cursor_block_scalar_default_severity_is_info():
    """Default severity (no flag) is INFO."""
    skill = parse(FIXTURES_DIR / "cursor_desc_folded_keep.md")
    rules = get_rules(target_agent="all")
    diagnostics = [d for r in rules for d in r(skill) if d.rule == _RULE_ID]
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == Severity.INFO


def test_cursor_block_scalar_target_cursor_emits_single_warning():
    skill = parse(FIXTURES_DIR / "cursor_desc_folded_keep.md")
    rules = get_rules(target_agent="cursor")
    diagnostics = [d for r in rules for d in r(skill) if d.rule == _RULE_ID]
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == Severity.WARNING


def test_cursor_block_scalar_strict_cursor_replaces_info():
    """strict_cursor + target_agent='all' should emit one ERROR, not duplicates."""
    skill = parse(FIXTURES_DIR / "cursor_desc_folded_keep.md")
    rules = get_rules(strict_cursor=True, target_agent="all")
    diagnostics = [d for r in rules for d in r(skill) if d.rule == _RULE_ID]
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == Severity.ERROR


def test_cursor_block_scalar_strict_cursor_target_cursor():
    """strict_cursor with target_agent='cursor' should also produce one ERROR."""
    skill = parse(FIXTURES_DIR / "cursor_desc_folded_keep.md")
    rules = get_rules(strict_cursor=True, target_agent="cursor")
    diagnostics = [d for r in rules for d in r(skill) if d.rule == _RULE_ID]
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == Severity.ERROR


def test_cursor_target_agent_accepts_cursor():
    """target_agent='cursor' must not raise."""
    rules = get_rules(target_agent="cursor")
    assert len(rules) > 0
