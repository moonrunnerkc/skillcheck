import json
import shutil
import subprocess
import sys

import pytest

from tests.conftest import FIXTURES_DIR

# Skip all CLI tests if the package is not installed as a command.
pytestmark = pytest.mark.skipif(
    shutil.which("skillcheck") is None,
    reason="skillcheck not installed; run `pip install -e .` first",
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["skillcheck", *args],
        capture_output=True,
        text=True,
    )


def run_fixture(*args: str) -> subprocess.CompletedProcess:
    """Run skillcheck with --skip-dirname-check for fixture files."""
    return subprocess.run(
        ["skillcheck", "--skip-dirname-check", *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

def test_valid_file_exits_zero():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"))
    assert result.returncode == 0


def test_invalid_file_exits_one():
    result = run(str(FIXTURES_DIR / "bad_name_caps.md"))
    assert result.returncode == 1


def test_missing_file_exits_two():
    result = run("/nonexistent/path/SKILL.md")
    assert result.returncode == 2


def test_empty_directory_exits_two(tmp_path):
    result = run(str(tmp_path))
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Text output
# ---------------------------------------------------------------------------

def test_text_output_is_default():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"))
    assert "PASS" in result.stdout


def test_text_output_shows_fail_for_invalid_file():
    result = run(str(FIXTURES_DIR / "bad_name_caps.md"))
    assert "FAIL" in result.stdout


def test_text_output_shows_rule_id_and_message():
    result = run(str(FIXTURES_DIR / "bad_name_caps.md"))
    assert "frontmatter.name.invalid-chars" in result.stdout
    assert "PDF-Processing" in result.stdout


def test_text_output_includes_summary_line():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"))
    assert "Checked" in result.stdout and "passed" in result.stdout


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def test_json_output_is_valid_json():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "version" in data
    assert "files_checked" in data
    assert "results" in data


def test_json_output_schema_for_valid_file():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--format", "json")
    data = json.loads(result.stdout)
    assert data["files_checked"] == 1
    assert data["files_passed"] == 1
    assert data["files_failed"] == 0
    assert data["results"][0]["valid"] is True


def test_json_output_schema_for_invalid_file():
    result = run(str(FIXTURES_DIR / "bad_name_caps.md"), "--format", "json")
    data = json.loads(result.stdout)
    assert data["files_failed"] == 1
    diagnostic = data["results"][0]["diagnostics"][0]
    assert diagnostic["rule"] == "frontmatter.name.invalid-chars"
    assert diagnostic["severity"] == "error"
    assert "line" in diagnostic
    assert "context" in diagnostic


# ---------------------------------------------------------------------------
# Directory mode
# ---------------------------------------------------------------------------

def test_directory_mode_finds_skill_files(tmp_path):
    # Create two SKILL.md files in subdirectories with matching names.
    (tmp_path / "skill-a").mkdir()
    (tmp_path / "skill-b").mkdir()
    (tmp_path / "skill-a" / "SKILL.md").write_text(
        "---\nname: skill-a\ndescription: Skill A for testing.\n---\nBody.\n"
    )
    (tmp_path / "skill-b" / "SKILL.md").write_text(
        "---\nname: skill-b\ndescription: Skill B for testing.\n---\nBody.\n"
    )
    result = run(str(tmp_path), "--format", "json")
    data = json.loads(result.stdout)
    assert data["files_checked"] == 2
    assert data["files_passed"] == 2


def test_directory_mode_ignores_non_skill_md_files(tmp_path):
    (tmp_path / "README.md").write_text("Just a readme.")
    (tmp_path / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: My skill.\n---\nBody.\n"
    )
    result = run(str(tmp_path), "--format", "json")
    data = json.loads(result.stdout)
    assert data["files_checked"] == 1


# ---------------------------------------------------------------------------
# Threshold overrides
# ---------------------------------------------------------------------------

def test_max_lines_override_triggers_warning():
    # valid_basic.md is short; override threshold to 1 so it always warns.
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--max-lines", "1")
    assert "sizing.body.line-count" in result.stdout
    # Warnings do not cause a non-zero exit.
    assert result.returncode == 0


def test_max_tokens_override_triggers_warning():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--max-tokens", "1")
    assert "sizing.body.token-estimate" in result.stdout
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Ignore prefix
# ---------------------------------------------------------------------------

def test_ignore_prefix_suppresses_matching_rules():
    result = run(
        str(FIXTURES_DIR / "bad_name_caps.md"),
        "--ignore", "frontmatter.name",
    )
    # With the name rules suppressed, the only remaining error (if any) is description.
    # bad_name_caps.md has a valid description, so this should exit 0.
    assert result.returncode == 0


def test_ignore_prefix_does_not_suppress_unrelated_rules():
    result = run(
        str(FIXTURES_DIR / "bad_name_caps.md"),
        "--ignore", "sizing",
    )
    # Name error still present; should still exit 1.
    assert result.returncode == 1


# ---------------------------------------------------------------------------
# Version flag
# ---------------------------------------------------------------------------

def test_version_flag_shows_version():
    result = run("--version")
    assert result.returncode == 0
    assert "0.2.0" in result.stdout


# ---------------------------------------------------------------------------
# New output features
# ---------------------------------------------------------------------------

def test_pass_shows_checkmark_symbol():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"))
    assert "✔ PASS" in result.stdout


def test_fail_shows_cross_symbol():
    result = run(str(FIXTURES_DIR / "bad_name_caps.md"))
    assert "✗ FAIL" in result.stdout


def test_warning_severity_shown_in_diagnostics():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--max-lines", "1")
    assert "warning" in result.stdout.lower()
    assert "⚠" in result.stdout


def test_summary_includes_warning_count():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--max-lines", "1")
    assert "warning" in result.stdout.split("Checked")[-1]


def test_no_color_flag_accepted():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--no-color")
    assert result.returncode == 0
    assert "\033[" not in result.stdout


def test_help_shows_examples():
    result = run("--help")
    assert "examples:" in result.stdout
    assert "--format json" in result.stdout


# ---------------------------------------------------------------------------
# Quiet flag
# ---------------------------------------------------------------------------

def test_quiet_flag_suppresses_output_valid():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--quiet")
    assert result.returncode == 0
    assert result.stdout == ""


def test_quiet_flag_short_form():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "-q")
    assert result.returncode == 0
    assert result.stdout == ""


def test_quiet_flag_still_fails_with_exit_code():
    result = run(str(FIXTURES_DIR / "bad_name_caps.md"), "--quiet")
    assert result.returncode == 1
    assert result.stdout == ""


def test_quiet_flag_with_json_format():
    result = run_fixture(str(FIXTURES_DIR / "valid_basic.md"), "--quiet", "--format", "json")
    assert result.returncode == 0
    assert result.stdout == ""
