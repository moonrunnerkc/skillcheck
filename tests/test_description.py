"""Tests for Feature 2: Description quality scoring."""

import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.description import (
    check_description_quality,
    make_min_score_rule,
    score_description,
)
from tests.conftest import FIXTURES_DIR


# ---------------------------------------------------------------------------
# score_description: scoring ranges
# ---------------------------------------------------------------------------

def test_high_quality_description_scores_above_60():
    desc = (
        "Generates conventional commit messages from staged git diffs, "
        "enforcing semantic versioning conventions. Use this skill whenever "
        "the user needs a commit message, mentions conventional commits, "
        "or has staged changes ready to commit."
    )
    score, suggestions = score_description(desc)
    assert score >= 60, f"Expected >= 60, got {score}. Suggestions: {suggestions}"


def test_low_quality_description_scores_below_40():
    desc = "A thing."
    score, suggestions = score_description(desc)
    assert score < 40, f"Expected < 40, got {score}"
    assert len(suggestions) > 0


def test_empty_description_scores_zero():
    score, suggestions = score_description("")
    assert score == 0


def test_vague_description_penalized():
    desc = "A helpful tool and general utility for various things."
    score, _ = score_description(desc)
    # This is vague and should score poorly
    assert score < 40


def test_action_verb_at_start_boosts_score():
    desc = "Validates SKILL.md files against the agentskills.io specification."
    score_with_verb, _ = score_description(desc)
    desc_no_verb = "A checker for SKILL.md files and specification compliance."
    score_no_verb, _ = score_description(desc_no_verb)
    assert score_with_verb > score_no_verb


def test_trigger_phrase_boosts_score():
    base = "Generates commit messages from git diffs."
    with_trigger = base + " Use this skill whenever the user mentions commits."
    score_base, _ = score_description(base)
    score_trigger, _ = score_description(with_trigger)
    assert score_trigger > score_base


def test_very_short_description_penalized():
    desc = "Lints files."
    score, suggestions = score_description(desc)
    # 11 chars, should get length penalty
    assert any("short" in s.lower() for s in suggestions)


def test_very_long_description_penalized():
    desc = "Deploys applications to production. " * 20  # ~700 chars
    score, suggestions = score_description(desc)
    assert any("long" in s.lower() for s in suggestions)


# ---------------------------------------------------------------------------
# check_description_quality: rule integration
# ---------------------------------------------------------------------------

def test_quality_rule_returns_info_diagnostic():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    diagnostics = check_description_quality(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "description.quality-score"
    assert diagnostics[0].severity == Severity.INFO
    assert "/100" in diagnostics[0].message


def test_quality_rule_skips_missing_description(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: no-desc\n---\nBody.\n")
    skill = parse(f)
    assert check_description_quality(skill) == []


def test_quality_rule_skips_empty_description(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: empty-desc\ndescription:\n---\nBody.\n")
    skill = parse(f)
    assert check_description_quality(skill) == []


# ---------------------------------------------------------------------------
# make_min_score_rule
# ---------------------------------------------------------------------------

def test_min_score_rule_warns_below_threshold():
    rule = make_min_score_rule(80)
    skill = parse(FIXTURES_DIR / "bad_desc_quality.md")
    diagnostics = rule(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "description.min-score"
    assert diagnostics[0].severity == Severity.WARNING
    assert "80" in diagnostics[0].message


def test_min_score_rule_passes_above_threshold():
    rule = make_min_score_rule(10)
    skill = parse(FIXTURES_DIR / "valid_good_desc.md")
    diagnostics = rule(skill)
    assert diagnostics == []


def test_min_score_rule_skips_missing_description(tmp_path):
    rule = make_min_score_rule(50)
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: no-desc\n---\nBody.\n")
    skill = parse(f)
    assert rule(skill) == []
