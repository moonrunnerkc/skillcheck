"""Tests for parse_critique_response."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillcheck.agents.parser import (
    CritiqueJSONError,
    CritiqueParseError,
    CritiqueSchemaError,
    CritiqueValueError,
    parse_critique_response,
)
from skillcheck.agents.schema import SemanticCritique
from skillcheck.result import Severity

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CRITIQUE_DIR = FIXTURES_DIR / "critique"

_MINIMAL_VALID = {
    "clarity_score": 80,
    "completeness_score": 70,
    "executability_score": 90,
    "findings": [],
    "missing_context": [],
    "contradictions": [],
}


def _json(d: dict) -> str:
    return json.dumps(d)


# ---------------------------------------------------------------------------
# Valid responses
# ---------------------------------------------------------------------------


def test_parse_minimal_valid_response() -> None:
    result = parse_critique_response(_json(_MINIMAL_VALID))
    assert isinstance(result, SemanticCritique)
    assert result.clarity_score == 80
    assert result.completeness_score == 70
    assert result.executability_score == 90
    assert result.findings == ()
    assert result.missing_context == ()
    assert result.contradictions == ()


def test_parse_response_with_findings() -> None:
    payload = dict(_MINIMAL_VALID, findings=[{
        "section": "Overview",
        "issue": "Unclear",
        "severity": "warning",
        "suggestion": "Be specific.",
    }])
    result = parse_critique_response(_json(payload))
    assert len(result.findings) == 1
    assert result.findings[0].severity is Severity.WARNING


def test_parse_response_with_missing_context() -> None:
    payload = dict(_MINIMAL_VALID, missing_context=["auth token", "file path"])
    result = parse_critique_response(_json(payload))
    assert result.missing_context == ("auth token", "file path")


def test_parse_response_with_contradictions() -> None:
    payload = dict(_MINIMAL_VALID, contradictions=[{
        "location_a": "Sec A",
        "location_b": "Sec B",
        "nature": "They conflict.",
    }])
    result = parse_critique_response(_json(payload))
    assert len(result.contradictions) == 1
    assert result.contradictions[0].nature == "They conflict."


def test_parse_all_severity_values() -> None:
    for sev in ("error", "warning", "info"):
        payload = dict(_MINIMAL_VALID, findings=[{
            "section": "S", "issue": "I", "severity": sev, "suggestion": "X"
        }])
        result = parse_critique_response(_json(payload))
        assert result.findings[0].severity == Severity(sev)


def test_parse_boundary_scores() -> None:
    for score in (0, 100):
        payload = dict(_MINIMAL_VALID, clarity_score=score)
        result = parse_critique_response(_json(payload))
        assert result.clarity_score == score


# ---------------------------------------------------------------------------
# Noise stripping: markdown fences
# ---------------------------------------------------------------------------


def test_parse_strips_json_code_fence() -> None:
    fenced = "```json\n" + _json(_MINIMAL_VALID) + "\n```"
    result = parse_critique_response(fenced)
    assert result.clarity_score == 80


def test_parse_strips_plain_code_fence() -> None:
    fenced = "```\n" + _json(_MINIMAL_VALID) + "\n```"
    result = parse_critique_response(fenced)
    assert result.clarity_score == 80


def test_parse_strips_leading_trailing_whitespace() -> None:
    padded = "   \n\n" + _json(_MINIMAL_VALID) + "\n\n   "
    result = parse_critique_response(padded)
    assert result.clarity_score == 80


# ---------------------------------------------------------------------------
# Noise stripping: prose preamble
# ---------------------------------------------------------------------------


def test_parse_strips_prose_preamble() -> None:
    raw = (CRITIQUE_DIR / "malformed_prose_preamble.txt").read_text()
    result = parse_critique_response(raw)
    assert result.clarity_score == 80


def test_parse_strips_inline_prose_preamble() -> None:
    preamble = "Here is my assessment of the skill:\n"
    result = parse_critique_response(preamble + _json(_MINIMAL_VALID))
    assert result.clarity_score == 80


# ---------------------------------------------------------------------------
# CritiqueJSONError
# ---------------------------------------------------------------------------


def test_json_error_raised_for_invalid_json() -> None:
    with pytest.raises(CritiqueJSONError):
        parse_critique_response("this is not json")


def test_json_error_is_subclass_of_parse_error() -> None:
    with pytest.raises(CritiqueParseError):
        parse_critique_response("not json")


def test_json_error_message_includes_preview() -> None:
    bad = "definitely not { json"
    with pytest.raises(CritiqueJSONError, match="definitely not"):
        parse_critique_response(bad)


def test_json_error_message_includes_position() -> None:
    with pytest.raises(CritiqueJSONError, match="position"):
        parse_critique_response("{bad: value}")


def test_json_error_preserves_cause() -> None:
    with pytest.raises(CritiqueJSONError) as exc_info:
        parse_critique_response("not json")
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# CritiqueSchemaError
# ---------------------------------------------------------------------------


def test_schema_error_for_missing_required_field() -> None:
    payload = {k: v for k, v in _MINIMAL_VALID.items() if k != "clarity_score"}
    with pytest.raises(CritiqueSchemaError, match="clarity_score"):
        parse_critique_response(_json(payload))


def test_schema_error_for_extra_top_level_field() -> None:
    payload = dict(_MINIMAL_VALID, rogue_field="should not be here")
    with pytest.raises(CritiqueSchemaError, match="rogue_field"):
        parse_critique_response(_json(payload))


def test_schema_error_for_wrong_score_type() -> None:
    payload = dict(_MINIMAL_VALID, clarity_score="high")
    with pytest.raises(CritiqueSchemaError, match="clarity_score.*str.*'high'"):
        parse_critique_response(_json(payload))


def test_schema_error_for_bool_score() -> None:
    # JSON true becomes Python True which is bool, not int
    raw = '{"clarity_score": true, "completeness_score": 70, "executability_score": 90, "findings": [], "missing_context": [], "contradictions": []}'
    with pytest.raises(CritiqueSchemaError, match="clarity_score"):
        parse_critique_response(raw)


def test_schema_error_for_missing_finding_field() -> None:
    payload = dict(_MINIMAL_VALID, findings=[{
        "section": "S",
        "issue": "I",
        # severity missing
        "suggestion": "X",
    }])
    with pytest.raises(CritiqueSchemaError, match="severity"):
        parse_critique_response(_json(payload))


def test_schema_error_for_extra_finding_field() -> None:
    payload = dict(_MINIMAL_VALID, findings=[{
        "section": "S",
        "issue": "I",
        "severity": "info",
        "suggestion": "X",
        "extra": "nope",
    }])
    with pytest.raises(CritiqueSchemaError, match="extra"):
        parse_critique_response(_json(payload))


def test_schema_error_for_finding_not_dict() -> None:
    payload = dict(_MINIMAL_VALID, findings=["a string, not a dict"])
    with pytest.raises(CritiqueSchemaError, match="findings\\[0\\].*object"):
        parse_critique_response(_json(payload))


def test_schema_error_for_contradiction_missing_field() -> None:
    payload = dict(_MINIMAL_VALID, contradictions=[{
        "location_a": "A",
        # location_b missing
        "nature": "conflict",
    }])
    with pytest.raises(CritiqueSchemaError, match="location_b"):
        parse_critique_response(_json(payload))


def test_schema_error_for_missing_context_item_not_string() -> None:
    payload = dict(_MINIMAL_VALID, missing_context=[42])
    with pytest.raises(CritiqueSchemaError, match="missing_context\\[0\\].*str"):
        parse_critique_response(_json(payload))


def test_schema_error_for_top_level_not_object() -> None:
    with pytest.raises(CritiqueSchemaError, match="JSON object"):
        parse_critique_response("[1, 2, 3]")


# ---------------------------------------------------------------------------
# CritiqueValueError
# ---------------------------------------------------------------------------


def test_value_error_for_score_below_zero() -> None:
    payload = dict(_MINIMAL_VALID, clarity_score=-1)
    with pytest.raises(CritiqueValueError, match="clarity_score.*-1"):
        parse_critique_response(_json(payload))


def test_value_error_for_score_above_hundred() -> None:
    payload = dict(_MINIMAL_VALID, completeness_score=101)
    with pytest.raises(CritiqueValueError, match="completeness_score.*101"):
        parse_critique_response(_json(payload))


def test_value_error_for_invalid_severity_string() -> None:
    payload = dict(_MINIMAL_VALID, findings=[{
        "section": "S",
        "issue": "I",
        "severity": "critical",
        "suggestion": "X",
    }])
    with pytest.raises(CritiqueValueError, match="severity.*critical"):
        parse_critique_response(_json(payload))


def test_value_error_is_subclass_of_parse_error() -> None:
    payload = dict(_MINIMAL_VALID, clarity_score=999)
    with pytest.raises(CritiqueParseError):
        parse_critique_response(_json(payload))
