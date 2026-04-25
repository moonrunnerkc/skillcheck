"""Claude-specific self-critique prompt template stub for v1.0."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillcheck.agents.base import SelfCritiqueTemplate


class ClaudeTemplate(SelfCritiqueTemplate):
    """Stub template for Claude-specific semantic critique prompts."""

    @property
    def agent_name(self) -> str:
        raise NotImplementedError("Claude template lands in v1.0.")

    def build_prompt(self, skill_path: Path, skill_text: str) -> str:
        raise NotImplementedError("Claude template lands in v1.0.")

    def validate_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Claude template lands in v1.0.")
