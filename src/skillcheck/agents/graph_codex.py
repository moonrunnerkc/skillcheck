"""Codex-specific graph-extraction prompt.

Framing basis: OpenAI prompt engineering guidance favors concise, direct system
prompts with minimal structural markup. Codex and GPT-4-class models in API
contexts respond well to markdown-style section headers and a single explicit
output instruction at the end. Verbose XML tagging adds token cost without
measurable accuracy improvement for these models.

Differences from the Claude variant:
- No XML tags. Section boundaries are markdown headers (### Schema, ### Skill).
- Full worked example included (same JSON as the claude variant; example fidelity
  matters more than token savings for Codex; cursor handles compression).
- Single "Output only the JSON object." line at the end instead of bracketing.
"""

from __future__ import annotations

from skillcheck.agents.graph_base import (
    GRAPH_SCHEMA_VERSION,
    GraphExtractionPrompt,
    graph_schema_reference,
    graph_worked_example,
)
from skillcheck.parser import ParsedSkill


class CodexGraphPrompt(GraphExtractionPrompt):
    """Codex-variant graph-extraction prompt.

    Overrides render() with markdown-header structure and no XML tags, per
    OpenAI prompting guidance.
    """

    AGENT_ID: str = "codex"

    def render(self, skill: ParsedSkill) -> str:
        """Return the Codex-variant graph-extraction prompt for a given skill.

        Args:
            skill: Parsed skill to extract a capability graph from.

        Returns:
            Plain-text prompt suitable for Codex and GPT-4-class API models.
        """
        schema = graph_schema_reference().format(schema_version=GRAPH_SCHEMA_VERSION)
        return (
            "Extract a capability graph from the SKILL.md below. "
            "Identify capabilities, their required inputs, and their produced outputs.\n\n"
            "### Schema\n\n"
            + schema
            + "\n\n"
            "### Worked example\n\n"
            + graph_worked_example()
            + "\n\n"
            "skillcheck parses your response mechanically. Extra fields, missing "
            "required fields, wrong types, duplicate IDs, or dangling edge references "
            "cause the response to be rejected. Match the schema exactly.\n\n"
            "### Skill\n\n"
            + skill.raw_text.strip()
            + "\n\n"
            "Output only the JSON object. Do not include explanations or markdown fencing."
        )
