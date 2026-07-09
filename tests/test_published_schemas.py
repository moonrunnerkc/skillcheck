"""Sanity checks for the JSON Schema files shipped under skillcheck/schemas.

The schemas document the contract between skillcheck and any calling agent.
The parser modules (agents/parser.py and agents/graph_parser.py) are the
authoritative implementation; these tests assert the published schemas
stay aligned with those parsers so an agent that validates its output
against the schema also passes ingestion.
"""

from __future__ import annotations

import json
from pathlib import Path

from skillcheck.agents import SCHEMAS
from skillcheck.agents.graph_parser import (
    _TOP_LEVEL_FIELDS as _GRAPH_TOP_LEVEL_FIELDS,
)
from skillcheck.agents.graph_parser import (
    _VALID_EDGE_KINDS,
    _VALID_INPUT_KINDS,
    _VALID_OUTPUT_KINDS,
)
from skillcheck.agents.parser import _REQUIRED_FIELDS as _CRITIQUE_REQUIRED_FIELDS
from skillcheck.result import Severity


def _load(name: str) -> dict:
    path = SCHEMAS[name]
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _object_subschemas(node: object) -> list[dict]:
    """Return every subschema in *node* that declares ``"type": "object"``."""
    found: list[dict] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            found.append(node)
        for value in node.values():
            found.extend(_object_subschemas(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_object_subschemas(item))
    return found


def test_schemas_are_valid_json() -> None:
    """Both schemas parse as JSON and declare the 2020-12 dialect."""
    for name in SCHEMAS:
        doc = _load(name)
        assert doc.get("$schema") == "https://json-schema.org/draft/2020-12/schema", (
            f"{name}: $schema must declare draft 2020-12"
        )
        assert doc.get("$id"), f"{name}: $id must be set"


def test_critique_schema_required_matches_parser() -> None:
    """Top-level required fields in critique-v1.json match parser._REQUIRED_FIELDS."""
    doc = _load("critique-v1")
    assert set(doc["required"]) == set(_CRITIQUE_REQUIRED_FIELDS), (
        f"critique schema 'required' drifted from parser: schema="
        f"{sorted(doc['required'])} parser={sorted(_CRITIQUE_REQUIRED_FIELDS)}"
    )


def test_critique_schema_severity_enum_matches_parser() -> None:
    """The findings[].severity enum matches the Severity enum values."""
    doc = _load("critique-v1")
    schema_values = set(doc["properties"]["findings"]["items"]["properties"]["severity"]["enum"])
    enum_values = {s.value for s in Severity}
    assert schema_values == enum_values, (
        f"severity enum drifted: schema={sorted(schema_values)} "
        f"Severity={sorted(enum_values)}"
    )


def test_critique_schema_scores_are_0_to_100() -> None:
    """Score fields enforce the 0..100 range that the parser checks at runtime."""
    doc = _load("critique-v1")
    for field in ("clarity_score", "completeness_score", "executability_score"):
        prop = doc["properties"][field]
        assert prop["type"] == "integer"
        assert prop["minimum"] == 0
        assert prop["maximum"] == 100


def test_graph_schema_required_matches_parser() -> None:
    """Top-level required fields in graph-v1.json match graph_parser._TOP_LEVEL_FIELDS."""
    doc = _load("graph-v1")
    assert set(doc["required"]) == set(_GRAPH_TOP_LEVEL_FIELDS), (
        f"graph schema 'required' drifted from parser: schema="
        f"{sorted(doc['required'])} parser={sorted(_GRAPH_TOP_LEVEL_FIELDS)}"
    )


def test_graph_schema_kind_enums_match_parser() -> None:
    """inputs.kind, outputs.kind, edges.kind enums match the parser's valid sets."""
    doc = _load("graph-v1")
    inputs_enum = set(doc["properties"]["inputs"]["items"]["properties"]["kind"]["enum"])
    outputs_enum = set(doc["properties"]["outputs"]["items"]["properties"]["kind"]["enum"])
    edges_enum = set(doc["properties"]["edges"]["items"]["properties"]["kind"]["enum"])
    assert inputs_enum == set(_VALID_INPUT_KINDS), (
        f"inputs.kind enum drifted: schema={sorted(inputs_enum)} "
        f"parser={sorted(_VALID_INPUT_KINDS)}"
    )
    assert outputs_enum == set(_VALID_OUTPUT_KINDS), (
        f"outputs.kind enum drifted: schema={sorted(outputs_enum)} "
        f"parser={sorted(_VALID_OUTPUT_KINDS)}"
    )
    assert edges_enum == set(_VALID_EDGE_KINDS), (
        f"edges.kind enum drifted: schema={sorted(edges_enum)} "
        f"parser={sorted(_VALID_EDGE_KINDS)}"
    )


def test_critique_schema_forbids_additional_properties() -> None:
    """Every object in critique-v1.json forbids extra properties, matching the
    parser, which rejects unexpected fields at every level."""
    objects = _object_subschemas(_load("critique-v1"))
    assert objects, "expected at least one object subschema"
    for obj in objects:
        assert obj.get("additionalProperties") is False, (
            f"object subschema missing 'additionalProperties: false': "
            f"{sorted(obj.get('properties', {}))}"
        )


def test_graph_schema_forbids_additional_properties() -> None:
    """Every object in graph-v1.json forbids extra properties, matching the
    parser's unknown-field rejection at each node level."""
    objects = _object_subschemas(_load("graph-v1"))
    assert objects, "expected at least one object subschema"
    for obj in objects:
        assert obj.get("additionalProperties") is False, (
            f"object subschema missing 'additionalProperties: false': "
            f"{sorted(obj.get('properties', {}))}"
        )


def test_schemas_validate_known_good_fixtures() -> None:
    """Each schema's known-good fixture loads cleanly and satisfies the
    required-field check (used as a low-rigor self-test that the schema
    matches at least one canonical response shape).
    """
    fixtures_dir = Path(__file__).parent / "fixtures"
    critique_doc = _load("critique-v1")
    candidates = list(fixtures_dir.rglob("*critique*.json"))
    candidates += list(fixtures_dir.rglob("*clean*.json"))
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict) and "clarity_score" in payload:
            missing = set(critique_doc["required"]) - payload.keys()
            assert not missing, (
                f"critique fixture {candidate} missing schema-required fields: {missing}"
            )

    graph_doc = _load("graph-v1")
    for candidate in fixtures_dir.rglob("*.json"):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict) and "capabilities" in payload and "edges" in payload:
            missing = set(graph_doc["required"]) - payload.keys()
            assert not missing, (
                f"graph fixture {candidate} missing schema-required fields: {missing}"
            )
