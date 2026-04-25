"""Interfaces for agent-specific self-critique prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class SelfCritiqueTemplate(Protocol):
    """Protocol for agent-native self-critique prompt templates."""

    @property
    def agent_name(self) -> str:
        """Return the stable identifier for the target agent."""

    def build_prompt(self, skill_path: Path, skill_text: str) -> str:
        """Return the critique prompt text for the provided skill."""

    def validate_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize an agent response payload."""
