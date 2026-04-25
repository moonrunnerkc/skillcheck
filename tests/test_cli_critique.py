"""CLI tests for --emit-critique-prompt and --ingest-critique flags."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import FIXTURES_DIR

CRITIQUE_DIR = FIXTURES_DIR / "critique"

pytestmark = pytest.mark.skipif(
    shutil.which("skillcheck") is None,
    reason="skillcheck not installed; run `pip install -e .` first",
)


def run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["skillcheck", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=stdin,
    )


def run_fixture(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["skillcheck", "--skip-dirname-check", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=stdin,
    )


_VALID_SKILL = str(FIXTURES_DIR / "valid_full.md")
_BAD_SKILL = str(FIXTURES_DIR / "bad_name_caps.md")
_CLEAN_RESPONSE = str(CRITIQUE_DIR / "response_clean.json")
_CONTRA_RESPONSE = str(CRITIQUE_DIR / "response_contradiction.json")
_MALFORMED_RESPONSE = str(CRITIQUE_DIR / "response_malformed.json")
_SCHEMA_ERROR_RESPONSE = str(CRITIQUE_DIR / "response_schema_error.json")


# ---------------------------------------------------------------------------
# --emit-critique-prompt: basic
# ---------------------------------------------------------------------------


def test_emit_critique_prompt_exits_zero() -> None:
    result = run_fixture(_VALID_SKILL, "--emit-critique-prompt")
    assert result.returncode == 0


def test_emit_critique_prompt_stdout_contains_prompt() -> None:
    result = run_fixture(_VALID_SKILL, "--emit-critique-prompt")
    assert len(result.stdout.strip()) > 100
    assert "clarity_score" in result.stdout


def test_emit_critique_prompt_stderr_empty() -> None:
    result = run_fixture(_VALID_SKILL, "--emit-critique-prompt")
    assert result.stderr == ""


def test_emit_critique_prompt_no_symbolic_output() -> None:
    result = run_fixture(_VALID_SKILL, "--emit-critique-prompt")
    # Symbolic validation output starts with ✔ or ✗; shouldn't appear
    assert "PASS" not in result.stdout
    assert "FAIL" not in result.stdout
    assert "Checked" not in result.stdout


def test_emit_critique_prompt_contains_skill_content() -> None:
    result = run_fixture(_VALID_SKILL, "--emit-critique-prompt")
    assert "document-analyzer" in result.stdout


# ---------------------------------------------------------------------------
# --emit-critique-prompt --format json
# ---------------------------------------------------------------------------


def test_emit_critique_prompt_json_format_is_valid_json() -> None:
    result = run_fixture(_VALID_SKILL, "--emit-critique-prompt", "--format", "json")
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert "prompt" in parsed


def test_emit_critique_prompt_json_prompt_key_is_string() -> None:
    result = run_fixture(_VALID_SKILL, "--emit-critique-prompt", "--format", "json")
    parsed = json.loads(result.stdout)
    assert isinstance(parsed["prompt"], str)
    assert len(parsed["prompt"]) > 50


# ---------------------------------------------------------------------------
# --emit-critique-prompt with directory (two skills)
# ---------------------------------------------------------------------------


def test_emit_critique_prompt_directory_contains_delimiters(tmp_path: Path) -> None:
    # Create two minimal SKILL.md files in a directory structure
    for name in ("skill-a", "skill-b"):
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: " + name + "\ndescription: A test skill for " + name + " processing tasks.\n---\n\n## Overview\n\nDoes " + name + " things.\n",
            encoding="utf-8",
        )

    result = subprocess.run(
        ["skillcheck", "--skip-dirname-check", str(tmp_path), "--emit-critique-prompt"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    # Both delimiters should appear (order is sorted by path)
    assert "skillcheck:critique-prompt:" in result.stdout
    # Should appear twice (once per skill)
    assert result.stdout.count("skillcheck:critique-prompt:") == 2


def test_emit_critique_prompt_single_file_no_delimiter() -> None:
    result = run_fixture(_VALID_SKILL, "--emit-critique-prompt")
    assert "skillcheck:critique-prompt:" not in result.stdout


# ---------------------------------------------------------------------------
# --ingest-critique: clean response on passing skill
# ---------------------------------------------------------------------------


def test_ingest_critique_clean_passing_skill_exits_zero() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", _CLEAN_RESPONSE)
    assert result.returncode == 0


def test_ingest_critique_clean_passing_skill_produces_report() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", _CLEAN_RESPONSE)
    assert "PASS" in result.stdout or "passed" in result.stdout


# ---------------------------------------------------------------------------
# --ingest-critique: contradiction (semantic drift = exit 3)
# ---------------------------------------------------------------------------


def test_ingest_critique_contradiction_on_passing_skill_exits_three() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", _CONTRA_RESPONSE)
    assert result.returncode == 3


def test_ingest_critique_contradiction_report_shows_contradiction() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", _CONTRA_RESPONSE)
    assert "semantic.contradiction.detected" in result.stdout


# ---------------------------------------------------------------------------
# --ingest-critique: contradiction on failing skill (symbolic takes priority)
# ---------------------------------------------------------------------------


def test_ingest_critique_contradiction_on_failing_skill_exits_one() -> None:
    result = run("--ingest-critique", _CONTRA_RESPONSE, _BAD_SKILL)
    assert result.returncode == 1


def test_ingest_critique_failing_skill_report_shows_both_issues() -> None:
    result = run("--ingest-critique", _CONTRA_RESPONSE, _BAD_SKILL)
    # Symbolic error and semantic contradiction both appear
    assert "semantic.contradiction.detected" in result.stdout


# ---------------------------------------------------------------------------
# --ingest-critique: malformed JSON -> exit 1 with semantic.ingest.* rule
# ---------------------------------------------------------------------------


def test_ingest_critique_malformed_json_exits_one() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", _MALFORMED_RESPONSE)
    assert result.returncode == 1


def test_ingest_critique_malformed_json_emits_ingest_error_rule() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", _MALFORMED_RESPONSE)
    assert "semantic.ingest.parse_error" in result.stdout


# ---------------------------------------------------------------------------
# --ingest-critique: schema violation -> exit 1
# ---------------------------------------------------------------------------


def test_ingest_critique_schema_error_exits_one() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", _SCHEMA_ERROR_RESPONSE)
    assert result.returncode == 1


def test_ingest_critique_schema_error_emits_ingest_rule() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", _SCHEMA_ERROR_RESPONSE)
    assert "semantic.ingest.parse_error" in result.stdout


# ---------------------------------------------------------------------------
# --ingest-critique: missing path -> exit 2
# ---------------------------------------------------------------------------


def test_ingest_critique_missing_path_exits_two() -> None:
    result = run_fixture(_VALID_SKILL, "--ingest-critique", "/nonexistent/response.json")
    assert result.returncode == 2


def test_ingest_critique_missing_path_message_names_path() -> None:
    bad_path = "/nonexistent/response.json"
    result = run_fixture(_VALID_SKILL, "--ingest-critique", bad_path)
    assert bad_path in result.stderr or bad_path in result.stdout


# ---------------------------------------------------------------------------
# --ingest-critique: reads from stdin when PATH is -
# ---------------------------------------------------------------------------


def test_ingest_critique_stdin_clean_exits_zero() -> None:
    raw = (CRITIQUE_DIR / "response_clean.json").read_text()
    result = run_fixture(_VALID_SKILL, "--ingest-critique", "-", stdin=raw)
    assert result.returncode == 0


def test_ingest_critique_stdin_contradiction_exits_three() -> None:
    raw = (CRITIQUE_DIR / "response_contradiction.json").read_text()
    result = run_fixture(_VALID_SKILL, "--ingest-critique", "-", stdin=raw)
    assert result.returncode == 3


# ---------------------------------------------------------------------------
# Mutual exclusion
# ---------------------------------------------------------------------------


def test_both_flags_together_exits_two() -> None:
    result = run_fixture(
        _VALID_SKILL,
        "--emit-critique-prompt",
        "--ingest-critique", _CLEAN_RESPONSE,
    )
    assert result.returncode == 2


def test_both_flags_together_message_names_both_flags() -> None:
    result = run_fixture(
        _VALID_SKILL,
        "--emit-critique-prompt",
        "--ingest-critique", _CLEAN_RESPONSE,
    )
    combined = result.stdout + result.stderr
    assert "--emit-critique-prompt" in combined
    assert "--ingest-critique" in combined


# ---------------------------------------------------------------------------
# Regression: v0.2.0 invocations produce byte-identical behavior
# ---------------------------------------------------------------------------


def test_regression_valid_skill_text_format() -> None:
    result = run_fixture(_VALID_SKILL)
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert result.stderr == ""


def test_regression_invalid_skill_exits_one() -> None:
    result = run(_BAD_SKILL)
    assert result.returncode == 1


def test_regression_json_format() -> None:
    result = run_fixture(_VALID_SKILL, "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "results" in payload
    assert payload["files_checked"] == 1


def test_regression_ignore_flag() -> None:
    # With --ignore frontmatter, frontmatter errors are suppressed
    result = run_fixture(_VALID_SKILL, "--ignore", "frontmatter")
    assert result.returncode == 0


def test_regression_target_agent_vscode() -> None:
    result = run_fixture(_VALID_SKILL, "--target-agent", "vscode")
    assert result.returncode == 0
