"""Agent-native semantic validation interfaces for skillcheck v1.0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


SEMANTIC_STUB_MESSAGE = "Semantic engine requires --agent-reason and lands in v1.0."


@dataclass(frozen=True)
class SemanticIssue:
    """Represents one semantic finding produced by an agent critique."""

    code: str
    message: str
    confidence: float


@dataclass(frozen=True)
class SemanticReport:
    """Structured semantic output returned by the agent bridge."""

    target_agent: str
    score: float
    summary: str
    issues: list[SemanticIssue]
    raw_payload: dict[str, Any]


def build_self_critique_prompt(skill_path: Path, target_agent: str) -> str:
    """Build a structured self-critique prompt for an agent.

    Args:
        skill_path: Path to the SKILL.md file under validation.
        target_agent: Agent template key, such as ``claude`` or ``codex``.

    Returns:
        Prompt text intended for agent-native semantic critique.

    Raises:
        NotImplementedError: Always raised in Phase 0 scaffolding.
    """
    raise NotImplementedError(SEMANTIC_STUB_MESSAGE)


def validate_agent_report(report_payload: dict[str, Any], target_agent: str) -> SemanticReport:
    """Validate a semantic report payload and normalize it into a typed report.

    Args:
        report_payload: Agent-produced JSON payload from self-critique.
        target_agent: Agent template key that generated the payload.

    Returns:
        Parsed semantic report.

    Raises:
        NotImplementedError: Always raised in Phase 0 scaffolding.
    """
    raise NotImplementedError(SEMANTIC_STUB_MESSAGE)
