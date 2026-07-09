"""Capability graph data model and heuristic extractor for skillcheck.

IMPERATIVE_VERBS, INPUT_SECTION_ALIASES, and OUTPUT_SECTION_ALIASES are
conservative by design. The agent-mode extractor (Phase 2C) handles the long
tail via semantic matching; the heuristic here errs toward precision over recall.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from skillcheck.parser import ParsedSkill

# ---------------------------------------------------------------------------
# Classification constants (module-level, frozen tuples, sorted alphabetically)
# ---------------------------------------------------------------------------

IMPERATIVE_VERBS: tuple[str, ...] = (
    "analyze",
    "build",
    "check",
    "compile",
    "configure",
    "convert",
    "create",
    "define",
    "describe",
    "design",
    "document",
    "evaluate",
    "explain",
    "extract",
    "find",
    "format",
    "generate",
    "identify",
    "implement",
    "install",
    "list",
    "parse",
    "plan",
    "render",
    "review",
    "run",
    "set",
    "setup",
    "study",
    "summarize",
    "test",
    "transform",
    "understand",
    "validate",
    "write",
)

# Section prefixes stripped from headings before imperative-verb classification.
# Matches "Phase 1:", "Phase 1 -", "Step 2.", "Section 3:", "1.", "2)",
# "1.1", "1.1.1 ", "1.2)" etc. Real-world skills use both flat and nested
# numbering (mcp-builder uses "#### 1.1 Understand...").  Conservative:
# strips a single leading section/numeric token plus its trailing delimiter
# or whitespace, leaving the rest of the heading intact for verb detection.
_SECTION_PREFIX_RE = re.compile(
    r"""
    ^\s*
    (?:
        (?:phase|step|section|part|chapter)\s+[\w\.]+\s*[:.\-]?\s+  # named section
        | \d+(?:\.\d+)*\s*[:.)\-]?\s+                               # numeric (incl. 1.1)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

INPUT_SECTION_ALIASES: tuple[str, ...] = (
    "before you start",
    "inputs",
    "prerequisites",
    "requirements",
    "setup",
)

OUTPUT_SECTION_ALIASES: tuple[str, ...] = (
    "output",
    "outputs",
    "produces",
    "result",
    "results",
    "returns",
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Capability:
    """A declared capability: something the skill can do."""

    id: str
    name: str
    description: str
    line: int | None


@dataclass(frozen=True)
class Input:
    """An input consumed by one or more capabilities."""

    id: str
    name: str
    kind: Literal["file", "tool", "env", "context", "prerequisite"]
    line: int | None


@dataclass(frozen=True)
class Output:
    """An output produced by one or more capabilities."""

    id: str
    name: str
    kind: Literal["file", "artifact", "side_effect", "return"]
    line: int | None


@dataclass(frozen=True)
class Edge:
    """Directed relationship between a capability and an input or output."""

    source_id: str
    target_id: str
    kind: Literal["requires", "produces"]


@dataclass(frozen=True)
class CapabilityGraph:
    """Complete capability graph for a single ParsedSkill.

    All fields are tuples to preserve hashability of the frozen dataclass.
    Constructed graphs are validated in __post_init__.
    """

    capabilities: tuple[Capability, ...]
    inputs: tuple[Input, ...]
    outputs: tuple[Output, ...]
    edges: tuple[Edge, ...]
    source: Literal["heuristic", "agent"]

    def __post_init__(self) -> None:
        capability_ids = {c.id for c in self.capabilities}
        input_ids = {i.id for i in self.inputs}
        output_ids = {o.id for o in self.outputs}

        # Duplicate ID check across all node collections.
        all_ids: list[str] = (
            [c.id for c in self.capabilities]
            + [i.id for i in self.inputs]
            + [o.id for o in self.outputs]
        )
        seen: set[str] = set()
        for nid in all_ids:
            if nid in seen:
                raise ValueError(
                    f"Duplicate node ID '{nid}' appears in multiple "
                    f"capability graph collections."
                )
            seen.add(nid)

        # Edge referential integrity.
        for edge in self.edges:
            if edge.source_id not in capability_ids:
                raise ValueError(
                    f"Edge source_id '{edge.source_id}' does not reference a known capability "
                    f"(edge: {edge.source_id!r} -[{edge.kind}]-> {edge.target_id!r})."
                )
            if edge.kind == "requires":
                if edge.target_id not in input_ids:
                    misrouted = "an output" if edge.target_id in output_ids else "unknown"
                    raise ValueError(
                        f"Edge kind='requires' has target_id '{edge.target_id}' which is not an "
                        f"input ID ({misrouted}). "
                        f"Edge: {edge.source_id!r} -[requires]-> {edge.target_id!r}."
                    )
            elif edge.kind == "produces":
                if edge.target_id not in output_ids:
                    misrouted = "an input" if edge.target_id in input_ids else "unknown"
                    raise ValueError(
                        f"Edge kind='produces' has target_id '{edge.target_id}' which is not an "
                        f"output ID ({misrouted}). "
                        f"Edge: {edge.source_id!r} -[produces]-> {edge.target_id!r}."
                    )


# ---------------------------------------------------------------------------
# ID generation: content-derived, deterministic, stable across runs
# ---------------------------------------------------------------------------


def _make_id(node_type: str, name: str, line: int | None) -> str:
    """Return an 8-hex-char ID derived from node_type, name, and line.

    Two calls with identical arguments always return the same value. No
    timestamps, no randomness.
    """
    raw = f"{node_type}:{name}:{line if line is not None else -1}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Private section-classification helpers (Phase 2C imports these by name)
# ---------------------------------------------------------------------------


def _normalize_heading(text: str) -> str:
    """Lower-case and strip non-alpha characters for alias matching."""
    return re.sub(r"[^a-z\s]", "", text.lower()).strip()


def _is_input_section_heading(text: str) -> bool:
    """Return True if heading text matches an input-section alias."""
    return _normalize_heading(text) in INPUT_SECTION_ALIASES


def _is_output_section_heading(text: str) -> bool:
    """Return True if heading text matches an output-section alias."""
    return _normalize_heading(text) in OUTPUT_SECTION_ALIASES


def _strip_section_prefix(text: str) -> str:
    """Strip a single leading section or numeric prefix.

    Real-world skills frequently nest imperative verbs inside section labels
    like "Phase 1: Implement Tools" or "2. Build the index". The verb-classifier
    needs the prefix removed so the first word seen is the actual verb.
    Returns the text unchanged when no recognized prefix is present.
    """
    return _SECTION_PREFIX_RE.sub("", text, count=1)


def _is_imperative_heading(text: str) -> bool:
    """Return True if the heading's first word is a known imperative verb.

    Section/numeric prefixes ("Phase 1:", "Step 2.", "1.") are stripped first
    so that headings like "Phase 1: Implement Tools" classify on "Implement".
    """
    stripped = _strip_section_prefix(text)
    first_word = stripped.lower().split()[0] if stripped.split() else ""
    return first_word in IMPERATIVE_VERBS


def _infer_input_kind(
    item_text: str,
) -> Literal["file", "tool", "env", "context", "prerequisite"]:
    """Infer Input.kind from a list-item text string.

    Checks in order: env (ALL_CAPS), file (extension or path), tool (backtick
    single-token), prerequisite (fallback).

    Args:
        item_text: Text of the list item after stripping the list marker.

    Returns:
        The inferred input kind.
    """
    name_raw = re.split(r"\s+[-:]\s+", item_text, maxsplit=1)[0].strip()
    name = name_raw.strip("`").strip()

    # env: ALL_CAPS with underscores/digits, at least 2 characters, no extension.
    if re.fullmatch(r"[A-Z][A-Z0-9_]{1,}", name) and "." not in name:
        return "env"

    # file: has a path separator or a recognizable file extension.
    if "/" in name or "\\" in name or re.search(r"\.\w{1,6}$", name):
        return "file"

    # tool: originally backtick-quoted and single-token (no spaces in name).
    if name_raw.startswith("`") and " " not in name:
        return "tool"

    return "prerequisite"


def _infer_output_kind(
    item_text: str,
) -> Literal["file", "artifact", "side_effect", "return"]:
    """Infer Output.kind from a list-item text string.

    Checks in order: file (extension or path), side_effect (mutating verb),
    return (short single-token), artifact (fallback).

    Args:
        item_text: Text of the list item after stripping the list marker.

    Returns:
        The inferred output kind.
    """
    name_raw = re.split(r"\s+[-:]\s+", item_text, maxsplit=1)[0].strip()
    name = name_raw.strip("`").strip()
    full = item_text.lower()

    # file: has a path separator or recognizable file extension.
    if "/" in name or "\\" in name or re.search(r"\.\w{1,6}$", name):
        return "file"

    # side_effect: description mentions a mutating verb.
    if re.search(r"\b(modif|updat|delet|overwrit|sends?\b|emit|writes?\b)", full):
        return "side_effect"

    # return: short single-token name (no spaces), value-shaped.
    if " " not in name and len(name) <= 30:
        return "return"

    return "artifact"


def extract_backtick_refs(text: str) -> list[str]:
    """Return all backtick-quoted strings found in text, in order.

    Args:
        text: Arbitrary markdown body text.

    Returns:
        Contents of each backtick span.
    """
    return re.findall(r"`([^`]+)`", text)


def _extract_list_item_name(item_text: str) -> str:
    """Return the canonical node name from a list item (description stripped)."""
    name_raw = re.split(r"\s+[-:]\s+", item_text, maxsplit=1)[0].strip()
    return name_raw.strip("`").strip()


def _get_list_item(line: str) -> str | None:
    """Return item text if the line is a list item, else None."""
    m = re.match(r"^\s*(?:-|\*|\d+\.)\s+(.*)", line)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# Body section parser
# ---------------------------------------------------------------------------


def _sectionize(
    body_lines: list[str],
) -> list[tuple[int, int, str, list[tuple[int, str]]]]:
    """Split body into sections.

    Each section is (start_line_1indexed, level, heading_text, content_lines).
    content_lines is [(line_num, text)] for every line between this heading
    and the next heading at the same or shallower level. Sub-headings are
    included in content so that nested list items are still harvested.

    Args:
        body_lines: Body of the skill as a list of line strings (no trailing newlines).

    Returns:
        List of section tuples in document order.
    """
    headings: list[tuple[int, int, str]] = []
    for i, line in enumerate(body_lines, 1):
        m = re.match(r"^(#+)\s+(.*)", line)
        if m:
            headings.append((i, len(m.group(1)), m.group(2).strip()))

    sections = []
    for idx, (line_num, level, text) in enumerate(headings):
        content_end = len(body_lines) + 1
        for j in range(idx + 1, len(headings)):
            if headings[j][1] <= level:
                content_end = headings[j][0]
                break
        content = [(i, body_lines[i - 1]) for i in range(line_num + 1, content_end)]
        sections.append((line_num, level, text, content))

    return sections


# ---------------------------------------------------------------------------
# Public extractor
# ---------------------------------------------------------------------------


def extract_graph_heuristic(skill: ParsedSkill) -> CapabilityGraph:
    """Extract a CapabilityGraph from a ParsedSkill using markdown heuristics.

    Pure function: no I/O, no randomness, no mutation after construction.
    Two calls with the same skill produce equal, hash-equal graphs with
    identical tuple ordering.

    Algorithm:
      1. Inputs from frontmatter allowed-tools.
      2. Section-driven inputs and outputs from body headings.
      3. Capabilities from imperative-verb headings outside I/O sections.
      4. Edges from backtick references in capability section bodies.
      5. Sort each collection, build and validate.

    Args:
        skill: Parsed SKILL.md document.

    Returns:
        CapabilityGraph with source="heuristic".
    """
    inputs: list[Input] = []
    outputs: list[Output] = []
    capabilities: list[Capability] = []

    # Step 1: frontmatter-derived tool inputs. Tool IDs are content-hashed on
    # the name alone, so a repeated tool (allowed-tools: [Bash, Bash]) would
    # mint two nodes with the same ID and trip the duplicate-ID check. Dedupe
    # by name first, preserving order.
    allowed_tools = skill.frontmatter.get("allowed-tools", [])
    if isinstance(allowed_tools, list):
        tool_names = [t for t in allowed_tools if isinstance(t, str) and t]
        for tool_name in dict.fromkeys(tool_names):
            iid = _make_id("tool", tool_name, None)
            inputs.append(Input(id=iid, name=tool_name, kind="tool", line=None))

    # name -> id maps; edge pass reads these after the section loop completes.
    input_name_map: dict[str, str] = {inp.name: inp.id for inp in inputs}
    output_name_map: dict[str, str] = {}

    # Capability sections stashed for the deferred edge pass.
    capability_sections: list[tuple[Capability, list[tuple[int, str]]]] = []

    # Steps 2 + 3: scan body sections.
    body_lines = skill.body.splitlines()
    for line_num, _level, heading_text, content in _sectionize(body_lines):
        if _is_input_section_heading(heading_text):
            for content_line_num, content_line in content:
                item = _get_list_item(content_line)
                if item is None:
                    continue
                name = _extract_list_item_name(item)
                if not name:
                    continue
                input_kind = _infer_input_kind(item)
                iid = _make_id(input_kind, name, content_line_num)
                inputs.append(Input(id=iid, name=name, kind=input_kind, line=content_line_num))
                input_name_map[name] = iid

        elif _is_output_section_heading(heading_text):
            for content_line_num, content_line in content:
                item = _get_list_item(content_line)
                if item is None:
                    continue
                name = _extract_list_item_name(item)
                if not name:
                    continue
                output_kind = _infer_output_kind(item)
                oid = _make_id(output_kind, name, content_line_num)
                outputs.append(Output(id=oid, name=name, kind=output_kind, line=content_line_num))
                output_name_map[name] = oid

        elif _is_imperative_heading(heading_text):
            description = ""
            for _, cline in content:
                stripped = cline.strip()
                if stripped and not re.match(r"^#+\s", cline):
                    description = stripped
                    break
            # Strip section/numeric prefix so stored name matches what an agent
            # would produce. Agents typically drop "1.1" but keep "Phase 1:";
            # we drop both for consistent name-based comparison in divergence
            # analyzers.
            cap_name = _strip_section_prefix(heading_text).strip() or heading_text
            cid = _make_id("capability", cap_name, line_num)
            cap = Capability(
                id=cid, name=cap_name, description=description, line=line_num
            )
            capabilities.append(cap)
            capability_sections.append((cap, content))

    # Step 4: edges from backtick references in capability section bodies.
    edges: list[Edge] = []
    for cap, content in capability_sections:
        content_text = "\n".join(line for _, line in content)
        seen_edge_keys: set[tuple[str, str]] = set()
        for ref in extract_backtick_refs(content_text):
            if ref in input_name_map:
                key = (cap.id, input_name_map[ref])
                if key not in seen_edge_keys:
                    edges.append(
                        Edge(source_id=cap.id, target_id=input_name_map[ref], kind="requires")
                    )
                    seen_edge_keys.add(key)
            if ref in output_name_map:
                key = (cap.id, output_name_map[ref])
                if key not in seen_edge_keys:
                    edges.append(
                        Edge(source_id=cap.id, target_id=output_name_map[ref], kind="produces")
                    )
                    seen_edge_keys.add(key)

    # Step 5: sort for determinism.
    sorted_caps = tuple(
        sorted(
            capabilities,
            key=lambda c: (c.line if c.line is not None else -1, c.name),
        )
    )
    sorted_inputs = tuple(
        sorted(
            inputs,
            key=lambda i: (i.line if i.line is not None else -1, i.name),
        )
    )
    sorted_outputs = tuple(
        sorted(
            outputs,
            key=lambda o: (o.line if o.line is not None else -1, o.name),
        )
    )
    sorted_edges = tuple(sorted(edges, key=lambda e: (e.source_id, e.target_id)))

    return CapabilityGraph(
        capabilities=sorted_caps,
        inputs=sorted_inputs,
        outputs=sorted_outputs,
        edges=sorted_edges,
        source="heuristic",
    )


def extract_graph_agent(skill: ParsedSkill, raw_response: str) -> CapabilityGraph:
    """Extract a CapabilityGraph from an agent JSON response.

    Thin wrapper around parse_graph_response. Returns a graph with
    source="agent". The heuristic extractor is not modified or removed;
    drift detection relies on both extractors coexisting.

    Args:
        skill: ParsedSkill the response was generated for. Used to validate
            that agent-claimed line numbers fall within the actual body.
        raw_response: Raw string from the agent (may include noise, fences,
            prose preamble).

    Returns:
        CapabilityGraph with source="agent".

    Raises:
        GraphParseError: Subclasses GraphJSONError, GraphSchemaError, or
            GraphValueError depending on failure mode. See agents/graph_parser.py.
    """
    from skillcheck.agents.graph_parser import parse_graph_response  # noqa: PLC0415

    return parse_graph_response(raw_response, skill)
