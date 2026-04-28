"""CLI tests for --emit-graph-prompt, --ingest-graph, and --graph-agent flags (Phase 2C)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GR_DIR = FIXTURES_DIR / "graph_responses"
GRAPH_DIR = FIXTURES_DIR / "graph"
CRITIQUE_DIR = FIXTURES_DIR / "critique"

pytestmark = pytest.mark.skipif(
    shutil.which("skillcheck") is None,
    reason="skillcheck not installed; run `pip install -e .` first",
)

_SKILL_BASIC_IO = str(GRAPH_DIR / "skill_basic_io.md")
_SKILL_VALID = str(FIXTURES_DIR / "valid_basic.md")
_CLEAN_GRAPH = str(GR_DIR / "response_clean.json")
_CONTRADICTION_GRAPH = str(GR_DIR / "response_with_contradiction.json")
_MALFORMED_GRAPH = str(GR_DIR / "response_malformed.json")
_SCHEMA_ERR_GRAPH = str(GR_DIR / "response_schema_error.json")
_CLEAN_CRITIQUE = str(CRITIQUE_DIR / "response_clean.json")
_FLAGS = ["--skip-dirname-check"]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["skillcheck", *_FLAGS, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# --emit-graph-prompt with agent variants
# ---------------------------------------------------------------------------


def test_emit_graph_prompt_claude_contains_xml_skill_tag() -> None:
    result = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--graph-agent", "claude")
    assert result.returncode == 0
    assert "<skill_to_analyze>" in result.stdout


def test_emit_graph_prompt_codex_contains_markdown_skill_header() -> None:
    result = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--graph-agent", "codex")
    assert result.returncode == 0
    assert "### Skill" in result.stdout


def test_emit_graph_prompt_codex_no_xml_tags() -> None:
    result = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--graph-agent", "codex")
    assert "<skill_to_analyze>" not in result.stdout


def test_emit_graph_prompt_cursor_shorter_than_claude() -> None:
    claude = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--graph-agent", "claude")
    cursor = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--graph-agent", "cursor")
    assert cursor.returncode == 0
    assert len(cursor.stdout) < len(claude.stdout)


def test_emit_graph_prompt_default_equals_claude() -> None:
    default = run(_SKILL_BASIC_IO, "--emit-graph-prompt")
    claude = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--graph-agent", "claude")
    assert default.stdout == claude.stdout


def test_emit_graph_prompt_exits_0() -> None:
    result = run(_SKILL_BASIC_IO, "--emit-graph-prompt")
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# --ingest-graph with clean response: exits 0, graph source in report
# ---------------------------------------------------------------------------


def test_ingest_graph_clean_exits_0() -> None:
    result = run(_SKILL_BASIC_IO, "--ingest-graph", _CLEAN_GRAPH)
    assert result.returncode == 0


def test_ingest_graph_text_report_has_graph_source_header() -> None:
    result = run(_SKILL_BASIC_IO, "--ingest-graph", _CLEAN_GRAPH)
    assert "Graph source: agent (claude)" in result.stdout


def test_ingest_graph_json_report_has_graph_source_field() -> None:
    result = run(_SKILL_BASIC_IO, "--ingest-graph", _CLEAN_GRAPH, "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["graph_source"] == {"mode": "agent", "agent": "claude"}


def test_ingest_graph_explicit_codex_agent_shows_in_header() -> None:
    result = run(
        _SKILL_BASIC_IO, "--ingest-graph", _CLEAN_GRAPH, "--graph-agent", "codex"
    )
    assert "Graph source: agent (codex)" in result.stdout


# ---------------------------------------------------------------------------
# --ingest-graph with contradiction: exits 1, ERROR diagnostic
# ---------------------------------------------------------------------------


def test_ingest_graph_contradiction_exits_1() -> None:
    result = run(_SKILL_BASIC_IO, "--ingest-graph", _CONTRADICTION_GRAPH)
    assert result.returncode == 1


def test_ingest_graph_contradiction_has_error_diagnostic() -> None:
    result = run(
        _SKILL_BASIC_IO, "--ingest-graph", _CONTRADICTION_GRAPH, "--format", "json"
    )
    data = json.loads(result.stdout)
    all_diags = [d for r in data["results"] for d in r["diagnostics"]]
    error_rules = [d["rule"] for d in all_diags if d["severity"] == "error"]
    assert "graph.contradiction.heuristic_disagreement" in error_rules


# ---------------------------------------------------------------------------
# Parse errors on --ingest-graph
# ---------------------------------------------------------------------------


def test_ingest_graph_malformed_json_exits_1() -> None:
    result = run(_SKILL_BASIC_IO, "--ingest-graph", _MALFORMED_GRAPH)
    assert result.returncode == 1


def test_ingest_graph_schema_error_exits_1() -> None:
    result = run(_SKILL_BASIC_IO, "--ingest-graph", _SCHEMA_ERR_GRAPH)
    assert result.returncode == 1


def test_ingest_graph_parse_error_has_semantic_diagnostic() -> None:
    result = run(
        _SKILL_BASIC_IO, "--ingest-graph", _MALFORMED_GRAPH, "--format", "json"
    )
    data = json.loads(result.stdout)
    all_rules = [d["rule"] for r in data["results"] for d in r["diagnostics"]]
    assert any(r.startswith("semantic.ingest.graph") for r in all_rules)


# ---------------------------------------------------------------------------
# --analyze-graph shows "Graph source: heuristic"
# ---------------------------------------------------------------------------


def test_analyze_graph_shows_heuristic_source_text() -> None:
    result = run(_SKILL_BASIC_IO, "--analyze-graph")
    assert "Graph source: heuristic" in result.stdout


def test_analyze_graph_shows_heuristic_source_json() -> None:
    result = run(_SKILL_BASIC_IO, "--analyze-graph", "--format", "json")
    data = json.loads(result.stdout)
    assert data["graph_source"] == {"mode": "heuristic"}


# ---------------------------------------------------------------------------
# Combined: --ingest-graph and --ingest-critique
# ---------------------------------------------------------------------------


def test_ingest_graph_and_ingest_critique_together_exits_0() -> None:
    result = run(
        _SKILL_BASIC_IO,
        "--ingest-graph",
        _CLEAN_GRAPH,
        "--ingest-critique",
        _CLEAN_CRITIQUE,
    )
    assert result.returncode == 0


def test_ingest_graph_and_ingest_critique_shows_both_source_headers() -> None:
    result = run(
        _SKILL_BASIC_IO,
        "--ingest-graph",
        _CLEAN_GRAPH,
        "--ingest-critique",
        _CLEAN_CRITIQUE,
    )
    assert "Critique source:" in result.stdout
    assert "Graph source:" in result.stdout


# ---------------------------------------------------------------------------
# Mutual exclusion: exits 2 with conflict message
# ---------------------------------------------------------------------------


def test_emit_graph_prompt_and_emit_critique_prompt_conflict() -> None:
    result = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--emit-critique-prompt")
    assert result.returncode == 2


def test_emit_graph_prompt_and_emit_graph_conflict() -> None:
    result = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--emit-graph")
    assert result.returncode == 2


def test_emit_graph_prompt_and_ingest_graph_conflict() -> None:
    result = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--ingest-graph", _CLEAN_GRAPH)
    assert result.returncode == 2


def test_emit_graph_prompt_and_analyze_graph_conflict() -> None:
    result = run(_SKILL_BASIC_IO, "--emit-graph-prompt", "--analyze-graph")
    assert result.returncode == 2


def test_emit_graph_prompt_and_ingest_critique_conflict() -> None:
    result = run(
        _SKILL_BASIC_IO, "--emit-graph-prompt", "--ingest-critique", _CLEAN_CRITIQUE
    )
    assert result.returncode == 2


def test_ingest_graph_and_emit_graph_conflict() -> None:
    result = run(_SKILL_BASIC_IO, "--ingest-graph", _CLEAN_GRAPH, "--emit-graph")
    assert result.returncode == 2


def test_ingest_graph_and_analyze_graph_conflict() -> None:
    result = run(_SKILL_BASIC_IO, "--ingest-graph", _CLEAN_GRAPH, "--analyze-graph")
    assert result.returncode == 2


def test_ingest_graph_and_emit_critique_prompt_conflict() -> None:
    result = run(
        _SKILL_BASIC_IO, "--ingest-graph", _CLEAN_GRAPH, "--emit-critique-prompt"
    )
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# --graph-agent without emit/ingest exits 2
# ---------------------------------------------------------------------------


def test_graph_agent_without_emit_or_ingest_exits_2() -> None:
    result = run(_SKILL_BASIC_IO, "--graph-agent", "codex")
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Backward compatibility regression
# ---------------------------------------------------------------------------


def test_baseline_valid_skill_exits_0() -> None:
    result = run(_SKILL_VALID)
    assert result.returncode == 0


def test_baseline_valid_skill_json_format() -> None:
    result = run(_SKILL_VALID, "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["files_checked"] == 1
    assert data["files_passed"] == 1
    assert "graph_source" not in data
    assert "critique_source" not in data


def test_analyze_graph_alone_baseline() -> None:
    result = run(_SKILL_VALID, "--analyze-graph")
    assert result.returncode == 0


def test_ingest_critique_alone_baseline() -> None:
    result = run(_SKILL_VALID, "--ingest-critique", _CLEAN_CRITIQUE)
    assert result.returncode == 0
    assert "Critique source:" in result.stdout
    assert "Graph source:" not in result.stdout
