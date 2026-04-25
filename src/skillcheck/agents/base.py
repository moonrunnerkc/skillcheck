"""Base class and shared utilities for agent self-critique prompt templates.

All shared rendering helpers live here. Agent subclasses (claude, codex, cursor)
call these directly rather than duplicating logic, so schema descriptions and
worked examples stay in sync across variants.
"""

from __future__ import annotations

from skillcheck.parser import ParsedSkill

# Increment when the expected JSON schema changes so downstream agents know
# which contract version they are implementing against.
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Shared content blocks (called by subclasses, not rendered directly)
# ---------------------------------------------------------------------------

_WORKED_EXAMPLE_BODY = """\
{
  "clarity_score": 72,
  "completeness_score": 58,
  "executability_score": 81,
  "findings": [
    {
      "section": "Overview",
      "issue": "The description says the skill 'helps with documents' but does not say which document formats are supported.",
      "severity": "warning",
      "suggestion": "List the supported formats explicitly, for example: PDF, DOCX, and plain text."
    },
    {
      "section": "Capabilities",
      "issue": "The word 'analyze' appears without specifying what analysis produces or what the caller receives.",
      "severity": "error",
      "suggestion": "State the output: structured JSON, a summary string, or a list of extracted fields."
    }
  ],
  "missing_context": [
    "Maximum file size the skill can handle",
    "Whether the skill requires the file to be local or accepts URLs"
  ],
  "contradictions": [
    {
      "location_a": "Overview: 'works offline with no external services'",
      "location_b": "Capabilities: 'fetches metadata from the document registry API'",
      "nature": "Claiming offline operation while also claiming network API access is contradictory."
    }
  ]
}"""

_SCHEMA_DESCRIPTION = """\
Required JSON schema (schema version {schema_version}):

  clarity_score: integer 0-100 -- how clearly the skill communicates what it does, when to use it, and what the caller should expect. 100 means unambiguous.
  completeness_score: integer 0-100 -- whether all information needed for execution is present. 100 means no external assumptions required.
  executability_score: integer 0-100 -- whether an agent can act on the instructions as written without ambiguity. 100 means a new agent could execute correctly on first attempt.
  findings: list of objects, each with:
    section (string): name of the skill section being critiqued
    issue (string): what is wrong
    severity (string): one of "error", "warning", "info"
    suggestion (string): concrete corrective action
  missing_context: list of strings -- what an agent would need that the skill does not provide
  contradictions: list of objects, each with:
    location_a (string): first contradicting location
    location_b (string): second contradicting location
    nature (string): explanation of the contradiction

Empty lists are valid for findings, missing_context, and contradictions.\
"""

_COMPACT_TYPE_SIGNATURE = """\
JSON response shape (schema version {schema_version}):
{{
  "clarity_score": int(0-100),
  "completeness_score": int(0-100),
  "executability_score": int(0-100),
  "findings": [{{"section": str, "issue": str, "severity": "error"|"warning"|"info", "suggestion": str}}],
  "missing_context": [str],
  "contradictions": [{{"location_a": str, "location_b": str, "nature": str}}]
}}\
"""


def schema_reference() -> str:
    """Return the prose schema description block used by claude and codex variants.

    The returned string contains a {schema_version} placeholder that the caller
    must format before use.

    Returns:
        Multi-line string describing every field, type, and score definition.
    """
    return _SCHEMA_DESCRIPTION


def worked_example() -> str:
    """Return the full worked example JSON string used by claude and codex variants.

    The example is a valid SemanticCritique response that passes through
    parse_critique_response from the Phase 1A parser. Callers should embed it
    verbatim in the prompt.

    Returns:
        JSON string of a valid SemanticCritique response.
    """
    return _WORKED_EXAMPLE_BODY


def compact_schema_signature() -> str:
    """Return the compact inline type signature used by the cursor variant.

    Approximately 60% the token count of schema_reference(). No worked example.
    The returned string contains a {schema_version} placeholder that the caller
    must format before use.

    Returns:
        Compact schema as a pseudo-type signature string.
    """
    return _COMPACT_TYPE_SIGNATURE


class SelfCritiquePrompt:
    """Base prompt template for agent self-critique of a SKILL.md file.

    Stateless. All rendering state comes from the ParsedSkill passed to
    render(). The base class renders the Claude variant. Agent-specific
    subclasses override render() to adjust framing for their target agent's
    documented preferences while the JSON schema contract (Phase 1A) remains
    invariant across all agents.
    """

    AGENT_ID: str = "claude"

    def render(self, skill: ParsedSkill) -> str:
        """Return the Claude-variant self-critique prompt for a given skill.

        Framing rationale (Anthropic prompt engineering guidance):
        - XML tags for structural sections (<skill_to_critique>, <response_schema>,
          <worked_example>) allow Claude to locate each block unambiguously even
          in long contexts.
        - Explicit bracketing: the "respond only with JSON" instruction appears
          at both the beginning and end of the prompt. Claude is documented to
          follow instructions reliably when they appear at both positions.
        - Full worked example included to anchor the expected format.

        Args:
            skill: Parsed skill to critique.

        Returns:
            Plain-text prompt ready for Claude Code, Claude.ai, or the API.
        """
        schema = schema_reference().format(schema_version=SCHEMA_VERSION)
        return (
            "You are evaluating a SKILL.md file. Your task is to assess it from the "
            "perspective of an agent that would receive and execute these instructions. "
            "Respond only with the JSON object described below. No preamble, no postamble.\n\n"
            "<response_schema>\n"
            + schema
            + "\n</response_schema>\n\n"
            "<worked_example>\n"
            + worked_example()
            + "\n</worked_example>\n\n"
            "skillcheck will parse your response mechanically. Extra fields, missing "
            "required fields, wrong types, or scores outside 0-100 will cause the "
            "response to be rejected entirely. Match the schema exactly.\n\n"
            "<skill_to_critique>\n"
            + skill.raw_text.strip()
            + "\n</skill_to_critique>\n\n"
            "Respond only with the JSON object. Begin with { and end with }."
        )
