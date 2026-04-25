"""Tests for the heuristic-disagreement divergence analyzer (Phase 2C)."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillcheck.agents.graph_parser import parse_graph_response
from skillcheck.core.graph import (
    Capability,
    CapabilityGraph,
    Edge,
    Input,
    Output,
    extract_graph_heuristic,
)
from skillcheck.core.graph_analyzers import (
    GRAPH_DIVERGENCE_ANALYZERS,
    check_heuristic_disagreement,
    run_divergence_analyzers,
)
from skillcheck.parser import parse
from skillcheck.result import Severity

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GRAPH_DIR = FIXTURES_DIR / "graph"
GR_DIR = FIXTURES_DIR / "graph_responses"


def _skill():
    return parse(GRAPH_DIR / "skill_basic_io.md")


def _heuristic():
    return extract_graph_heuristic(_skill())


def _agent_from_fixture(filename: str) -> CapabilityGraph:
    raw = (GR_DIR / filename).read_text()
    return parse_graph_response(raw, _skill())


# ---------------------------------------------------------------------------
# Agreement case: no diagnostics
# ---------------------------------------------------------------------------


def test_clean_response_no_divergence() -> None:
    agent = _agent_from_fixture("response_clean.json")
    heuristic = _heuristic()
    diags = check_heuristic_disagreement(agent, heuristic)
    assert diags == []


def test_extra_capabilities_no_divergence() -> None:
    agent = _agent_from_fixture("response_extra_capabilities.json")
    heuristic = _heuristic()
    diags = check_heuristic_disagreement(agent, heuristic)
    assert diags == []


def test_empty_agent_graph_no_divergence() -> None:
    agent = CapabilityGraph(
        capabilities=(), inputs=(), outputs=(), edges=(), source="agent"
    )
    diags = check_heuristic_disagreement(agent, _heuristic())
    assert diags == []


def test_run_divergence_analyzers_no_divergence_returns_empty() -> None:
    agent = _agent_from_fixture("response_clean.json")
    diags = run_divergence_analyzers(agent, _heuristic())
    assert diags == []


# ---------------------------------------------------------------------------
# Contradiction case: ERROR diagnostics
# ---------------------------------------------------------------------------


def test_contradiction_fires_one_error() -> None:
    agent = _agent_from_fixture("response_with_contradiction.json")
    heuristic = _heuristic()
    diags = check_heuristic_disagreement(agent, heuristic)
    assert len(diags) == 1


def test_contradiction_diagnostic_is_error_severity() -> None:
    agent = _agent_from_fixture("response_with_contradiction.json")
    heuristic = _heuristic()
    diags = check_heuristic_disagreement(agent, heuristic)
    assert all(d.severity == Severity.ERROR for d in diags)


def test_contradiction_rule_id() -> None:
    agent = _agent_from_fixture("response_with_contradiction.json")
    heuristic = _heuristic()
    diags = check_heuristic_disagreement(agent, heuristic)
    assert diags[0].rule == "graph.contradiction.heuristic_disagreement"


def test_contradiction_message_names_capability_and_output() -> None:
    agent = _agent_from_fixture("response_with_contradiction.json")
    heuristic = _heuristic()
    diags = check_heuristic_disagreement(agent, heuristic)
    msg = diags[0].message
    assert "Generate report" in msg
    assert "execution summary" in msg
    assert "backtick-referenced" in msg


# ---------------------------------------------------------------------------
# Requires-direction contradiction
# ---------------------------------------------------------------------------


def test_requires_contradiction_fires_error() -> None:
    """Agent claims cap -requires-> input where heuristic has both but no edge."""
    # Build a custom agent graph where cap "Generate report" requires "DB_URL"
    # (heuristic has both but no requires edge).
    skill = _skill()
    h = _heuristic()
    cap = Capability(id="c1", name="Generate report", description="desc", line=8)
    inp = Input(id="i1", name="DB_URL", kind="env", line=5)
    edge = Edge(source_id="c1", target_id="i1", kind="requires")
    agent = CapabilityGraph(
        capabilities=(cap,), inputs=(inp,), outputs=(), edges=(edge,), source="agent"
    )
    diags = check_heuristic_disagreement(agent, h)
    assert len(diags) == 1
    assert diags[0].severity == Severity.ERROR
    assert "DB_URL" in diags[0].message
    assert "requires" in diags[0].message


# ---------------------------------------------------------------------------
# Severity invariant
# ---------------------------------------------------------------------------


def test_all_divergence_diagnostics_are_error() -> None:
    """Every diagnostic from check_heuristic_disagreement must be ERROR severity."""
    agent = _agent_from_fixture("response_with_contradiction.json")
    heuristic = _heuristic()
    diags = check_heuristic_disagreement(agent, heuristic)
    for d in diags:
        assert d.severity == Severity.ERROR, (
            f"Expected ERROR for {d.rule}, got {d.severity}"
        )


def test_divergence_analyzers_tuple_non_empty() -> None:
    assert len(GRAPH_DIVERGENCE_ANALYZERS) >= 1


# ---------------------------------------------------------------------------
# Agent-finds-new-capability case (missing node, no divergence)
# ---------------------------------------------------------------------------


def test_agent_finds_cap_not_in_heuristic_no_divergence() -> None:
    """If agent has a capability the heuristic missed, no divergence fires."""
    out = Output(id="o1", name="report.json", kind="file", line=14)
    cap = Capability(
        id="c1", name="unseen_capability", description="brand new", line=None
    )
    edge = Edge(source_id="c1", target_id="o1", kind="produces")
    agent = CapabilityGraph(
        capabilities=(cap,), inputs=(), outputs=(out,), edges=(edge,), source="agent"
    )
    diags = check_heuristic_disagreement(agent, _heuristic())
    assert diags == []
