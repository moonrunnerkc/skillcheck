"""Cursor-specific self-critique prompt.

Framing basis: Cursor operates in an editor-integrated agent mode where the
effective context window available to a single tool call is meaningfully
smaller than a full API call -- often 8k-16k tokens in practice, partly
consumed by workspace context, open file contents, and conversation history.
Cursor's documentation and community reports confirm that shorter system
instructions reliably fire while longer ones risk truncation or lower
instruction-following quality.

Differences from the Claude variant:
- No XML tags, no markdown headers.
- Single-paragraph task framing instead of role-setting preamble.
- Schema described as a compact pseudo-type signature (compact_schema_signature)
  instead of the full prose description.
- No worked example (biggest single token reduction -- the example is ~250 tokens).
- One bare instruction line at the end.

Net effect: approximately 40% fewer characters vs the Claude variant for the
same skill body, attributable entirely to schema description and example removal.
This estimate holds for skills up to ~300 tokens; shorter skills shift the ratio
because fixed overhead dominates.
"""

from __future__ import annotations

from skillcheck.agents.base import (
    SCHEMA_VERSION,
    SelfCritiquePrompt,
    compact_schema_signature,
)
from skillcheck.parser import ParsedSkill


class CursorPrompt(SelfCritiquePrompt):
    """Cursor-variant self-critique prompt.

    Overrides render() with a compact, token-efficient framing designed for
    Cursor's editor-integrated agent context budget.
    """

    AGENT_ID: str = "cursor"

    def render(self, skill: ParsedSkill) -> str:
        """Return the Cursor-variant self-critique prompt for a given skill.

        More compact than the Claude or Codex variants. No worked example.
        Schema is a tight inline type signature.

        Args:
            skill: Parsed skill to critique.

        Returns:
            Plain-text prompt optimized for Cursor's constrained context budget.
        """
        compact = compact_schema_signature().format(schema_version=SCHEMA_VERSION)
        return (
            "Critique this SKILL.md from the perspective of an agent executing it. "
            "Score clarity, completeness, and executability 0-100. List any findings, "
            "missing context items, and contradictions.\n\n"
            + compact
            + "\n\nSKILL.md:\n\n"
            + skill.raw_text.strip()
            + "\n\nOutput only the JSON object."
        )
