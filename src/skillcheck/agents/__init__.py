"""Agent prompt registry for self-critique and graph extraction.

Prompt variants are based on each agent vendor's published prompting guidance
and observable context-budget behavior. Empirical comparison of prompt quality
across agents is a Phase 3+ activity. If you have data showing a different
framing produces better results for a given agent, file an issue.

The JSON schemas and parsers (Phase 1A for self-critique, Phase 2C for graph
extraction) are invariant across agents. Only the prompt framing changes.
"""

from __future__ import annotations

from skillcheck.agents.base import SelfCritiquePrompt
from skillcheck.agents.claude import ClaudePrompt
from skillcheck.agents.codex import CodexPrompt
from skillcheck.agents.cursor import CursorPrompt
from skillcheck.agents.graph_base import GraphExtractionPrompt
from skillcheck.agents.graph_claude import ClaudeGraphPrompt
from skillcheck.agents.graph_codex import CodexGraphPrompt
from skillcheck.agents.graph_cursor import CursorGraphPrompt

AGENTS: dict[str, type[SelfCritiquePrompt]] = {
    "claude": ClaudePrompt,
    "codex": CodexPrompt,
    "cursor": CursorPrompt,
}

GRAPH_AGENTS: dict[str, type[GraphExtractionPrompt]] = {
    "claude": ClaudeGraphPrompt,
    "codex": CodexGraphPrompt,
    "cursor": CursorGraphPrompt,
}

_VALID_IDS = sorted(AGENTS)
_VALID_GRAPH_IDS = sorted(GRAPH_AGENTS)


def get_agent_prompt(agent_id: str) -> SelfCritiquePrompt:
    """Return a self-critique prompt instance for the given agent ID.

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


def get_graph_prompt(agent_id: str) -> GraphExtractionPrompt:
    """Return a graph-extraction prompt instance for the given agent ID.

    Args:
        agent_id: One of "claude", "codex", or "cursor".

    Returns:
        Instantiated prompt object whose render() method produces the
        agent-appropriate graph-extraction prompt.

    Raises:
        ValueError: If agent_id is not a known graph agent. Message includes
            the offending value and the list of valid IDs.
    """
    cls = GRAPH_AGENTS.get(agent_id)
    if cls is None:
        raise ValueError(
            f"Unknown graph agent: '{agent_id}'. "
            f"Valid values: {', '.join(_VALID_GRAPH_IDS)}"
        )
    return cls()


__all__ = [
    "SelfCritiquePrompt",
    "ClaudePrompt",
    "CodexPrompt",
    "CursorPrompt",
    "AGENTS",
    "get_agent_prompt",
    "GraphExtractionPrompt",
    "ClaudeGraphPrompt",
    "CodexGraphPrompt",
    "CursorGraphPrompt",
    "GRAPH_AGENTS",
    "get_graph_prompt",
]
