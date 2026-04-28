"""Tests for --emit-graph and --analyze-graph CLI flags.

Covers: emit mode (text/json), analyze mode (augment), mutual exclusion,
directory emit, and backward-compat smoke tests.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import FIXTURES_DIR

pytestmark = pytest.mark.skipif(
    shutil.which("skillcheck") is None,
    reason="skillcheck not installed; run `pip install -e .` first",
)

GRAPH_FIXTURES = Path(__file__).parent / "fixtures" / "graph"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["skillcheck", "--skip-dirname-check", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# --emit-graph: basic text output
# ---------------------------------------------------------------------------


def test_emit_graph_exits_zero() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph")
    assert result.returncode == 0


def test_emit_graph_text_contains_source() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph")
    assert "source: heuristic" in result.stdout


def test_emit_graph_text_contains_sections() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph")
    assert "Capabilities" in result.stdout
    assert "Inputs" in result.stdout
    assert "Outputs" in result.stdout
    assert "Edges" in result.stdout


def test_emit_graph_text_contains_capability_name() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph")
    assert "Generate report" in result.stdout


def test_emit_graph_text_contains_io_items() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph")
    assert "db_client" in result.stdout
    assert "report.json" in result.stdout


def test_emit_graph_produces_no_validation_report() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph")
    # The standard validation summary line must not appear.
    assert "PASS" not in result.stdout
    assert "FAIL" not in result.stdout
    assert "Checked" not in result.stdout


# ---------------------------------------------------------------------------
# --emit-graph --format json
# ---------------------------------------------------------------------------


def test_emit_graph_json_exits_zero() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph", "--format", "json")
    assert result.returncode == 0


def test_emit_graph_json_is_valid_json() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph", "--format", "json")
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)


def test_emit_graph_json_has_expected_keys() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph", "--format", "json")
    parsed = json.loads(result.stdout)
    assert set(parsed.keys()) >= {"source", "capabilities", "inputs", "outputs", "edges"}


def test_emit_graph_json_capability_count() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_basic_io.md"), "--emit-graph", "--format", "json")
    parsed = json.loads(result.stdout)
    assert len(parsed["capabilities"]) == 1


# ---------------------------------------------------------------------------
# --emit-graph with directory (multiple files)
# ---------------------------------------------------------------------------


def test_emit_graph_directory_emits_delimiter(tmp_path: Path) -> None:
    # Copy two graph fixtures into a temp directory so the scanner finds them.
    for fname in ("skill_basic_io.md", "skill_orphan_capability.md"):
        src = GRAPH_FIXTURES / fname
        dest = tmp_path / fname
        dest.write_text(src.read_text())
    # Rename them so they match the SKILL.md scanner pattern.
    (tmp_path / "skill_basic_io.md").rename(tmp_path / "SKILL.md")
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "skill_orphan_capability.md").rename(sub / "SKILL.md")
    result = _run(str(tmp_path), "--emit-graph")
    assert result.returncode == 0
    assert "# === skillcheck:graph:" in result.stdout


# ---------------------------------------------------------------------------
# --analyze-graph: augment mode
# ---------------------------------------------------------------------------


def test_analyze_graph_exits_zero_for_clean_file() -> None:
    result = _run(str(FIXTURES_DIR / "valid_basic.md"), "--analyze-graph")
    assert result.returncode == 0


def test_analyze_graph_exits_zero_when_only_warnings() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_orphan_capability.md"), "--analyze-graph")
    assert result.returncode == 0


def test_analyze_graph_includes_graph_rule_in_output() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_orphan_capability.md"), "--analyze-graph")
    assert "graph.capability.orphaned" in result.stdout


def test_analyze_graph_still_includes_validation_summary() -> None:
    result = _run(str(GRAPH_FIXTURES / "skill_orphan_capability.md"), "--analyze-graph")
    assert "Checked" in result.stdout


def test_analyze_graph_json_includes_graph_diagnostics() -> None:
    result = _run(
        str(GRAPH_FIXTURES / "skill_orphan_capability.md"),
        "--analyze-graph",
        "--format", "json",
    )
    parsed = json.loads(result.stdout)
    rules = [d["rule"] for r in parsed["results"] for d in r["diagnostics"]]
    assert "graph.capability.orphaned" in rules


def test_analyze_graph_no_graph_diagnostics_for_empty_graph() -> None:
    """A skill with no capabilities/IO produces no graph diagnostics."""
    result = _run(
        str(GRAPH_FIXTURES / "skill_no_structure.md"),
        "--analyze-graph",
        "--format", "json",
    )
    parsed = json.loads(result.stdout)
    rules = [d["rule"] for r in parsed["results"] for d in r["diagnostics"]]
    graph_rules = [r for r in rules if r.startswith("graph.")]
    assert graph_rules == []


# ---------------------------------------------------------------------------
# Mutual exclusion
# ---------------------------------------------------------------------------


def test_emit_graph_and_analyze_graph_are_mutually_exclusive() -> None:
    result = _run(
        str(GRAPH_FIXTURES / "skill_basic_io.md"),
        "--emit-graph",
        "--analyze-graph",
    )
    assert result.returncode == 2
    assert "--emit-graph" in result.stderr


def test_emit_graph_and_emit_critique_prompt_are_mutually_exclusive() -> None:
    result = _run(
        str(GRAPH_FIXTURES / "skill_basic_io.md"),
        "--emit-graph",
        "--emit-critique-prompt",
    )
    assert result.returncode == 2


def test_emit_graph_and_ingest_critique_are_mutually_exclusive(tmp_path: Path) -> None:
    dummy = tmp_path / "r.json"
    dummy.write_text("{}")
    result = _run(
        str(GRAPH_FIXTURES / "skill_basic_io.md"),
        "--emit-graph",
        "--ingest-critique", str(dummy),
    )
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Backward-compat smoke tests
# ---------------------------------------------------------------------------


def test_normal_validation_unaffected_by_new_flags() -> None:
    result = _run(str(FIXTURES_DIR / "valid_basic.md"))
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_format_json_still_works_without_graph_flags() -> None:
    result = _run(str(FIXTURES_DIR / "valid_basic.md"), "--format", "json")
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert "results" in parsed
