"""CLI tests for --critique-agent flag (Phase 1C)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CRITIQUE_DIR = FIXTURES_DIR / "critique"

pytestmark = pytest.mark.skipif(
    shutil.which("skillcheck") is None,
    reason="skillcheck not installed; run `pip install -e .` first",
)

_SKILL = str(FIXTURES_DIR / "valid_basic.md")
_CLEAN_RESPONSE = str(CRITIQUE_DIR / "response_clean.json")
_FLAGS = ["--skip-dirname-check"]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["skillcheck", *_FLAGS, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# --emit-critique-prompt with agent variants
# ---------------------------------------------------------------------------


def test_emit_claude_contains_xml_skill_tag() -> None:
    result = run(_SKILL, "--emit-critique-prompt", "--critique-agent", "claude")
    assert result.returncode == 0
    assert "<skill_to_critique>" in result.stdout


def test_emit_codex_contains_markdown_skill_header() -> None:
    result = run(_SKILL, "--emit-critique-prompt", "--critique-agent", "codex")
    assert result.returncode == 0
    assert "### Skill" in result.stdout


def test_emit_codex_no_xml_tags() -> None:
    result = run(_SKILL, "--emit-critique-prompt", "--critique-agent", "codex")
    assert "<skill_to_critique>" not in result.stdout


def test_emit_cursor_shorter_than_claude() -> None:
    claude = run(_SKILL, "--emit-critique-prompt", "--critique-agent", "claude")
    cursor = run(_SKILL, "--emit-critique-prompt", "--critique-agent", "cursor")
    assert cursor.returncode == 0
    assert len(cursor.stdout) < len(claude.stdout)


def test_emit_default_equals_claude() -> None:
    default = run(_SKILL, "--emit-critique-prompt")
    claude = run(_SKILL, "--emit-critique-prompt", "--critique-agent", "claude")
    assert default.stdout == claude.stdout


# ---------------------------------------------------------------------------
# --ingest-critique with --critique-agent: critique_source in output
# ---------------------------------------------------------------------------


def test_ingest_text_output_has_critique_source() -> None:
    result = run(_SKILL, "--ingest-critique", _CLEAN_RESPONSE, "--critique-agent", "codex")
    assert result.returncode == 0
    assert "Critique source: codex" in result.stdout


def test_ingest_json_output_has_critique_source_field() -> None:
    result = run(
        _SKILL,
        "--ingest-critique",
        _CLEAN_RESPONSE,
        "--critique-agent",
        "cursor",
        "--format",
        "json",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload.get("critique_source") == "cursor"


def test_ingest_default_agent_adds_claude_source() -> None:
    result = run(_SKILL, "--ingest-critique", _CLEAN_RESPONSE)
    assert result.returncode == 0
    assert "Critique source: claude" in result.stdout


def test_ingest_json_default_agent_adds_claude_source_field() -> None:
    result = run(_SKILL, "--ingest-critique", _CLEAN_RESPONSE, "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload.get("critique_source") == "claude"


# ---------------------------------------------------------------------------
# --critique-agent alone (no --emit or --ingest) is an error
# ---------------------------------------------------------------------------


def test_critique_agent_without_emit_or_ingest_exits_two() -> None:
    result = run(_SKILL, "--critique-agent", "codex")
    assert result.returncode == 2
    assert "--critique-agent" in result.stderr


# ---------------------------------------------------------------------------
# Invalid agent name rejected by argparse
# ---------------------------------------------------------------------------


def test_invalid_agent_name_exits_two() -> None:
    result = run(_SKILL, "--emit-critique-prompt", "--critique-agent", "gpt-4o")
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Phase 1B regression: existing invocations without --critique-agent unchanged
# ---------------------------------------------------------------------------


def test_emit_without_critique_agent_exits_zero() -> None:
    result = run(_SKILL, "--emit-critique-prompt")
    assert result.returncode == 0


def test_ingest_without_critique_agent_exits_zero() -> None:
    result = run(_SKILL, "--ingest-critique", _CLEAN_RESPONSE)
    assert result.returncode == 0
