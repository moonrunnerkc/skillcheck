"""Claude-specific graph-extraction prompt.

The base GraphExtractionPrompt class already implements the Claude variant.
This module exists as a concrete, named subclass so the agent registry can
reference it explicitly and tests can verify AGENT_ID.

Framing basis: Anthropic prompt engineering documentation recommends XML tags
for structuring non-trivial inputs, explicit role framing, bracketing
instructions at start and end, and full worked examples for format-sensitive
tasks. All four techniques are applied in the base class render().
"""

from __future__ import annotations

from skillcheck.agents.graph_base import GraphExtractionPrompt


class ClaudeGraphPrompt(GraphExtractionPrompt):
    """Claude-variant graph-extraction prompt.

    Inherits render() from GraphExtractionPrompt (that method IS the Claude
    variant). Defined here so the registry maps "claude" to this class.
    """

    AGENT_ID: str = "claude"
