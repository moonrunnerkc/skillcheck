"""Tests for graph rendering functions.

Covers render_graph_text and render_graph_json with real fixtures,
empty graphs, and JSON round-trip / determinism checks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillcheck.core.graph import CapabilityGraph, extract_graph_heuristic
from skillcheck.core.graph_render import render_graph_json, render_graph_text
from skillcheck.parser import parse as _parse

FIXTURES = Path(__file__).parent / "fixtures" / "graph"


@pytest.fixture()
def basic_io_graph() -> CapabilityGraph:
    skill = _parse(FIXTURES / "skill_basic_io.md")
    return extract_graph_heuristic(skill)


# ---------------------------------------------------------------------------
# render_graph_text
# ---------------------------------------------------------------------------


def test_render_graph_text_includes_source(basic_io_graph: CapabilityGraph) -> None:
    text = render_graph_text(basic_io_graph)
    assert text.startswith("source: heuristic")


def test_render_graph_text_section_headers(basic_io_graph: CapabilityGraph) -> None:
    text = render_graph_text(basic_io_graph)
    assert "Capabilities (1):" in text
    assert "Inputs (3):" in text
    assert "Outputs (3):" in text
    assert "Edges (2):" in text


def test_render_graph_text_capability_name_and_line(basic_io_graph: CapabilityGraph) -> None:
    text = render_graph_text(basic_io_graph)
    assert "Generate report [line 8]" in text


def test_render_graph_text_capability_description(basic_io_graph: CapabilityGraph) -> None:
    text = render_graph_text(basic_io_graph)
    assert "Connects via" in text


def test_render_graph_text_input_kind(basic_io_graph: CapabilityGraph) -> None:
    text = render_graph_text(basic_io_graph)
    assert "db_client [tool, line 4]" in text
    assert "DB_URL [env, line 5]" in text
    assert "schema.sql [file, line 6]" in text


def test_render_graph_text_output_kind(basic_io_graph: CapabilityGraph) -> None:
    text = render_graph_text(basic_io_graph)
    assert "report.json [file, line 14]" in text
    assert "execution summary [artifact, line 15]" in text
    assert "record_count [return, line 16]" in text


def test_render_graph_text_edges(basic_io_graph: CapabilityGraph) -> None:
    text = render_graph_text(basic_io_graph)
    assert "Generate report requires db_client" in text
    assert "Generate report produces report.json" in text


def test_render_graph_text_empty_graph() -> None:
    graph = CapabilityGraph(
        capabilities=(),
        inputs=(),
        outputs=(),
        edges=(),
        source="heuristic",
    )
    text = render_graph_text(graph)
    assert "Capabilities (0):" in text
    assert "Inputs (0):" in text
    assert "Outputs (0):" in text
    assert "Edges (0):" in text


def test_render_graph_text_is_deterministic(basic_io_graph: CapabilityGraph) -> None:
    assert render_graph_text(basic_io_graph) == render_graph_text(basic_io_graph)


# ---------------------------------------------------------------------------
# render_graph_json
# ---------------------------------------------------------------------------


def test_render_graph_json_is_valid_json(basic_io_graph: CapabilityGraph) -> None:
    raw = render_graph_json(basic_io_graph)
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)


def test_render_graph_json_top_level_keys(basic_io_graph: CapabilityGraph) -> None:
    parsed = json.loads(render_graph_json(basic_io_graph))
    assert list(parsed.keys()) == ["source", "capabilities", "inputs", "outputs", "edges"]


def test_render_graph_json_source(basic_io_graph: CapabilityGraph) -> None:
    parsed = json.loads(render_graph_json(basic_io_graph))
    assert parsed["source"] == "heuristic"


def test_render_graph_json_capability_structure(basic_io_graph: CapabilityGraph) -> None:
    parsed = json.loads(render_graph_json(basic_io_graph))
    cap = parsed["capabilities"][0]
    assert cap["name"] == "Generate report"
    assert cap["line"] == 8
    assert "description" in cap
    assert "id" in cap


def test_render_graph_json_input_count(basic_io_graph: CapabilityGraph) -> None:
    parsed = json.loads(render_graph_json(basic_io_graph))
    assert len(parsed["inputs"]) == 3


def test_render_graph_json_output_count(basic_io_graph: CapabilityGraph) -> None:
    parsed = json.loads(render_graph_json(basic_io_graph))
    assert len(parsed["outputs"]) == 3


def test_render_graph_json_edge_structure(basic_io_graph: CapabilityGraph) -> None:
    parsed = json.loads(render_graph_json(basic_io_graph))
    edge = parsed["edges"][0]
    assert "source_id" in edge
    assert "target_id" in edge
    assert "kind" in edge


def test_render_graph_json_edge_kinds(basic_io_graph: CapabilityGraph) -> None:
    parsed = json.loads(render_graph_json(basic_io_graph))
    kinds = {e["kind"] for e in parsed["edges"]}
    assert "requires" in kinds
    assert "produces" in kinds


def test_render_graph_json_is_deterministic(basic_io_graph: CapabilityGraph) -> None:
    assert render_graph_json(basic_io_graph) == render_graph_json(basic_io_graph)


def test_render_graph_json_round_trip_ids(basic_io_graph: CapabilityGraph) -> None:
    """Edge source_id / target_id must match capability / IO node ids exactly."""
    parsed = json.loads(render_graph_json(basic_io_graph))
    cap_ids = {c["id"] for c in parsed["capabilities"]}
    inp_ids = {i["id"] for i in parsed["inputs"]}
    out_ids = {o["id"] for o in parsed["outputs"]}
    for edge in parsed["edges"]:
        assert edge["source_id"] in cap_ids
        if edge["kind"] == "requires":
            assert edge["target_id"] in inp_ids
        else:
            assert edge["target_id"] in out_ids


def test_render_graph_json_empty_graph() -> None:
    graph = CapabilityGraph(
        capabilities=(),
        inputs=(),
        outputs=(),
        edges=(),
        source="heuristic",
    )
    parsed = json.loads(render_graph_json(graph))
    assert parsed["capabilities"] == []
    assert parsed["edges"] == []


def test_render_graph_json_null_line_is_serialised(basic_io_graph: CapabilityGraph) -> None:
    """Input with no line number (e.g. frontmatter tool) should serialise as null."""
    skill = _parse(FIXTURES / "skill_frontmatter_tools.md")
    graph = extract_graph_heuristic(skill)
    parsed = json.loads(render_graph_json(graph))
    tool_inputs = [i for i in parsed["inputs"] if i["kind"] == "tool"]
    assert any(i["line"] is None for i in tool_inputs)
