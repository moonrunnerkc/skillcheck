from __future__ import annotations

from skillcheck.agents.base import SelfCritiqueTemplate
from skillcheck.agents.claude import ClaudeTemplate
from skillcheck.agents.codex import CodexTemplate
from skillcheck.agents.cursor import CursorTemplate

__all__ = [
    "SelfCritiqueTemplate",
    "ClaudeTemplate",
    "CodexTemplate",
    "CursorTemplate",
]
