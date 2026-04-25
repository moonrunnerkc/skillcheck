"""Capability graph extraction module for skillcheck v1.0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


GRAPH_STUB_MESSAGE = "Capability graph extraction lands in v1.0."


@dataclass(frozen=True)
class CapabilityEdge:
    """Directed relationship between two capability nodes."""

    source: str
    relation: str
    target: str


def extract_capability_graph(skill_path: Path) -> list[CapabilityEdge]:
    """Extract capability edges from a skill document.

    Args:
        skill_path: Path to the SKILL.md file under analysis.

    Returns:
        Directed capability edges.

    Raises:
        NotImplementedError: Always raised in Phase 0 scaffolding.
    """
    raise NotImplementedError(GRAPH_STUB_MESSAGE)
