"""Tests for --explain-score: per-dimension description quality breakdown."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from skillcheck.parser import parse as _parse
from skillcheck.rules.description import score_description

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Unit tests: score_description returns 3-tuple with breakdown
# ---------------------------------------------------------------------------


def test_full_credit_description():
    """A high-quality description should give a breakdown with mostly max values."""
    desc = (
        "Generates conventional commit messages from staged git diffs, "
        "enforcing semantic versioning conventions. Use this skill whenever "
        "the user needs a commit message, mentions conventional commits, "
        "or has staged changes ready to commit."
    )
    score, suggestions, breakdown = score_description(desc)
    assert score >= 85, f"Expected score >= 85, got {score}"
    assert "action" in breakdown
    assert "trigger" in breakdown
    assert "keywords" in breakdown
    assert "specificity" in breakdown
    assert "length" in breakdown
    assert breakdown["action"] in (20, 25), f"Expected action 20 or 25, got {breakdown['action']}"
    assert breakdown["trigger"] >= 20  # at least one trigger phrase
    # Verify breakdown sums to score
    assert sum(breakdown.values()) == score


def test_zero_credit_description():
    """An empty description should give all-zero breakdown."""
    desc = ""
    score, suggestions, breakdown = score_description(desc)
    assert score == 0
    assert breakdown["action"] == 0
    assert breakdown["trigger"] == 0
    assert breakdown["keywords"] == 0
    assert breakdown["specificity"] == 0
    assert breakdown["length"] == 0
    assert sum(breakdown.values()) == score


def test_mid_range_description():
    """A description with some but not all qualities should produce mid-range scores."""
    desc = "Validates files against a specification."
    score, suggestions, breakdown = score_description(desc)
    # Has action verb at start but no triggers, short length
    assert 0 < score < 100
    assert breakdown["action"] >= 10  # has leading verb
    assert breakdown["trigger"] == 0  # no trigger phrases
    assert sum(breakdown.values()) == score


# ---------------------------------------------------------------------------
# CLI integration: --format json always includes breakdown
# ---------------------------------------------------------------------------


def test_json_breakdown_present():
    """JSON output should include 'breakdown' for description.quality-score diagnostics."""
    skill_file = FIXTURES_DIR / "valid_good_desc.md"
    result = subprocess.run(
        [sys.executable, "-m", "skillcheck", str(skill_file), "--format", "json"],
        capture_output=True,
        text=True,
        cwd=str(FIXTURES_DIR.parent.parent),
    )
    assert result.returncode in (0, 1), f"Exit code {result.returncode}, stderr: {result.stderr}"
    data = json.loads(result.stdout)
    # Find description.quality-score diagnostics
    for file_result in data["results"]:
        for diag in file_result["diagnostics"]:
            if diag["rule"] == "description.quality-score":
                assert "breakdown" in diag, (
                    f"JSON diagnostic for description.quality-score should include 'breakdown', "
                    f"got keys: {list(diag.keys())}"
                )
                bd = diag["breakdown"]
                assert "action" in bd
                assert "trigger" in bd
                assert "keywords" in bd
                assert "specificity" in bd
                assert "length" in bd
                return
    pytest.skip("No description.quality-score diagnostic found in output")


# ---------------------------------------------------------------------------
# CLI integration: text format with/without --explain-score
# ---------------------------------------------------------------------------


def test_text_flag_off_suppresses_breakdown():
    """Without --explain-score, text output should NOT show breakdown dimension lines."""
    skill_file = FIXTURES_DIR / "valid_good_desc.md"
    result = subprocess.run(
        [sys.executable, "-m", "skillcheck", str(skill_file)],
        capture_output=True,
        text=True,
        cwd=str(FIXTURES_DIR.parent.parent),
    )
    assert result.returncode in (0, 1)
    output = result.stdout
    # Should contain the quality-score diagnostic
    assert "description.quality-score" in output
    # Should NOT contain a breakdown line like "action: 25/25"
    # (the colon-space pattern with "/25" is unique to breakdown lines)
    assert "/25" not in output, (
        f"Breakdown dimensions should not appear without --explain-score. Got: {output}"
    )


def test_text_explain_score_shows_breakdown():
    """With --explain-score, text output should show the per-dimension breakdown."""
    skill_file = FIXTURES_DIR / "valid_good_desc.md"
    result = subprocess.run(
        [sys.executable, "-m", "skillcheck", str(skill_file), "--explain-score"],
        capture_output=True,
        text=True,
        cwd=str(FIXTURES_DIR.parent.parent),
    )
    assert result.returncode in (0, 1)
    output = result.stdout
    # Should contain dimension breakdown with /25, /15, /10 patterns
    assert "action:" in output
    assert "/25" in output