"""Self-host integration tests for skills/skillcheck/SKILL.md.

The skill at skills/skillcheck/SKILL.md is the fixture-of-truth for all tests here.
Editing the skill may require regenerating tests/fixtures/self_host/graph_clean.json
via the regen-self-host-fixtures Makefile target.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from skillcheck import validate
from skillcheck.core.graph import extract_graph_agent, extract_graph_heuristic
from skillcheck.core.graph_analyzers import run_divergence_analyzers, run_graph_analyzers
from skillcheck.core.semantic import ingest_critique_response
from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.description import score_description

SKILL_PATH = Path(__file__).parent.parent / "skills" / "skillcheck" / "SKILL.md"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "self_host"
CRITIQUE_FIXTURE = FIXTURES_DIR / "critique_clean.json"
GRAPH_FIXTURE = FIXTURES_DIR / "graph_clean.json"


def test_self_host_symbolic_clean() -> None:
    """The skill passes all symbolic rules with zero ERROR and zero WARNING diagnostics."""
    result = validate(SKILL_PATH)
    assert result.valid, "Expected symbolic validation to pass"
    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
    assert errors == [], f"Unexpected ERROR diagnostics: {errors}"
    assert warnings == [], f"Unexpected WARNING diagnostics: {warnings}"


def test_self_host_graph_analyzers_clean() -> None:
    """All five Phase 2B graph analyzers fire zero diagnostics on the heuristic graph."""
    skill = parse(SKILL_PATH)
    graph = extract_graph_heuristic(skill)
    diagnostics = run_graph_analyzers(graph)
    errors_and_warnings = [d for d in diagnostics if d.severity in (Severity.ERROR, Severity.WARNING)]
    assert errors_and_warnings == [], (
        f"Graph analyzers fired unexpected diagnostics: {errors_and_warnings}"
    )


def test_self_host_critique_clean() -> None:
    """Ingesting critique_clean.json against the skill produces zero ERROR and WARNING diagnostics."""
    skill = parse(SKILL_PATH)
    raw = CRITIQUE_FIXTURE.read_text(encoding="utf-8")
    diagnostics = ingest_critique_response(skill, raw)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    warnings = [d for d in diagnostics if d.severity == Severity.WARNING]
    assert errors == [], f"Unexpected ERROR from critique: {errors}"
    assert warnings == [], f"Unexpected WARNING from critique: {warnings}"


def test_self_host_graph_agent_clean() -> None:
    """Ingesting graph_clean.json and running divergence analysis fires zero diagnostics."""
    skill = parse(SKILL_PATH)
    raw = GRAPH_FIXTURE.read_text(encoding="utf-8")
    agent_graph = extract_graph_agent(skill, raw)
    heuristic_graph = extract_graph_heuristic(skill)

    agent_diagnostics = run_graph_analyzers(agent_graph)
    divergence_diagnostics = run_divergence_analyzers(agent_graph, heuristic_graph)
    all_diagnostics = agent_diagnostics + divergence_diagnostics

    errors_and_warnings = [d for d in all_diagnostics if d.severity in (Severity.ERROR, Severity.WARNING)]
    assert errors_and_warnings == [], (
        f"Graph agent/divergence analyzers fired unexpected diagnostics: {errors_and_warnings}"
    )


def test_self_host_full_pipeline_clean() -> None:
    """CLI end-to-end: --ingest-critique + --ingest-graph exits 0 with no ERROR or WARNING."""
    result = subprocess.run(
        [
            sys.executable, "-m", "skillcheck",
            str(SKILL_PATH),
            "--ingest-critique", str(CRITIQUE_FIXTURE),
            "--ingest-graph", str(GRAPH_FIXTURE),
            "--format", "json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit code 0, got {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    output = json.loads(result.stdout)
    results = output["results"]
    assert len(results) == 1
    diagnostics = results[0]["diagnostics"]
    errors_and_warnings = [
        d for d in diagnostics
        if d["severity"] in ("error", "warning")
    ]
    assert errors_and_warnings == [], (
        f"Merged report has unexpected ERROR/WARNING diagnostics: {errors_and_warnings}"
    )


def test_self_host_history_round_trip(tmp_path: Path) -> None:
    """--history records a run; --show-history reads it back with exactly one entry."""
    # Parent directory must be named "skillcheck" to satisfy the dirname rule.
    skill_dir = tmp_path / "skillcheck"
    skill_dir.mkdir()
    skill_copy = skill_dir / "SKILL.md"
    shutil.copy(SKILL_PATH, skill_copy)

    record_result = subprocess.run(
        [sys.executable, "-m", "skillcheck", str(skill_copy), "--history", "--no-color"],
        capture_output=True,
        text=True,
    )
    assert record_result.returncode == 0, (
        f"--history exited {record_result.returncode}: {record_result.stdout}{record_result.stderr}"
    )

    show_result = subprocess.run(
        [sys.executable, "-m", "skillcheck", str(skill_copy), "--show-history", "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert show_result.returncode == 0, (
        f"--show-history exited {show_result.returncode}: {show_result.stdout}{show_result.stderr}"
    )

    ledger = json.loads(show_result.stdout)
    assert len(ledger["runs"]) == 1, f"Expected 1 ledger run, got {len(ledger['runs'])}"
    run = ledger["runs"][0]
    assert run["validation_modes"]["symbolic"] is True
    assert run["validation_modes"]["critique"] is False
    assert run["validation_modes"]["graph"] is False
    assert run["exit_code"] == 0


def test_self_host_description_score_above_threshold() -> None:
    """The skill description scores >= 85 with the live heuristic scorer."""
    skill = parse(SKILL_PATH)
    desc = skill.frontmatter.get("description", "")
    assert isinstance(desc, str) and desc.strip(), "Description must be a non-empty string"
    score, _, _ = score_description(desc)
    assert score >= 85, f"Description score {score} is below the 85 threshold: {desc!r}"
