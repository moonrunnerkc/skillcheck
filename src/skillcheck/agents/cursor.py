"""Cursor-specific agent configuration for self-critique prompts."""

from __future__ import annotations

from skillcheck.agents.base import SelfCritiquePrompt


class CursorTemplate:
    """Cursor configuration for the self-critique workflow.

    Returns the base SelfCritiquePrompt. Cursor follows the generic schema
    without dialect-specific adjustments in this phase. This class exists so
    Phase 1B can add Cursor-specific tuning without restructuring callers.
    """

    @staticmethod
    def prompt_class() -> type[SelfCritiquePrompt]:
        """Return the prompt class to use for Cursor."""
        return SelfCritiquePrompt
