"""Tests for graph analyzer functions.

One positive (fires) and one negative (silent) case per analyzer.
Severity assertion, rule name assertion, and determinism are verified.
run_graph_analyzers integration is tested separately.
"""

from __future__ import annotations

from pathlib import Path

from skillcheck.core.graph import CapabilityGraph, extract_graph_heuristic
from skillcheck.core.graph_analyzers import (
    GRAPH_ANALYZERS,
    check_empty_descriptions,
    check_orphaned_capabilities,
    check_unproduced_outputs,
    check_unreferenced_tools,
    check_unused_inputs,
    run_graph_analyzers,
)
from skillcheck.result import Severity

FIXTURES = Path(__file__).parent / "fixtures" / "graph"


def _graph(filename: str) -> CapabilityGraph:
    from skillcheck.parser import parse as _parse
    skill = _parse(FIXTURES / filename)
    return extract_graph_heuristic(skill)


# ---------------------------------------------------------------------------
# check_orphaned_capabilities
# ---------------------------------------------------------------------------


def test_orphaned_capabilities_fires_for_isolated_capability() -> None:
    diags = check_orphaned_capabilities(_graph("skill_orphan_capability.md"))
    assert len(diags) == 1
    assert diags[0].rule == "graph.capability.orphaned"
    assert diags[0].severity == Severity.WARNING
    assert "Generate report" in diags[0].message


def test_orphaned_capabilities_silent_when_connected() -> None:
    diags = check_orphaned_capabilities(_graph("skill_basic_io.md"))
    assert diags == []


def test_orphaned_capabilities_includes_line_number() -> None:
    diags = check_orphaned_capabilities(_graph("skill_orphan_capability.md"))
    assert diags[0].line is not None


# ---------------------------------------------------------------------------
# check_unused_inputs
# ---------------------------------------------------------------------------


def test_unused_inputs_fires_for_unreferenced_body_input() -> None:
    diags = check_unused_inputs(_graph("skill_unused_input.md"))
    assert len(diags) == 1
    assert diags[0].rule == "graph.input.unused"
    assert diags[0].severity == Severity.WARNING
    assert "config.yaml" in diags[0].message


def test_unused_inputs_silent_when_no_inputs_declared() -> None:
    """A skill with no Inputs section produces no unused-input diagnostics."""
    diags = check_unused_inputs(_graph("skill_orphan_capability.md"))
    assert diags == []


def test_unused_inputs_does_not_fire_for_frontmatter_tools() -> None:
    """Frontmatter tools with no requires edge must NOT fire graph.input.unused."""
    diags = check_unused_inputs(_graph("skill_unreferenced_tool.md"))
    rules = [d.rule for d in diags]
    assert "graph.input.unused" not in rules


# ---------------------------------------------------------------------------
# check_unproduced_outputs
# ---------------------------------------------------------------------------


def test_unproduced_outputs_fires_for_output_with_no_produces_edge() -> None:
    diags = check_unproduced_outputs(_graph("skill_unproduced_output.md"))
    assert len(diags) == 1
    assert diags[0].rule == "graph.output.unproduced"
    assert diags[0].severity == Severity.WARNING
    assert "report.json" in diags[0].message


def test_unproduced_outputs_silent_when_no_outputs_declared() -> None:
    """A skill with no Outputs section produces no unproduced-output diagnostics."""
    diags = check_unproduced_outputs(_graph("skill_orphan_capability.md"))
    assert diags == []


# ---------------------------------------------------------------------------
# check_empty_descriptions
# ---------------------------------------------------------------------------


def test_empty_descriptions_fires_for_headingonly_capability() -> None:
    diags = check_empty_descriptions(_graph("skill_empty_capability.md"))
    rules = [d.rule for d in diags]
    assert "graph.capability.empty_description" in rules
    assert all(d.severity == Severity.WARNING for d in diags)


def test_empty_descriptions_identifies_correct_capability() -> None:
    diags = check_empty_descriptions(_graph("skill_empty_capability.md"))
    firing = [d for d in diags if d.rule == "graph.capability.empty_description"]
    names_in_messages = [d.message for d in firing]
    assert any("Generate report" in m for m in names_in_messages)


def test_empty_descriptions_silent_when_all_described() -> None:
    diags = check_empty_descriptions(_graph("skill_basic_io.md"))
    assert diags == []


# ---------------------------------------------------------------------------
# check_unreferenced_tools
# ---------------------------------------------------------------------------


def test_unreferenced_tools_fires_for_frontmatter_tool_not_in_body() -> None:
    diags = check_unreferenced_tools(_graph("skill_unreferenced_tool.md"))
    assert len(diags) == 1
    assert diags[0].rule == "graph.tool.unreferenced"
    assert diags[0].severity == Severity.WARNING
    assert "Bash" in diags[0].message


def test_unreferenced_tools_silent_when_no_frontmatter_tools() -> None:
    """skill_basic_io.md has no allowed-tools frontmatter entry."""
    diags = check_unreferenced_tools(_graph("skill_basic_io.md"))
    assert diags == []


def test_unreferenced_tools_does_not_fire_for_body_inputs() -> None:
    """Body-declared inputs (line is not None) must not fire graph.tool.unreferenced."""
    diags = check_unreferenced_tools(_graph("skill_unused_input.md"))
    assert diags == []


# ---------------------------------------------------------------------------
# run_graph_analyzers
# ---------------------------------------------------------------------------


def test_run_graph_analyzers_returns_flat_list() -> None:
    diags = run_graph_analyzers(_graph("skill_orphan_capability.md"))
    assert isinstance(diags, list)
    assert all(hasattr(d, "rule") for d in diags)


def test_run_graph_analyzers_includes_orphaned_rule_for_fixture() -> None:
    diags = run_graph_analyzers(_graph("skill_orphan_capability.md"))
    assert any(d.rule == "graph.capability.orphaned" for d in diags)


def test_run_graph_analyzers_is_deterministic() -> None:
    graph = _graph("skill_basic_io.md")
    assert run_graph_analyzers(graph) == run_graph_analyzers(graph)


def test_run_graph_analyzers_returns_empty_for_empty_graph() -> None:
    diags = run_graph_analyzers(_graph("skill_no_structure.md"))
    assert diags == []


def test_graph_analyzers_tuple_has_five_entries() -> None:
    assert len(GRAPH_ANALYZERS) == 5


def test_all_analyzer_diagnostics_are_warnings() -> None:
    """Every diagnostic from every fixture must be WARNING severity (no ERROR, no INFO)."""
    bad_fixtures = [
        "skill_orphan_capability.md",
        "skill_unused_input.md",
        "skill_unproduced_output.md",
        "skill_empty_capability.md",
        "skill_unreferenced_tool.md",
    ]
    for fname in bad_fixtures:
        diags = run_graph_analyzers(_graph(fname))
        for d in diags:
            assert d.severity == Severity.WARNING, (
                f"{fname}: expected WARNING, got {d.severity} for rule {d.rule}"
            )
