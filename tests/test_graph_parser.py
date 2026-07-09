"""Tests for the agent graph-extraction response parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillcheck.agents.graph_parser import (
    GraphJSONError,
    GraphParseError,
    GraphSchemaError,
    GraphValueError,
    parse_graph_response,
)
from skillcheck.core.graph import CapabilityGraph
from skillcheck.parser import parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GRAPH_DIR = FIXTURES_DIR / "graph"
GR_DIR = FIXTURES_DIR / "graph_responses"


def _skill():
    return parse(GRAPH_DIR / "skill_basic_io.md")


# ---------------------------------------------------------------------------
# Valid responses
# ---------------------------------------------------------------------------


def test_clean_response_parses_to_agent_graph() -> None:
    raw = (GR_DIR / "response_clean.json").read_text()
    graph = parse_graph_response(raw, _skill())
    assert isinstance(graph, CapabilityGraph)
    assert graph.source == "agent"


def test_clean_response_has_correct_capability_count() -> None:
    raw = (GR_DIR / "response_clean.json").read_text()
    graph = parse_graph_response(raw, _skill())
    assert len(graph.capabilities) == 1
    assert graph.capabilities[0].name == "Generate report"


def test_clean_response_has_correct_edge_count() -> None:
    raw = (GR_DIR / "response_clean.json").read_text()
    graph = parse_graph_response(raw, _skill())
    assert len(graph.edges) == 2


def test_extra_capabilities_response_parses_ok() -> None:
    raw = (GR_DIR / "response_extra_capabilities.json").read_text()
    graph = parse_graph_response(raw, _skill())
    assert len(graph.capabilities) == 3


def test_empty_collections_valid() -> None:
    raw = json.dumps({"capabilities": [], "inputs": [], "outputs": [], "edges": []})
    graph = parse_graph_response(raw, _skill())
    assert graph.source == "agent"
    assert len(graph.capabilities) == 0


# ---------------------------------------------------------------------------
# Noise stripping
# ---------------------------------------------------------------------------


def test_strips_code_fence() -> None:
    inner = json.dumps(
        {"capabilities": [], "inputs": [], "outputs": [], "edges": []}
    )
    raw = f"```json\n{inner}\n```"
    graph = parse_graph_response(raw, _skill())
    assert graph.source == "agent"


def test_strips_prose_preamble() -> None:
    inner = json.dumps(
        {"capabilities": [], "inputs": [], "outputs": [], "edges": []}
    )
    raw = f"Here is the capability graph you requested:\n{inner}"
    graph = parse_graph_response(raw, _skill())
    assert graph.source == "agent"


def test_strips_surrounding_whitespace() -> None:
    inner = json.dumps(
        {"capabilities": [], "inputs": [], "outputs": [], "edges": []}
    )
    raw = f"\n\n  {inner}  \n\n"
    graph = parse_graph_response(raw, _skill())
    assert graph.source == "agent"


# ---------------------------------------------------------------------------
# GraphJSONError
# ---------------------------------------------------------------------------


def test_malformed_json_raises_graph_json_error() -> None:
    raw = (GR_DIR / "response_malformed.json").read_text()
    with pytest.raises(GraphJSONError) as exc_info:
        parse_graph_response(raw, _skill())
    assert exc_info.value.__cause__ is not None


def test_graph_json_error_is_graph_parse_error() -> None:
    with pytest.raises(GraphParseError):
        parse_graph_response("not json at all !!!!", _skill())


def test_graph_json_error_message_includes_preview() -> None:
    raw = "not json xyz"
    with pytest.raises(GraphJSONError, match="first 200 chars"):
        parse_graph_response(raw, _skill())


# ---------------------------------------------------------------------------
# GraphSchemaError
# ---------------------------------------------------------------------------


def test_schema_error_for_wrong_type() -> None:
    raw = (GR_DIR / "response_schema_error.json").read_text()
    with pytest.raises(GraphSchemaError) as exc_info:
        parse_graph_response(raw, _skill())
    msg = str(exc_info.value)
    assert "capabilities" in msg
    assert "list" in msg


def test_schema_error_is_graph_parse_error() -> None:
    raw = json.dumps(
        {"capabilities": "not a list", "inputs": [], "outputs": [], "edges": []}
    )
    with pytest.raises(GraphParseError):
        parse_graph_response(raw, _skill())


def test_schema_error_for_missing_top_level_field() -> None:
    raw = json.dumps({"inputs": [], "outputs": [], "edges": []})
    with pytest.raises(GraphSchemaError, match="capabilities"):
        parse_graph_response(raw, _skill())


def test_schema_error_for_extra_top_level_field() -> None:
    raw = json.dumps(
        {
            "capabilities": [],
            "inputs": [],
            "outputs": [],
            "edges": [],
            "extra_field": "not allowed",
        }
    )
    with pytest.raises(GraphSchemaError, match="extra_field"):
        parse_graph_response(raw, _skill())


def test_schema_error_for_capability_missing_field() -> None:
    cap = {"id": "c1", "name": "Do something", "description": ""}
    # Missing "line"
    raw = json.dumps({"capabilities": [cap], "inputs": [], "outputs": [], "edges": []})
    with pytest.raises(GraphSchemaError, match="line"):
        parse_graph_response(raw, _skill())


def test_schema_error_for_invalid_input_kind() -> None:
    inp = {"id": "i1", "name": "foo", "kind": "database", "line": None}
    raw = json.dumps(
        {"capabilities": [], "inputs": [inp], "outputs": [], "edges": []}
    )
    with pytest.raises(GraphSchemaError, match="kind"):
        parse_graph_response(raw, _skill())


def test_schema_error_for_invalid_output_kind() -> None:
    out = {"id": "o1", "name": "bar", "kind": "blob", "line": None}
    raw = json.dumps(
        {"capabilities": [], "inputs": [], "outputs": [out], "edges": []}
    )
    with pytest.raises(GraphSchemaError, match="kind"):
        parse_graph_response(raw, _skill())


def test_schema_error_for_invalid_edge_kind() -> None:
    cap = {"id": "c1", "name": "Do something", "description": "", "line": None}
    inp = {"id": "i1", "name": "foo", "kind": "file", "line": None}
    edge = {"source_id": "c1", "target_id": "i1", "kind": "uses"}
    raw = json.dumps(
        {
            "capabilities": [cap],
            "inputs": [inp],
            "outputs": [],
            "edges": [edge],
        }
    )
    with pytest.raises(GraphSchemaError, match="kind"):
        parse_graph_response(raw, _skill())


def test_schema_error_for_bool_line_value() -> None:
    cap = {"id": "c1", "name": "Do something", "description": "", "line": True}
    raw = json.dumps({"capabilities": [cap], "inputs": [], "outputs": [], "edges": []})
    with pytest.raises(GraphSchemaError, match="bool"):
        parse_graph_response(raw, _skill())


# ---------------------------------------------------------------------------
# GraphValueError
# ---------------------------------------------------------------------------


def test_bad_line_raises_graph_value_error() -> None:
    raw = (GR_DIR / "response_bad_line.json").read_text()
    with pytest.raises(GraphValueError) as exc_info:
        parse_graph_response(raw, _skill())
    msg = str(exc_info.value)
    assert "99" in msg
    assert exc_info.value.__cause__ is None  # not a rethrow from constructor


def test_graph_value_error_is_graph_parse_error() -> None:
    raw = (GR_DIR / "response_bad_line.json").read_text()
    with pytest.raises(GraphParseError):
        parse_graph_response(raw, _skill())


def test_duplicate_id_across_collections_raises_graph_value_error() -> None:
    cap = {"id": "shared_id", "name": "Do something", "description": "", "line": None}
    inp = {"id": "shared_id", "name": "some input", "kind": "file", "line": None}
    raw = json.dumps(
        {"capabilities": [cap], "inputs": [inp], "outputs": [], "edges": []}
    )
    with pytest.raises(GraphValueError) as exc_info:
        parse_graph_response(raw, _skill())
    assert exc_info.value.__cause__ is not None


def test_dangling_edge_raises_graph_value_error() -> None:
    cap = {"id": "c1", "name": "Do something", "description": "", "line": None}
    edge = {"source_id": "c1", "target_id": "nonexistent", "kind": "produces"}
    raw = json.dumps(
        {"capabilities": [cap], "inputs": [], "outputs": [], "edges": [edge]}
    )
    with pytest.raises(GraphValueError) as exc_info:
        parse_graph_response(raw, _skill())
    assert exc_info.value.__cause__ is not None


def test_line_zero_is_out_of_range() -> None:
    cap = {"id": "c1", "name": "Do something", "description": "", "line": 0}
    raw = json.dumps({"capabilities": [cap], "inputs": [], "outputs": [], "edges": []})
    with pytest.raises(GraphValueError, match="range"):
        parse_graph_response(raw, _skill())


def test_line_equal_to_body_lines_is_valid() -> None:
    skill = _skill()
    cap = {
        "id": "c1",
        "name": "Do something",
        "description": "",
        "line": skill.body_lines,
    }
    raw = json.dumps({"capabilities": [cap], "inputs": [], "outputs": [], "edges": []})
    graph = parse_graph_response(raw, skill)
    assert graph.capabilities[0].line == skill.body_lines


def test_capabilities_over_cap_rejected() -> None:
    from skillcheck.agents._ingest import MAX_INGEST_LIST_ITEMS
    caps = [
        {"id": str(i), "name": "n", "description": "", "line": None}
        for i in range(MAX_INGEST_LIST_ITEMS + 1)
    ]
    raw = json.dumps({"capabilities": caps, "inputs": [], "outputs": [], "edges": []})
    with pytest.raises(GraphSchemaError, match="capabilities.*over the .*-item cap"):
        parse_graph_response(raw, _skill())
