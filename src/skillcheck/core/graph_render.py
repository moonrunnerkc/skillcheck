"""Graph rendering functions for CapabilityGraph.

render_graph_text and render_graph_json are both pure functions. No I/O.

Field ordering for JSON is determined by dataclass field declaration order:
  Capability: id, name, description, line
  Input:       id, name, kind, line
  Output:      id, name, kind, line
  Edge:        source_id, target_id, kind

Top-level JSON key order: source, capabilities, inputs, outputs, edges.
"""

from __future__ import annotations

import dataclasses
import json

from skillcheck.core.graph import CapabilityGraph


def render_graph_text(graph: CapabilityGraph) -> str:
    """Render a CapabilityGraph as human-readable plain text.

    Sections: source, Capabilities, Inputs, Outputs, Edges. Ordering follows
    the CapabilityGraph tuple fields (already sorted by line then name).

    Args:
        graph: Extracted capability graph.

    Returns:
        Multi-line string suitable for terminal output.
    """
    # Build a fast lookup: id -> name for capabilities and IO nodes.
    cap_by_id = {c.id: c.name for c in graph.capabilities}
    inp_by_id = {i.id: i.name for i in graph.inputs}
    out_by_id = {o.id: o.name for o in graph.outputs}

    lines: list[str] = []
    lines.append(f"source: {graph.source}")
    lines.append("")

    lines.append(f"Capabilities ({len(graph.capabilities)}):")
    for cap in graph.capabilities:
        loc = f" [line {cap.line}]" if cap.line is not None else ""
        lines.append(f"  {cap.name}{loc}")
        if cap.description:
            lines.append(f"    {cap.description}")

    lines.append("")
    lines.append(f"Inputs ({len(graph.inputs)}):")
    for inp in graph.inputs:
        loc = f", line {inp.line}" if inp.line is not None else ""
        lines.append(f"  {inp.name} [{inp.kind}{loc}]")

    lines.append("")
    lines.append(f"Outputs ({len(graph.outputs)}):")
    for out in graph.outputs:
        loc = f", line {out.line}" if out.line is not None else ""
        lines.append(f"  {out.name} [{out.kind}{loc}]")

    lines.append("")
    lines.append(f"Edges ({len(graph.edges)}):")
    for edge in graph.edges:
        src_name = cap_by_id.get(edge.source_id, edge.source_id)
        if edge.kind == "requires":
            tgt_name = inp_by_id.get(edge.target_id, edge.target_id)
        else:
            tgt_name = out_by_id.get(edge.target_id, edge.target_id)
        lines.append(f"  {src_name} {edge.kind} {tgt_name}")

    return "\n".join(lines)


def render_graph_json(graph: CapabilityGraph) -> str:
    """Render a CapabilityGraph as deterministic JSON.

    Top-level keys: source, capabilities, inputs, outputs, edges.
    Each node is serialized as a flat object using dataclass field order.
    sort_keys=False preserves declaration order for readability.

    Args:
        graph: Extracted capability graph.

    Returns:
        JSON string, indented with 2 spaces.
    """
    def _node(obj: object) -> dict[str, object]:
        return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}  # type: ignore[arg-type]

    payload = {
        "source": graph.source,
        "capabilities": [_node(c) for c in graph.capabilities],
        "inputs": [_node(i) for i in graph.inputs],
        "outputs": [_node(o) for o in graph.outputs],
        "edges": [_node(e) for e in graph.edges],
    }
    return json.dumps(payload, indent=2, sort_keys=False)
