from __future__ import annotations

from skillcheck.agents.base import SelfCritiquePrompt
from skillcheck.agents.claude import ClaudeTemplate
from skillcheck.agents.codex import CodexTemplate
from skillcheck.agents.cursor import CursorTemplate

__all__ = [
    "SelfCritiquePrompt",
    "ClaudeTemplate",
    "CodexTemplate",
    "CursorTemplate",
]
