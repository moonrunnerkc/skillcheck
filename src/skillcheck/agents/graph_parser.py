"""Parser for agent capability-graph JSON responses.

Converts raw agent output into a CapabilityGraph with source="agent". Handles
the three failure modes that are realistically distinct: invalid JSON, schema
mismatch, and out-of-range or semantically invalid values.

Noise stripping (markdown fences, prose preambles) is shared with the
critique parser; see agents/_response_text.py.
"""

from __future__ import annotations

import json
from typing import Literal

from skillcheck.agents._response_text import strip_response_noise
from skillcheck.core.graph import Capability, CapabilityGraph, Edge, Input, Output
from skillcheck.parser import ParsedSkill

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class GraphParseError(Exception):
    """Base class for all graph response parse errors."""


class GraphJSONError(GraphParseError):
    """Raw response is not valid JSON.

    Message contains the first 200 characters received and the decoder's
    error position so callers can log useful context without dumping the
    full response.
    """


class GraphSchemaError(GraphParseError):
    """JSON parsed but does not match the required schema.

    Message names the specific field and what was wrong, e.g.:
      "Field 'capabilities[0].line' must be int or null, got str: '5'"
    """


class GraphValueError(GraphParseError):
    """Schema matches but a value violates semantic rules.

    Examples: line number out of range, edge source_id not in capabilities.
    Message includes the offending value or IDs.
    """


# ---------------------------------------------------------------------------
# Valid enumeration sets
# ---------------------------------------------------------------------------

_VALID_INPUT_KINDS: frozenset[str] = frozenset(
    {"file", "tool", "env", "context", "prerequisite"}
)
_VALID_OUTPUT_KINDS: frozenset[str] = frozenset(
    {"file", "artifact", "side_effect", "return"}
)
_VALID_EDGE_KINDS: frozenset[str] = frozenset({"requires", "produces"})

# Top-level required keys and acceptable Python types.
_TOP_LEVEL_FIELDS: dict[str, type] = {
    "capabilities": list,
    "inputs": list,
    "outputs": list,
    "edges": list,
}

# Per-node required fields.
_CAP_FIELDS: dict[str, type | tuple[type, ...]] = {
    "id": str,
    "name": str,
    "description": str,
    "line": (int, type(None)),
}
_INPUT_FIELDS: dict[str, type | tuple[type, ...]] = {
    "id": str,
    "name": str,
    "kind": str,
    "line": (int, type(None)),
}
_OUTPUT_FIELDS: dict[str, type | tuple[type, ...]] = {
    "id": str,
    "name": str,
    "kind": str,
    "line": (int, type(None)),
}
_EDGE_FIELDS: dict[str, type] = {
    "source_id": str,
    "target_id": str,
    "kind": str,
}

# ---------------------------------------------------------------------------
# Field-level helpers
# ---------------------------------------------------------------------------


def _require_field(
    obj: dict,
    key: str,
    expected_type: type | tuple[type, ...],
    context: str = "",
) -> object:
    """Extract a required field with type checking.

    Args:
        obj: Mapping to extract from.
        key: Required field name.
        expected_type: Acceptable Python type(s). For union types pass a tuple.
        context: Optional prefix for error messages, e.g. "capabilities[0]".

    Returns:
        The field value.

    Raises:
        GraphSchemaError: If the field is missing, has wrong type, or (for int)
            is actually a bool (bool is an int subclass but not a line number).
    """
    full_key = f"{context}.{key}" if context else key
    if key not in obj:
        raise GraphSchemaError(f"Missing required field '{full_key}'")
    value = obj[key]
    # bool is a subclass of int; reject it for integer fields.
    if expected_type is int and isinstance(value, bool):
        raise GraphSchemaError(
            f"Field '{full_key}' must be int, got bool: {value!r}"
        )
    # For (int, NoneType) unions, bool is also rejected.
    if (
        isinstance(expected_type, tuple)
        and int in expected_type
        and isinstance(value, bool)
    ):
        raise GraphSchemaError(
            f"Field '{full_key}' must be int or null, got bool: {value!r}"
        )
    if not isinstance(value, expected_type):  # type: ignore[arg-type]
        if isinstance(expected_type, tuple):
            type_name = " or ".join(
                "null" if t is type(None) else t.__name__ for t in expected_type
            )
        else:
            type_name = expected_type.__name__
        raise GraphSchemaError(
            f"Field '{full_key}' must be {type_name}, "
            f"got {type(value).__name__}: {value!r}"
        )
    return value


def _check_no_extra_fields(obj: dict, allowed: dict, context: str) -> None:
    extra = set(obj) - set(allowed)
    if extra:
        raise GraphSchemaError(
            f"{context} has unexpected fields: {sorted(extra)}"
        )


# ---------------------------------------------------------------------------
# Per-collection parsers
# ---------------------------------------------------------------------------


def _parse_capability(raw: object, index: int) -> Capability:
    ctx = f"capabilities[{index}]"
    if not isinstance(raw, dict):
        raise GraphSchemaError(
            f"capabilities[{index}] must be an object, got {type(raw).__name__}"
        )
    _check_no_extra_fields(raw, _CAP_FIELDS, ctx)
    node_id = str(_require_field(raw, "id", str, ctx))
    name = str(_require_field(raw, "name", str, ctx))
    description = str(_require_field(raw, "description", str, ctx))
    line_raw = _require_field(raw, "line", (int, type(None)), ctx)
    assert isinstance(line_raw, int | type(None))
    line = int(line_raw) if line_raw is not None else None
    return Capability(id=node_id, name=name, description=description, line=line)


def _parse_input(raw: object, index: int) -> Input:
    ctx = f"inputs[{index}]"
    if not isinstance(raw, dict):
        raise GraphSchemaError(
            f"inputs[{index}] must be an object, got {type(raw).__name__}"
        )
    _check_no_extra_fields(raw, _INPUT_FIELDS, ctx)
    node_id = str(_require_field(raw, "id", str, ctx))
    name = str(_require_field(raw, "name", str, ctx))
    kind_raw = str(_require_field(raw, "kind", str, ctx))
    line_raw = _require_field(raw, "line", (int, type(None)), ctx)
    assert isinstance(line_raw, int | type(None))
    line = int(line_raw) if line_raw is not None else None
    if kind_raw not in _VALID_INPUT_KINDS:
        raise GraphSchemaError(
            f"inputs[{index}].kind must be one of "
            f"{sorted(_VALID_INPUT_KINDS)}, got: {kind_raw!r}"
        )
    kind: Literal["file", "tool", "env", "context", "prerequisite"] = kind_raw  # type: ignore[assignment]
    return Input(id=node_id, name=name, kind=kind, line=line)


def _parse_output(raw: object, index: int) -> Output:
    ctx = f"outputs[{index}]"
    if not isinstance(raw, dict):
        raise GraphSchemaError(
            f"outputs[{index}] must be an object, got {type(raw).__name__}"
        )
    _check_no_extra_fields(raw, _OUTPUT_FIELDS, ctx)
    node_id = str(_require_field(raw, "id", str, ctx))
    name = str(_require_field(raw, "name", str, ctx))
    kind_raw = str(_require_field(raw, "kind", str, ctx))
    line_raw = _require_field(raw, "line", (int, type(None)), ctx)
    assert isinstance(line_raw, int | type(None))
    line = int(line_raw) if line_raw is not None else None
    if kind_raw not in _VALID_OUTPUT_KINDS:
        raise GraphSchemaError(
            f"outputs[{index}].kind must be one of "
            f"{sorted(_VALID_OUTPUT_KINDS)}, got: {kind_raw!r}"
        )
    kind: Literal["file", "artifact", "side_effect", "return"] = kind_raw  # type: ignore[assignment]
    return Output(id=node_id, name=name, kind=kind, line=line)


def _parse_edge(raw: object, index: int) -> Edge:
    ctx = f"edges[{index}]"
    if not isinstance(raw, dict):
        raise GraphSchemaError(
            f"edges[{index}] must be an object, got {type(raw).__name__}"
        )
    _check_no_extra_fields(raw, _EDGE_FIELDS, ctx)
    source_id = str(_require_field(raw, "source_id", str, ctx))
    target_id = str(_require_field(raw, "target_id", str, ctx))
    kind_raw = str(_require_field(raw, "kind", str, ctx))
    if kind_raw not in _VALID_EDGE_KINDS:
        raise GraphSchemaError(
            f"edges[{index}].kind must be one of "
            f"{sorted(_VALID_EDGE_KINDS)}, got: {kind_raw!r}"
        )
    kind: Literal["requires", "produces"] = kind_raw  # type: ignore[assignment]
    return Edge(source_id=source_id, target_id=target_id, kind=kind)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_graph_response(raw: str, skill: ParsedSkill) -> CapabilityGraph:
    """Parse an agent graph-extraction JSON response into a CapabilityGraph.

    Returns a graph with source="agent". Line numbers from the agent response
    are validated against skill.body_lines: each non-None line value must
    satisfy 1 <= line <= skill.body_lines.

    Args:
        raw: Raw string from the agent (may include noise, fences, preamble).
        skill: ParsedSkill the response was generated for. Used to validate
            that line numbers fall within the actual body.

    Returns:
        CapabilityGraph with source="agent".

    Raises:
        GraphJSONError: raw is not valid JSON after noise stripping.
        GraphSchemaError: JSON parses but does not match the required schema.
        GraphValueError: Schema matches but values violate semantic rules
            (out-of-range line numbers, duplicate IDs, dangling edge references).
    """
    cleaned = strip_response_noise(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        preview = raw[:200].replace("\n", " ")
        raise GraphJSONError(
            f"Response is not valid JSON (error at position {exc.pos}): "
            f"first 200 chars: {preview!r}"
        ) from exc

    if not isinstance(data, dict):
        raise GraphSchemaError(
            f"Response must be a JSON object, got {type(data).__name__}"
        )

    # Validate top-level fields.
    extra_top = set(data) - set(_TOP_LEVEL_FIELDS)
    if extra_top:
        raise GraphSchemaError(
            f"Response has unexpected top-level fields: {sorted(extra_top)}"
        )
    for key, expected_type in _TOP_LEVEL_FIELDS.items():
        _require_field(data, key, expected_type)

    # Parse node collections.
    capabilities = tuple(
        _parse_capability(item, i)
        for i, item in enumerate(data["capabilities"])
    )
    inputs = tuple(
        _parse_input(item, i)
        for i, item in enumerate(data["inputs"])
    )
    outputs = tuple(
        _parse_output(item, i)
        for i, item in enumerate(data["outputs"])
    )
    edges = tuple(
        _parse_edge(item, i)
        for i, item in enumerate(data["edges"])
    )

    # Validate line numbers against actual skill body.
    body_len = skill.body_lines
    for cap in capabilities:
        if cap.line is not None and not (1 <= cap.line <= body_len):
            raise GraphValueError(
                f"capabilities node '{cap.id}' (name={cap.name!r}) has "
                f"line={cap.line} which is outside the skill body range "
                f"[1, {body_len}]."
            )
    for inp in inputs:
        if inp.line is not None and not (1 <= inp.line <= body_len):
            raise GraphValueError(
                f"inputs node '{inp.id}' (name={inp.name!r}) has "
                f"line={inp.line} which is outside the skill body range "
                f"[1, {body_len}]."
            )
    for out in outputs:
        if out.line is not None and not (1 <= out.line <= body_len):
            raise GraphValueError(
                f"outputs node '{out.id}' (name={out.name!r}) has "
                f"line={out.line} which is outside the skill body range "
                f"[1, {body_len}]."
            )

    # Pass through CapabilityGraph constructor, which validates duplicate IDs
    # and edge referential integrity. ValueError from constructor -> GraphValueError.
    try:
        return CapabilityGraph(
            capabilities=capabilities,
            inputs=inputs,
            outputs=outputs,
            edges=edges,
            source="agent",
        )
    except ValueError as exc:
        raise GraphValueError(str(exc)) from exc
