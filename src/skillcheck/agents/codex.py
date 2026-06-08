"""Codex-specific self-critique prompt.

Framing basis: OpenAI's prompt engineering guidance favors concise, direct
system prompts with minimal structural markup. Codex (and GPT-4-class models
in API contexts) respond well to markdown-style section headers and a single
explicit output instruction at the end of the prompt. Verbose XML tagging
adds token cost without measurable accuracy improvement for these models.

Differences from the Claude variant:
- No XML tags. Section boundaries are markdown headers (### Skill, ### Schema).
- Full worked example included but compact (one JSON block, same object as
  the claude variant -- not shortened -- because example fidelity matters more
  than token savings for Codex; cursor handles compression).
- Single "Output only the JSON object." line at the end instead of bracketing.
"""

from __future__ import annotations

from skillcheck.agents.base import (
    SCHEMA_VERSION,
    SelfCritiquePrompt,
    schema_reference,
    worked_example,
)
from skillcheck.parser import ParsedSkill


class CodexPrompt(SelfCritiquePrompt):
    """Codex-variant self-critique prompt.

    Overrides render() with markdown-header structure and no XML tags, per
    OpenAI prompting guidance.
    """

    AGENT_ID: str = "codex"

    def render(self, skill: ParsedSkill) -> str:
        """Return the Codex-variant self-critique prompt for a given skill.

        Args:
            skill: Parsed skill to critique.

        Returns:
            Plain-text prompt suitable for Codex and GPT-4-class API models.
        """
        schema = schema_reference().format(schema_version=SCHEMA_VERSION)
        return (
            "Evaluate the SKILL.md below. Assess it from the perspective of an agent "
            "that would receive and execute these instructions.\n\n"
            "### Schema\n\n"
            + schema
            + "\n\n"
            "### Worked example\n\n"
            + worked_example()
            + "\n\n"
            "skillcheck parses your response mechanically. Extra fields, missing "
            "required fields, wrong types, or scores outside 0-100 cause the response "
            "to be rejected. Match the schema exactly.\n\n"
            "### Skill\n\n"
            + skill.raw_text.strip()
            + "\n\n"
            "Output only the JSON object. Do not include explanations or markdown fencing."
        )
