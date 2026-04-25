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
