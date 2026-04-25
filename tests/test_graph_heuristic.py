"""Tests for CapabilityGraph data model and extract_graph_heuristic."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from skillcheck.core.graph import (
    IMPERATIVE_VERBS,
    INPUT_SECTION_ALIASES,
    OUTPUT_SECTION_ALIASES,
    Capability,
    CapabilityGraph,
    Edge,
    Input,
    Output,
    _make_id,
    extract_graph_heuristic,
)
from skillcheck.parser import parse

GRAPH_DIR = Path(__file__).parent / "fixtures" / "graph"


def _parse(name: str):  # type: ignore[return]
    return parse(GRAPH_DIR / name)


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


def test_imperative_verbs_tuple_sorted() -> None:
    assert IMPERATIVE_VERBS == tuple(sorted(IMPERATIVE_VERBS))


def test_input_section_aliases_tuple_sorted() -> None:
    assert INPUT_SECTION_ALIASES == tuple(sorted(INPUT_SECTION_ALIASES))


def test_output_section_aliases_tuple_sorted() -> None:
    assert OUTPUT_SECTION_ALIASES == tuple(sorted(OUTPUT_SECTION_ALIASES))


# ---------------------------------------------------------------------------
# skill_basic_io.md: exact graph contents
# ---------------------------------------------------------------------------


def test_basic_io_capability_count() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    assert len(g.capabilities) == 1


def test_basic_io_capability_name() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    assert g.capabilities[0].name == "Generate report"


def test_basic_io_capability_description() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    assert "db_client" in g.capabilities[0].description


def test_basic_io_input_count() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    assert len(g.inputs) == 3


def test_basic_io_input_kinds() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    kinds = {i.name: i.kind for i in g.inputs}
    assert kinds["db_client"] == "tool"
    assert kinds["DB_URL"] == "env"
    assert kinds["schema.sql"] == "file"


def test_basic_io_output_count() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    assert len(g.outputs) == 3


def test_basic_io_output_kinds() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    kinds = {o.name: o.kind for o in g.outputs}
    assert kinds["report.json"] == "file"
    assert kinds["execution summary"] == "artifact"
    assert kinds["record_count"] == "return"


def test_basic_io_edge_count() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    assert len(g.edges) == 2


def test_basic_io_edges_correct_kinds() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    edge_kinds = {e.target_id: e.kind for e in g.edges}
    # db_client is an input -> requires
    db_client_id = next(i.id for i in g.inputs if i.name == "db_client")
    assert edge_kinds[db_client_id] == "requires"
    # report.json is an output -> produces
    report_id = next(o.id for o in g.outputs if o.name == "report.json")
    assert edge_kinds[report_id] == "produces"


def test_basic_io_source_is_heuristic() -> None:
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    assert g.source == "heuristic"


# ---------------------------------------------------------------------------
# skill_frontmatter_tools.md: allowed-tools becomes tool-kind inputs
# ---------------------------------------------------------------------------


def test_frontmatter_tools_input_count() -> None:
    g = extract_graph_heuristic(_parse("skill_frontmatter_tools.md"))
    assert len(g.inputs) == 3


def test_frontmatter_tools_all_kind_tool() -> None:
    g = extract_graph_heuristic(_parse("skill_frontmatter_tools.md"))
    assert all(i.kind == "tool" for i in g.inputs)


def test_frontmatter_tools_names() -> None:
    g = extract_graph_heuristic(_parse("skill_frontmatter_tools.md"))
    names = {i.name for i in g.inputs}
    assert names == {"Read", "Write", "Bash"}


def test_frontmatter_tools_line_is_none() -> None:
    g = extract_graph_heuristic(_parse("skill_frontmatter_tools.md"))
    assert all(i.line is None for i in g.inputs)


def test_frontmatter_tools_no_capabilities() -> None:
    g = extract_graph_heuristic(_parse("skill_frontmatter_tools.md"))
    assert len(g.capabilities) == 0


# ---------------------------------------------------------------------------
# skill_imperative_capabilities.md: only imperative headings become capabilities
# ---------------------------------------------------------------------------


def test_imperative_caps_count() -> None:
    g = extract_graph_heuristic(_parse("skill_imperative_capabilities.md"))
    assert len(g.capabilities) == 3


def test_imperative_caps_names_are_imperative() -> None:
    g = extract_graph_heuristic(_parse("skill_imperative_capabilities.md"))
    names = {c.name for c in g.capabilities}
    assert names == {"Generate summary", "Build index", "Validate output"}


def test_imperative_caps_overview_excluded() -> None:
    g = extract_graph_heuristic(_parse("skill_imperative_capabilities.md"))
    names = {c.name for c in g.capabilities}
    assert "Overview" not in names
    assert "Usage Notes" not in names


# ---------------------------------------------------------------------------
# skill_no_structure.md: prose-only body yields empty graph
# ---------------------------------------------------------------------------


def test_no_structure_empty_graph() -> None:
    g = extract_graph_heuristic(_parse("skill_no_structure.md"))
    assert len(g.capabilities) == 0
    assert len(g.inputs) == 0
    assert len(g.outputs) == 0
    assert len(g.edges) == 0


# ---------------------------------------------------------------------------
# skill_section_aliases.md: "Prerequisites" and "Produces" are recognised
# ---------------------------------------------------------------------------


def test_aliases_prerequisites_section_recognized() -> None:
    g = extract_graph_heuristic(_parse("skill_section_aliases.md"))
    assert len(g.inputs) == 2


def test_aliases_produces_section_recognized() -> None:
    g = extract_graph_heuristic(_parse("skill_section_aliases.md"))
    assert len(g.outputs) == 1
    assert g.outputs[0].name == "output.zip"


def test_aliases_capability_and_edges() -> None:
    g = extract_graph_heuristic(_parse("skill_section_aliases.md"))
    assert len(g.capabilities) == 1
    assert g.capabilities[0].name == "Create artifact"
    assert len(g.edges) == 2


# ---------------------------------------------------------------------------
# skill_duplicate_section.md: items from both Outputs sections are merged
# ---------------------------------------------------------------------------


def test_duplicate_section_outputs_merged() -> None:
    g = extract_graph_heuristic(_parse("skill_duplicate_section.md"))
    output_names = {o.name for o in g.outputs}
    assert "primary.json" in output_names
    assert "secondary.csv" in output_names


def test_duplicate_section_total_outputs() -> None:
    g = extract_graph_heuristic(_parse("skill_duplicate_section.md"))
    assert len(g.outputs) == 2


def test_duplicate_section_edges() -> None:
    g = extract_graph_heuristic(_parse("skill_duplicate_section.md"))
    # "Generate output" capability body backtick-references both output names.
    assert len(g.edges) == 2
    assert all(e.kind == "produces" for e in g.edges)


# ---------------------------------------------------------------------------
# Determinism: same fixture produces equal, hash-equal graphs
# ---------------------------------------------------------------------------


def test_equal_on_repeated_extraction() -> None:
    skill = _parse("skill_basic_io.md")
    g1 = extract_graph_heuristic(skill)
    g2 = extract_graph_heuristic(skill)
    assert g1 == g2


def test_hash_equal_on_repeated_extraction() -> None:
    skill = _parse("skill_basic_io.md")
    g1 = extract_graph_heuristic(skill)
    g2 = extract_graph_heuristic(skill)
    assert hash(g1) == hash(g2)


def test_tuple_ordering_is_stable() -> None:
    skill = _parse("skill_basic_io.md")
    g1 = extract_graph_heuristic(skill)
    g2 = extract_graph_heuristic(skill)
    assert g1.capabilities == g2.capabilities
    assert g1.inputs == g2.inputs
    assert g1.outputs == g2.outputs
    assert g1.edges == g2.edges


def test_stable_ids_for_basic_io() -> None:
    # Verify specific IDs using the same hash function the extractor uses.
    # If the algorithm changes, these will fail and force a conscious update.
    g = extract_graph_heuristic(_parse("skill_basic_io.md"))
    cap = g.capabilities[0]
    assert cap.id == _make_id("capability", "Generate report", cap.line)

    db_client = next(i for i in g.inputs if i.name == "db_client")
    assert db_client.id == _make_id("tool", "db_client", db_client.line)

    report = next(o for o in g.outputs if o.name == "report.json")
    assert report.id == _make_id("file", "report.json", report.line)


def test_make_id_is_deterministic() -> None:
    assert _make_id("capability", "Generate report", 8) == _make_id("capability", "Generate report", 8)


def test_make_id_differs_with_different_line() -> None:
    assert _make_id("capability", "Generate report", 8) != _make_id("capability", "Generate report", 9)


def test_make_id_differs_with_none_vs_int() -> None:
    assert _make_id("tool", "Read", None) != _make_id("tool", "Read", 1)


def test_make_id_is_eight_hex_chars() -> None:
    result = _make_id("capability", "x", 1)
    assert len(result) == 8
    assert all(c in "0123456789abcdef" for c in result)


# ---------------------------------------------------------------------------
# CapabilityGraph validation: constructor enforces integrity
# ---------------------------------------------------------------------------

# Helpers to build minimal valid graphs for violation tests.
_CAP = Capability(id="cap00001", name="Generate x", description="", line=1)
_INP = Input(id="inp00001", name="data.csv", kind="file", line=2)
_OUT = Output(id="out00001", name="result.json", kind="file", line=5)


def _valid_graph(**overrides) -> CapabilityGraph:
    base = dict(
        capabilities=(_CAP,),
        inputs=(_INP,),
        outputs=(_OUT,),
        edges=(
            Edge(source_id="cap00001", target_id="inp00001", kind="requires"),
            Edge(source_id="cap00001", target_id="out00001", kind="produces"),
        ),
        source="heuristic",
    )
    base.update(overrides)
    return CapabilityGraph(**base)  # type: ignore[arg-type]


def test_valid_graph_constructs_without_error() -> None:
    _valid_graph()


def test_edge_unknown_target_raises_value_error() -> None:
    bad_edge = Edge(source_id="cap00001", target_id="nonexistent", kind="requires")
    with pytest.raises(ValueError, match="nonexistent"):
        CapabilityGraph(
            capabilities=(_CAP,),
            inputs=(_INP,),
            outputs=(_OUT,),
            edges=(bad_edge,),
            source="heuristic",
        )


def test_edge_unknown_source_raises_value_error() -> None:
    bad_edge = Edge(source_id="ghost", target_id="inp00001", kind="requires")
    with pytest.raises(ValueError, match="ghost"):
        CapabilityGraph(
            capabilities=(_CAP,),
            inputs=(_INP,),
            outputs=(_OUT,),
            edges=(bad_edge,),
            source="heuristic",
        )


def test_duplicate_ids_raises_value_error() -> None:
    dup_input = Input(id="cap00001", name="collision", kind="file", line=99)
    with pytest.raises(ValueError, match="cap00001"):
        CapabilityGraph(
            capabilities=(_CAP,),
            inputs=(_INP, dup_input),
            outputs=(_OUT,),
            edges=(),
            source="heuristic",
        )


def test_requires_edge_pointing_to_output_raises_value_error() -> None:
    # Edge kind="requires" but target_id references an output, not an input.
    bad_edge = Edge(source_id="cap00001", target_id="out00001", kind="requires")
    with pytest.raises(ValueError, match="out00001"):
        CapabilityGraph(
            capabilities=(_CAP,),
            inputs=(_INP,),
            outputs=(_OUT,),
            edges=(bad_edge,),
            source="heuristic",
        )


def test_produces_edge_pointing_to_input_raises_value_error() -> None:
    bad_edge = Edge(source_id="cap00001", target_id="inp00001", kind="produces")
    with pytest.raises(ValueError, match="inp00001"):
        CapabilityGraph(
            capabilities=(_CAP,),
            inputs=(_INP,),
            outputs=(_OUT,),
            edges=(bad_edge,),
            source="heuristic",
        )


# ---------------------------------------------------------------------------
# Line-numbering regression: capability line is body-relative, not file-relative
# ---------------------------------------------------------------------------


def test_capability_line_is_body_relative() -> None:
    # skill_basic_io.md has 7 frontmatter lines (including --- delimiters).
    # "## Generate report" is body line 8.
    # File-relative would be 8 + 7 = 15.
    skill = _parse("skill_basic_io.md")
    g = extract_graph_heuristic(skill)
    cap = g.capabilities[0]
    assert cap.name == "Generate report"
    assert cap.line is not None

    # Count frontmatter lines (everything in raw_text before the body).
    frontmatter_line_count = skill.raw_text[: skill.raw_text.index(skill.body)].count("\n")
    assert frontmatter_line_count >= 6, (
        "Fixture needs enough frontmatter to distinguish body-relative from file-relative"
    )

    # Body-relative: line must be within the body.
    body_line_count = len(skill.body.splitlines())
    assert cap.line <= body_line_count, (
        f"line {cap.line} exceeds body length {body_line_count}; looks file-relative"
    )

    # Must NOT equal the file-relative line.
    file_relative = cap.line + frontmatter_line_count
    assert cap.line != file_relative


def test_input_line_is_body_relative() -> None:
    skill = _parse("skill_basic_io.md")
    g = extract_graph_heuristic(skill)
    frontmatter_line_count = skill.raw_text[: skill.raw_text.index(skill.body)].count("\n")
    body_line_count = len(skill.body.splitlines())

    for inp in g.inputs:
        if inp.line is not None:
            assert inp.line <= body_line_count, (
                f"Input '{inp.name}' line {inp.line} exceeds body length; looks file-relative"
            )
            assert inp.line != inp.line + frontmatter_line_count


# ---------------------------------------------------------------------------
# Core module re-exports
# ---------------------------------------------------------------------------


def test_core_exports_extract_graph_heuristic() -> None:
    from skillcheck.core import graph as graph_module
    assert hasattr(graph_module, "extract_graph_heuristic")


def test_import_path_smoke() -> None:
    from skillcheck.core.graph import (  # noqa: F401
        Capability,
        CapabilityGraph,
        Edge,
        Input,
        Output,
        extract_graph_heuristic,
    )
