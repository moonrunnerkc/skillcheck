"""Prompt template for agent self-critique of a SKILL.md file."""

from __future__ import annotations

from skillcheck.parser import ParsedSkill

# Increment when the expected JSON schema changes so agents know
# the contract version they are implementing against.
SCHEMA_VERSION = "1.0"

_WORKED_EXAMPLE = """\
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
}\
"""

_PROMPT_TEMPLATE = """\
You are evaluating a SKILL.md file. Your task is to assess it from the \
perspective of an agent that would receive and execute these instructions.

Read the skill below. Then respond with a single JSON object. Your response \
must be only that JSON object. No preamble, no explanation, no markdown \
formatting. Begin with {{ and end with }}.

skillcheck will parse your response mechanically. Any deviation from the \
required schema (extra fields, missing required fields, wrong types, scores \
outside 0-100) will cause skillcheck to reject the response entirely. There \
is no partial credit. Match the schema exactly.

Required JSON schema (schema version {schema_version}):

{{
  "clarity_score": <integer 0-100>,
  "completeness_score": <integer 0-100>,
  "executability_score": <integer 0-100>,
  "findings": [
    {{
      "section": <string, name of the skill section being critiqued>,
      "issue": <string, what is wrong>,
      "severity": <string, one of "error", "warning", "info">,
      "suggestion": <string, concrete corrective action>
    }}
  ],
  "missing_context": [<string>, ...],
  "contradictions": [
    {{
      "location_a": <string, first contradicting location>,
      "location_b": <string, second contradicting location>,
      "nature": <string, explanation of the contradiction>
    }}
  ]
}}

Score definitions:
  clarity_score: How clearly the skill communicates what it does, when to use \
it, and what the caller should expect. 100 means an agent could not \
misinterpret the instructions.
  completeness_score: Whether all information needed for execution is present. \
100 means no external assumptions are required.
  executability_score: Whether an agent can act on the instructions as written \
without ambiguity or missing steps. 100 means a new agent with no prior \
context could execute the skill correctly on first attempt.

findings is a list of specific issues found in named sections. Empty list \
is valid if no issues exist.
missing_context lists what an agent would need to execute the skill that the \
skill does not provide. Empty list is valid.
contradictions lists pairs of locations within the skill that contradict each \
other. Empty list is valid.

Worked example of a valid response:

{worked_example}

SKILL.md to evaluate:

{skill_text}\
"""


class SelfCritiquePrompt:
    """Renders the agent self-critique prompt for a given skill.

    This class is stateless. All state needed for rendering comes from the
    ParsedSkill argument passed to render(). Agent-specific subclasses may
    override render() to adjust phrasing while keeping the schema contract
    identical.
    """

    def render(self, skill: ParsedSkill) -> str:
        """Return the prompt text that an agent should evaluate and respond to.

        The rendered string contains the full skill text, the JSON schema the
        agent must follow, and a worked example. The schema version is embedded
        so responses can be validated against the version that was in effect
        when the prompt was generated.

        Args:
            skill: Parsed skill to critique.

        Returns:
            Plain-text prompt. No markdown. No ANSI codes.
        """
        return _PROMPT_TEMPLATE.format(
            schema_version=SCHEMA_VERSION,
            worked_example=_WORKED_EXAMPLE,
            skill_text=skill.raw_text.strip(),
        )
