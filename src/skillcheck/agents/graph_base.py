"""Base class and shared utilities for agent graph-extraction prompt templates.

Parallel to agents/base.py (critique prompts). Agent subclasses for graph
extraction call these shared helpers directly so schema descriptions and worked
examples stay in sync across prompt variants.

Prompt variants are based on vendor guidance and observable context behavior.
Empirical comparison of extraction quality across agents is a Phase 3+ activity.
If you have data showing a different framing produces better graphs for a given
agent, file an issue with extraction comparisons attached.
"""

from __future__ import annotations

from skillcheck.parser import ParsedSkill

# Increment when the expected JSON schema changes.
GRAPH_SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Shared content blocks
# ---------------------------------------------------------------------------

_GRAPH_SCHEMA_DESCRIPTION = """\
Required JSON schema (graph schema version {schema_version}):

  capabilities: list of objects, each with:
    id (string): stable identifier, unique across all node collections in this response
    name (string): heading text or descriptive name of the capability
    description (string): first explanatory sentence from the section body, or empty string
    line (integer or null): body-relative line number (1-indexed from the first line after
      the closing ---; does not count frontmatter lines); null for synthesized nodes

  inputs: list of objects, each with:
    id (string): stable identifier, unique across all node collections in this response
    name (string): canonical name of the input
    kind (string): one of "file", "tool", "env", "context", "prerequisite"
    line (integer or null): body-relative line number, or null

  outputs: list of objects, each with:
    id (string): stable identifier, unique across all node collections in this response
    name (string): canonical name of the output
    kind (string): one of "file", "artifact", "side_effect", "return"
    line (integer or null): body-relative line number, or null

  edges: list of objects, each with:
    source_id (string): id of a capability in this response
    target_id (string): id of an input (for kind="requires") or an output (for kind="produces")
    kind (string): one of "requires", "produces"

Line numbering: line 1 is the first line of the skill body (the first line after
the closing ---). Frontmatter lines are not counted.

ID uniqueness: every id value must be unique across capabilities, inputs, and outputs
combined. skillcheck will reject the response if any id appears in more than one collection.

Edge integrity: source_id must reference a capability id; for kind="requires" the
target_id must reference an input id; for kind="produces" the target_id must reference
an output id. Dangling references will cause the response to be rejected.

Empty lists are valid for any collection.\
"""

_GRAPH_WORKED_EXAMPLE = """\
{
  "capabilities": [
    {
      "id": "cap_generate_report",
      "name": "Generate report",
      "description": "Connects via db_client and writes results to report.json.",
      "line": 8
    }
  ],
  "inputs": [
    {
      "id": "inp_db_client",
      "name": "db_client",
      "kind": "tool",
      "line": 4
    },
    {
      "id": "inp_db_url",
      "name": "DB_URL",
      "kind": "env",
      "line": 5
    },
    {
      "id": "inp_schema_sql",
      "name": "schema.sql",
      "kind": "file",
      "line": 6
    }
  ],
  "outputs": [
    {
      "id": "out_report_json",
      "name": "report.json",
      "kind": "file",
      "line": 14
    },
    {
      "id": "out_exec_summary",
      "name": "execution summary",
      "kind": "artifact",
      "line": 15
    }
  ],
  "edges": [
    {"source_id": "cap_generate_report", "target_id": "inp_db_client", "kind": "requires"},
    {"source_id": "cap_generate_report", "target_id": "inp_db_url", "kind": "requires"},
    {"source_id": "cap_generate_report", "target_id": "inp_schema_sql", "kind": "requires"},
    {"source_id": "cap_generate_report", "target_id": "out_report_json", "kind": "produces"},
    {"source_id": "cap_generate_report", "target_id": "out_exec_summary", "kind": "produces"}
  ]
}\
"""

_COMPACT_GRAPH_TYPE_SIGNATURE = """\
JSON response shape (graph schema version {schema_version}):
{{
  "capabilities": [{{"id": str, "name": str, "description": str, "line": int|null}}],
  "inputs": [{{"id": str, "name": str, "kind": "file"|"tool"|"env"|"context"|"prerequisite", "line": int|null}}],
  "outputs": [{{"id": str, "name": str, "kind": "file"|"artifact"|"side_effect"|"return", "line": int|null}}],
  "edges": [{{"source_id": str, "target_id": str, "kind": "requires"|"produces"}}]
}}
IDs must be unique across capabilities+inputs+outputs. source_id -> capability id;
target_id -> input id for requires, output id for produces.
Line numbers are body-relative (1-indexed after closing ---).\
"""


def graph_schema_reference() -> str:
    """Return the prose graph schema description block used by claude and codex variants.

    The returned string contains a {schema_version} placeholder that the caller
    must format before use.

    Returns:
        Multi-line string describing every field, type, and constraint.
    """
    return _GRAPH_SCHEMA_DESCRIPTION


def graph_worked_example() -> str:
    """Return the full worked example JSON used by claude and codex variants.

    The example is a valid graph response that passes through parse_graph_response.
    Based on the skill_basic_io.md fixture so the worked example and the test
    fixture are consistent. Callers embed this verbatim in the prompt.

    Returns:
        JSON string of a valid graph extraction response.
    """
    return _GRAPH_WORKED_EXAMPLE


def compact_graph_schema_signature() -> str:
    """Return the compact inline type signature used by the cursor variant.

    Approximately 55% the token count of graph_schema_reference(). No worked example.
    The returned string contains a {schema_version} placeholder that the caller
    must format before use.

    Returns:
        Compact schema as a pseudo-type signature string.
    """
    return _COMPACT_GRAPH_TYPE_SIGNATURE


class GraphExtractionPrompt:
    """Base prompt template for agent capability-graph extraction from a SKILL.md file.

    Stateless. All rendering state comes from the ParsedSkill passed to render().
    The base class renders the Claude variant. Agent-specific subclasses override
    render() to adjust framing while the JSON schema contract remains invariant.

    Parallel to SelfCritiquePrompt in agents/base.py.
    """

    AGENT_ID: str = "claude"

    def render(self, skill: ParsedSkill) -> str:
        """Return the Claude-variant graph-extraction prompt for a given skill.

        Framing rationale (Anthropic prompt engineering guidance):
        - XML tags for structural sections allow Claude to locate each block
          unambiguously in long contexts.
        - Explicit bracketing: the "respond only with JSON" instruction appears
          at both the beginning and end of the prompt.
        - Full worked example to anchor the expected format.

        Args:
            skill: Parsed skill to extract a capability graph from.

        Returns:
            Plain-text prompt ready for Claude Code, Claude.ai, or the API.
        """
        schema = graph_schema_reference().format(schema_version=GRAPH_SCHEMA_VERSION)
        return (
            "You are extracting a capability graph from a SKILL.md file. "
            "Identify the capabilities the skill provides, the inputs each capability "
            "requires, and the outputs each capability produces. "
            "Respond only with the JSON object described below. No preamble, no postamble.\n\n"
            "<response_schema>\n"
            + schema
            + "\n</response_schema>\n\n"
            "<worked_example>\n"
            + graph_worked_example()
            + "\n</worked_example>\n\n"
            "skillcheck will parse your response mechanically. Extra fields, missing "
            "required fields, wrong types, duplicate IDs across collections, or dangling "
            "edge references will cause the response to be rejected entirely. "
            "Match the schema exactly.\n\n"
            "<skill_to_analyze>\n"
            + skill.raw_text.strip()
            + "\n</skill_to_analyze>\n\n"
            "Respond only with the JSON object. Begin with { and end with }."
        )
