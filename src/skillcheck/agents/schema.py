"""Typed schema for agent self-critique responses.

Every field here is part of the contract between skillcheck and any calling
agent. The agent returns JSON; skillcheck validates it against this schema and
constructs these objects. If the schema changes, bump the version string in
SelfCritiquePrompt and update the parser.
"""

from __future__ import annotations

from dataclasses import dataclass

from skillcheck.result import Severity


def _check_score(name: str, value: int) -> int:
    """Validate a 0-100 integer score, returning it if valid.

    Args:
        name: Field name for error messages.
        value: Score value to validate.

    Returns:
        The value unchanged if 0 <= value <= 100.

    Raises:
        ValueError: If value is outside [0, 100], including the offending value.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"Field '{name}' must be int 0-100, got {type(value).__name__}: {value!r}"
        )
    if value < 0 or value > 100:
        raise ValueError(
            f"Field '{name}' must be in range 0-100, got: {value}"
        )
    return value


@dataclass(frozen=True)
class CritiqueFinding:
    """One structured finding from the agent's per-section review.

    Attributes:
        section: Name or heading of the skill section being critiqued.
        issue: Short description of what the agent found problematic.
        severity: Reuses the existing Severity enum (error, warning, info).
        suggestion: Concrete corrective action the agent recommends.
    """

    section: str
    issue: str
    severity: Severity
    suggestion: str

    def __post_init__(self) -> None:
        if not isinstance(self.severity, Severity):
            raise ValueError(
                f"Field 'severity' must be a Severity enum value, got: {self.severity!r}"
            )


@dataclass(frozen=True)
class Contradiction:
    """A detected logical contradiction within the skill body.

    Attributes:
        location_a: Description or excerpt of the first contradicting location.
        location_b: Description or excerpt of the second contradicting location.
        nature: Short explanation of what makes these two locations contradictory.
    """

    location_a: str
    location_b: str
    nature: str


@dataclass(frozen=True)
class SemanticCritique:
    """Full structured output of an agent self-critique run.

    Score fields (clarity_score, completeness_score, executability_score) are
    integers in [0, 100]. Construction raises ValueError for out-of-range values
    so callers cannot silently ignore bad data.

    Attributes:
        clarity_score: How clearly the skill states what it does and when (0-100).
        completeness_score: Whether all necessary context is present for execution (0-100).
        executability_score: Whether an agent can act on the instructions as written (0-100).
        findings: Per-section structured critique items.
        missing_context: Names of things an agent would need but the skill omits.
        contradictions: Pairs of contradicting locations within the skill body.
    """

    clarity_score: int
    completeness_score: int
    executability_score: int
    findings: tuple[CritiqueFinding, ...]
    missing_context: tuple[str, ...]
    contradictions: tuple[Contradiction, ...]

    def __post_init__(self) -> None:
        _check_score("clarity_score", self.clarity_score)
        _check_score("completeness_score", self.completeness_score)
        _check_score("executability_score", self.executability_score)
