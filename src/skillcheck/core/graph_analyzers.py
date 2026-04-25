"""Graph-level analyzers that emit diagnostics from a CapabilityGraph.

All five analyzers are pure functions. They accept a CapabilityGraph and return
a list of Diagnostic objects. Every diagnostic carries severity WARNING.

Analyzers:
    check_orphaned_capabilities  -> rule graph.capability.orphaned
    check_unused_inputs          -> rule graph.input.unused
    check_unproduced_outputs     -> rule graph.output.unproduced
    check_empty_descriptions     -> rule graph.capability.empty_description
    check_unreferenced_tools     -> rule graph.tool.unreferenced

Entry point:
    run_graph_analyzers(graph)   -> list[Diagnostic]  (runs all analyzers in order)
"""

from __future__ import annotations

from collections.abc import Callable

from skillcheck.core.graph import CapabilityGraph
from skillcheck.result import Diagnostic, Severity


def check_orphaned_capabilities(graph: CapabilityGraph) -> list[Diagnostic]:
    """Fire on any capability that has zero edges (neither requires nor produces).

    Args:
        graph: Extracted capability graph.

    Returns:
        One WARNING per orphaned capability.
    """
    connected_sources = {e.source_id for e in graph.edges}
    results: list[Diagnostic] = []
    for cap in graph.capabilities:
        if cap.id not in connected_sources:
            results.append(
                Diagnostic(
                    rule="graph.capability.orphaned",
                    severity=Severity.WARNING,
                    message=(
                        f"Capability '{cap.name}' has no declared inputs or outputs. "
                        "Either add backtick references to its inputs/outputs in the "
                        "capability body, or remove the capability if it is incidental."
                    ),
                    line=cap.line,
                )
            )
    return results


def check_unused_inputs(graph: CapabilityGraph) -> list[Diagnostic]:
    """Fire on body-declared inputs (line is not None) that have no requires edge.

    Frontmatter tools (kind='tool', line is None) are handled separately by
    check_unreferenced_tools to avoid double-firing.

    Args:
        graph: Extracted capability graph.

    Returns:
        One WARNING per unused body input.
    """
    required_targets = {e.target_id for e in graph.edges if e.kind == "requires"}
    results: list[Diagnostic] = []
    for inp in graph.inputs:
        if inp.line is None:
            # Frontmatter-sourced; covered by check_unreferenced_tools.
            continue
        if inp.id not in required_targets:
            results.append(
                Diagnostic(
                    rule="graph.input.unused",
                    severity=Severity.WARNING,
                    message=(
                        f"Input '{inp.name}' ({inp.kind}) is declared but no capability "
                        "requires it. Either backtick-reference it in a capability body, "
                        "or remove it if it is not actually needed."
                    ),
                    line=inp.line,
                )
            )
    return results


def check_unproduced_outputs(graph: CapabilityGraph) -> list[Diagnostic]:
    """Fire on any output that has no produces edge pointing to it.

    Args:
        graph: Extracted capability graph.

    Returns:
        One WARNING per unproduced output.
    """
    produced_targets = {e.target_id for e in graph.edges if e.kind == "produces"}
    results: list[Diagnostic] = []
    for out in graph.outputs:
        if out.id not in produced_targets:
            results.append(
                Diagnostic(
                    rule="graph.output.unproduced",
                    severity=Severity.WARNING,
                    message=(
                        f"Output '{out.name}' ({out.kind}) is declared but no capability "
                        "produces it. Either backtick-reference it in the producing "
                        "capability's body, or remove it if it is not actually produced."
                    ),
                    line=out.line,
                )
            )
    return results


def check_empty_descriptions(graph: CapabilityGraph) -> list[Diagnostic]:
    """Fire on any capability whose description is an empty string.

    Args:
        graph: Extracted capability graph.

    Returns:
        One WARNING per capability with no description text.
    """
    results: list[Diagnostic] = []
    for cap in graph.capabilities:
        if cap.description == "":
            results.append(
                Diagnostic(
                    rule="graph.capability.empty_description",
                    severity=Severity.WARNING,
                    message=(
                        f"Capability '{cap.name}' has no description. "
                        "Add at least one sentence under the heading explaining what it does."
                    ),
                    line=cap.line,
                )
            )
    return results


def check_unreferenced_tools(graph: CapabilityGraph) -> list[Diagnostic]:
    """Fire on allowed-tools entries (kind='tool', line is None) with no requires edge.

    Body-declared tool inputs (line is not None) are handled by check_unused_inputs
    to avoid double-firing.

    Args:
        graph: Extracted capability graph.

    Returns:
        One WARNING per unreferenced frontmatter tool.
    """
    required_targets = {e.target_id for e in graph.edges if e.kind == "requires"}
    results: list[Diagnostic] = []
    for inp in graph.inputs:
        if inp.kind != "tool" or inp.line is not None:
            # Not a frontmatter tool; skip.
            continue
        if inp.id not in required_targets:
            results.append(
                Diagnostic(
                    rule="graph.tool.unreferenced",
                    severity=Severity.WARNING,
                    message=(
                        f"Tool '{inp.name}' is declared in allowed-tools but never "
                        "referenced in the body. Either reference it from the capability "
                        "that uses it, or remove it from allowed-tools to avoid "
                        "over-permissioning."
                    ),
                    line=None,
                )
            )
    return results


#: Ordered tuple of all graph analyzers. run_graph_analyzers iterates this.
GRAPH_ANALYZERS: tuple[Callable[[CapabilityGraph], list[Diagnostic]], ...] = (
    check_orphaned_capabilities,
    check_unused_inputs,
    check_unproduced_outputs,
    check_empty_descriptions,
    check_unreferenced_tools,
)


def run_graph_analyzers(graph: CapabilityGraph) -> list[Diagnostic]:
    """Run all graph analyzers in declaration order and return combined diagnostics.

    Args:
        graph: Extracted capability graph.

    Returns:
        Flat list of Diagnostic, one entry per finding, in analyzer order.
    """
    results: list[Diagnostic] = []
    for analyzer in GRAPH_ANALYZERS:
        results.extend(analyzer(graph))
    return results


# ---------------------------------------------------------------------------
# Agent-vs-heuristic divergence analyzers (Phase 2C)
# ---------------------------------------------------------------------------


def check_heuristic_disagreement(
    agent_graph: CapabilityGraph,
    heuristic_graph: CapabilityGraph,
) -> list[Diagnostic]:
    """Fire on structural contradictions between agent and heuristic graphs.

    Fires graph.contradiction.heuristic_disagreement at ERROR severity when:
      - The agent claims a capability produces an output (or requires an input),
      - Both the capability name and the target name appear in the heuristic graph
        (meaning the heuristic found them declared literally in the skill body),
      - But the heuristic has no edge from that capability to that target.

    The heuristic only creates edges when a node name is backtick-referenced in
    a capability's body section. If the heuristic has the node in its collection
    (meaning the node IS declared in the body) but no edge, the output/input is
    not backtick-referenced. The agent claiming a semantic edge in this situation
    is a contradiction: either the agent over-claimed, or the skill body needs a
    backtick reference added.

    Does NOT fire when the agent finds capabilities or targets that the heuristic
    missed entirely (different node names in each graph). Agent finding more nodes
    than the heuristic is expected behavior; heuristic extraction is lossy.

    Args:
        agent_graph: Graph produced by the agent-mode extractor (source="agent").
        heuristic_graph: Graph produced by the heuristic extractor (source="heuristic").

    Returns:
        List of ERROR diagnostics, one per contradicted edge.
    """
    # Build name-to-id indexes for the heuristic graph.
    heuristic_cap_by_name: dict[str, str] = {
        c.name: c.id for c in heuristic_graph.capabilities
    }
    heuristic_inp_by_name: dict[str, str] = {
        i.name: i.id for i in heuristic_graph.inputs
    }
    heuristic_out_by_name: dict[str, str] = {
        o.name: o.id for o in heuristic_graph.outputs
    }

    # Build the set of (source_id, target_id, kind) tuples in the heuristic graph
    # for fast membership testing.
    heuristic_edge_set: frozenset[tuple[str, str, str]] = frozenset(
        (e.source_id, e.target_id, e.kind) for e in heuristic_graph.edges
    )

    # Build agent id -> name lookups.
    agent_cap_by_id: dict[str, str] = {c.id: c.name for c in agent_graph.capabilities}
    agent_inp_by_id: dict[str, str] = {i.id: i.name for i in agent_graph.inputs}
    agent_out_by_id: dict[str, str] = {o.id: o.name for o in agent_graph.outputs}

    results: list[Diagnostic] = []

    for edge in agent_graph.edges:
        # Resolve the capability and target by name from the agent graph.
        cap_name = agent_cap_by_id.get(edge.source_id)
        if cap_name is None:
            # Edge source doesn't resolve; CapabilityGraph constructor would have
            # caught dangling edges, so this shouldn't occur. Skip defensively.
            continue

        if edge.kind == "produces":
            target_name = agent_out_by_id.get(edge.target_id)
            if target_name is None:
                continue

            # Check if both endpoints exist in the heuristic graph (by name).
            h_cap_id = heuristic_cap_by_name.get(cap_name)
            h_target_id = heuristic_out_by_name.get(target_name)
            if h_cap_id is None or h_target_id is None:
                # At least one endpoint not in the heuristic graph; heuristic
                # extraction is lossy, so this is expected. No contradiction.
                continue

            # Both endpoints exist in both graphs. Check for the missing edge.
            if (h_cap_id, h_target_id, "produces") not in heuristic_edge_set:
                results.append(
                    Diagnostic(
                        rule="graph.contradiction.heuristic_disagreement",
                        severity=Severity.ERROR,
                        message=(
                            f"Agent claims capability '{cap_name}' produces "
                            f"'{target_name}', but '{target_name}' is not "
                            f"backtick-referenced in the capability body. "
                            f"Either the agent over-claimed, or add the reference "
                            f"to the body."
                        ),
                        line=None,
                    )
                )

        elif edge.kind == "requires":
            target_name = agent_inp_by_id.get(edge.target_id)
            if target_name is None:
                continue

            h_cap_id = heuristic_cap_by_name.get(cap_name)
            h_target_id = heuristic_inp_by_name.get(target_name)
            if h_cap_id is None or h_target_id is None:
                continue

            if (h_cap_id, h_target_id, "requires") not in heuristic_edge_set:
                results.append(
                    Diagnostic(
                        rule="graph.contradiction.heuristic_disagreement",
                        severity=Severity.ERROR,
                        message=(
                            f"Agent claims capability '{cap_name}' requires "
                            f"'{target_name}', but '{target_name}' is not "
                            f"backtick-referenced in the capability body. "
                            f"Either the agent over-claimed, or add the reference "
                            f"to the body."
                        ),
                        line=None,
                    )
                )

    return results


#: Ordered tuple of divergence analyzers. run_divergence_analyzers iterates this.
GRAPH_DIVERGENCE_ANALYZERS: tuple[
    Callable[[CapabilityGraph, CapabilityGraph], list[Diagnostic]], ...
] = (check_heuristic_disagreement,)


def run_divergence_analyzers(
    agent: CapabilityGraph,
    heuristic: CapabilityGraph,
) -> list[Diagnostic]:
    """Run all divergence analyzers and return combined diagnostics.

    Args:
        agent: Graph produced by agent-mode extraction.
        heuristic: Graph produced by heuristic extraction of the same skill.

    Returns:
        Flat list of Diagnostic, one entry per finding, in analyzer order.
    """
    results: list[Diagnostic] = []
    for analyzer in GRAPH_DIVERGENCE_ANALYZERS:
        results.extend(analyzer(agent, heuristic))
    return results
