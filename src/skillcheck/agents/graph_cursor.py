"""Cursor-specific graph-extraction prompt.

Framing basis: Cursor operates in an editor-integrated agent mode where the
effective context window available to a single tool call is meaningfully smaller
than a full API call. Cursor's documentation and community reports confirm that
shorter system instructions reliably fire while longer ones risk truncation or
lower instruction-following quality.

Differences from the Claude variant:
- No XML tags, no markdown headers.
- Single-paragraph task framing.
- Schema described as a compact pseudo-type signature instead of the full prose
  description (compact_graph_schema_signature).
- No worked example (the biggest single token reduction).
- One bare instruction line at the end.

Net effect: approximately 45% fewer characters vs the Claude variant for the
same skill body, attributable to schema description compression and example removal.
"""

from __future__ import annotations

from skillcheck.agents.graph_base import (
    GRAPH_SCHEMA_VERSION,
    GraphExtractionPrompt,
    compact_graph_schema_signature,
)
from skillcheck.parser import ParsedSkill


class CursorGraphPrompt(GraphExtractionPrompt):
    """Cursor-variant graph-extraction prompt.

    Overrides render() with a compact, token-efficient framing designed for
    Cursor's editor-integrated agent context budget.
    """

    AGENT_ID: str = "cursor"

    def render(self, skill: ParsedSkill) -> str:
        """Return the Cursor-variant graph-extraction prompt for a given skill.

        More compact than the Claude or Codex variants. No worked example.
        Schema is a tight inline type signature.

        Args:
            skill: Parsed skill to extract a capability graph from.

        Returns:
            Plain-text prompt optimized for Cursor's constrained context budget.
        """
        compact = compact_graph_schema_signature().format(
            schema_version=GRAPH_SCHEMA_VERSION
        )
        return (
            "Extract a capability graph from this SKILL.md. "
            "Identify capabilities, inputs each requires, and outputs each produces.\n\n"
            + compact
            + "\n\nSKILL.md:\n\n"
            + skill.raw_text.strip()
            + "\n\nOutput only the JSON object."
        )
