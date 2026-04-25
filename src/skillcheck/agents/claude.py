"""Claude-specific agent configuration for self-critique prompts."""

from __future__ import annotations

from skillcheck.agents.base import SelfCritiquePrompt


class ClaudeTemplate:
    """Claude configuration for the self-critique workflow.

    Returns the base SelfCritiquePrompt because Claude follows the
    generic schema without dialect-specific adjustments. This class
    exists so Phase 1B can add Claude-specific tuning here without
    restructuring callers.
    """

    @staticmethod
    def prompt_class() -> type[SelfCritiquePrompt]:
        """Return the prompt class to use for Claude."""
        return SelfCritiquePrompt
