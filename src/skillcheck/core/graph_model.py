"""Capability graph data model for skillcheck.

The frozen dataclasses that make up a ``CapabilityGraph`` live here, separated
from the heuristic extractor in ``graph.py`` so the model can be imported
without pulling in the extraction machinery. ``graph.py`` re-exports these
names, so ``from skillcheck.core.graph import CapabilityGraph`` still works.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Capability:
    """A declared capability: something the skill can do."""

    id: str
    name: str
    description: str
    line: int | None


@dataclass(frozen=True)
class Input:
    """An input consumed by one or more capabilities."""

    id: str
    name: str
    kind: Literal["file", "tool", "env", "context", "prerequisite"]
    line: int | None


@dataclass(frozen=True)
class Output:
    """An output produced by one or more capabilities."""

    id: str
    name: str
    kind: Literal["file", "artifact", "side_effect", "return"]
    line: int | None


@dataclass(frozen=True)
class Edge:
    """Directed relationship between a capability and an input or output."""

    source_id: str
    target_id: str
    kind: Literal["requires", "produces"]


@dataclass(frozen=True)
class CapabilityGraph:
    """Complete capability graph for a single ParsedSkill.

    All fields are tuples to preserve hashability of the frozen dataclass.
    Constructed graphs are validated in __post_init__.
    """

    capabilities: tuple[Capability, ...]
    inputs: tuple[Input, ...]
    outputs: tuple[Output, ...]
    edges: tuple[Edge, ...]
    source: Literal["heuristic", "agent"]

    def __post_init__(self) -> None:
        capability_ids = {c.id for c in self.capabilities}
        input_ids = {i.id for i in self.inputs}
        output_ids = {o.id for o in self.outputs}

        # Duplicate ID check across all node collections.
        all_ids: list[str] = (
            [c.id for c in self.capabilities]
            + [i.id for i in self.inputs]
            + [o.id for o in self.outputs]
        )
        seen: set[str] = set()
        for nid in all_ids:
            if nid in seen:
                raise ValueError(
                    f"Duplicate node ID '{nid}' appears in multiple "
                    f"capability graph collections."
                )
            seen.add(nid)

        # Edge referential integrity.
        for edge in self.edges:
            if edge.source_id not in capability_ids:
                raise ValueError(
                    f"Edge source_id '{edge.source_id}' does not reference a known capability "
                    f"(edge: {edge.source_id!r} -[{edge.kind}]-> {edge.target_id!r})."
                )
            if edge.kind == "requires":
                if edge.target_id not in input_ids:
                    misrouted = "an output" if edge.target_id in output_ids else "unknown"
                    raise ValueError(
                        f"Edge kind='requires' has target_id '{edge.target_id}' which is not an "
                        f"input ID ({misrouted}). "
                        f"Edge: {edge.source_id!r} -[requires]-> {edge.target_id!r}."
                    )
            elif edge.kind == "produces":
                if edge.target_id not in output_ids:
                    misrouted = "an input" if edge.target_id in input_ids else "unknown"
                    raise ValueError(
                        f"Edge kind='produces' has target_id '{edge.target_id}' which is not an "
                        f"output ID ({misrouted}). "
                        f"Edge: {edge.source_id!r} -[produces]-> {edge.target_id!r}."
                    )
