"""Agent self-critique prompt registry.

Prompt variants are based on each agent vendor's published prompting guidance
and observable context-budget behavior. Empirical comparison of critique quality
across agents is a Phase 2+ activity. If you have data showing a different
framing produces better critiques for a given agent, file an issue.

The JSON schema and parser (Phase 1A) are invariant across agents. Only the
prompt framing changes. Responses from all three agents pass through the same
parse_critique_response() pipeline.
"""

from __future__ import annotations

from skillcheck.agents.base import SelfCritiquePrompt
from skillcheck.agents.claude import ClaudePrompt
from skillcheck.agents.codex import CodexPrompt
from skillcheck.agents.cursor import CursorPrompt

AGENTS: dict[str, type[SelfCritiquePrompt]] = {
    "claude": ClaudePrompt,
    "codex": CodexPrompt,
    "cursor": CursorPrompt,
}

_VALID_IDS = sorted(AGENTS)


def get_agent_prompt(agent_id: str) -> SelfCritiquePrompt:
    """Return a prompt instance for the given agent ID.

    Args:
        agent_id: One of "claude", "codex", or "cursor".

    Returns:
        Instantiated prompt object whose render() method produces the
        agent-appropriate self-critique prompt.

    Raises:
        ValueError: If agent_id is not a known agent. Message includes the
            offending value and the list of valid IDs.
    """
    cls = AGENTS.get(agent_id)
    if cls is None:
        raise ValueError(
            f"Unknown critique agent: '{agent_id}'. "
            f"Valid values: {', '.join(_VALID_IDS)}"
        )
    return cls()


__all__ = [
    "SelfCritiquePrompt",
    "ClaudePrompt",
    "CodexPrompt",
    "CursorPrompt",
    "AGENTS",
    "get_agent_prompt",
]
