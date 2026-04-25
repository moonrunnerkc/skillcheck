"""Claude-specific self-critique prompt.

The base SelfCritiquePrompt class already implements the Claude variant.
This module exists as a concrete, named subclass so the agent registry can
reference it explicitly and tests can verify AGENT_ID.

Framing basis: Anthropic's prompt engineering documentation recommends XML
tags for structuring non-trivial inputs, explicit role framing, bracketing
instructions at start and end, and full worked examples for format-sensitive
tasks. All four techniques are applied in the base class render().
"""

from __future__ import annotations

from skillcheck.agents.base import SelfCritiquePrompt
from skillcheck.parser import ParsedSkill


class ClaudePrompt(SelfCritiquePrompt):
    """Claude-variant self-critique prompt.

    Inherits render() from SelfCritiquePrompt (that method IS the Claude
    variant). Defined here so the registry maps "claude" to this class.
    """

    AGENT_ID: str = "claude"
