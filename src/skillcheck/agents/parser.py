"""Parser for agent self-critique JSON responses.

Converts raw agent output into a SemanticCritique. Handles the three failure
modes that are realistically distinct: invalid JSON, schema mismatch, and
out-of-range values.

Noise stripping (markdown fences, prose preambles) is shared with the
graph parser; see agents/_response_text.py.
"""

from __future__ import annotations

from skillcheck.agents._ingest import (
    decode_json_or_raise,
    enforce_list_cap,
    require_field,
)
from skillcheck.agents.schema import (
    Contradiction,
    CritiqueFinding,
    SemanticCritique,
)
from skillcheck.result import Severity

# Required top-level keys and their expected Python types.
_REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "clarity_score": int,
    "completeness_score": int,
    "executability_score": int,
    "findings": list,
    "missing_context": list,
    "contradictions": list,
}

_FINDING_FIELDS: dict[str, type] = {
    "section": str,
    "issue": str,
    "severity": str,
    "suggestion": str,
}

_CONTRADICTION_FIELDS: dict[str, type] = {
    "location_a": str,
    "location_b": str,
    "nature": str,
}

_VALID_SEVERITIES = {s.value for s in Severity}


class CritiqueParseError(Exception):
    """Base class for all critique response parse errors."""


class CritiqueJSONError(CritiqueParseError):
    """Raw response is not valid JSON.

    Attributes include the first 200 characters received and the decoder's
    error position so callers can log useful context without dumping the full
    response.
    """


class CritiqueSchemaError(CritiqueParseError):
    """JSON parsed but does not match the required schema.

    Message names the specific field and what was wrong.
    """


class CritiqueValueError(CritiqueParseError):
    """Schema matches but a value is out of the allowed range.

    Message includes the offending value.
    """


def _require_field(obj: dict[str, object], key: str, expected_type: type | tuple[type, ...], context: str = "") -> object:
    """Extract a required field, raising CritiqueSchemaError on missing/wrong type.

    Thin binding of the shared ``require_field`` to this parser's error class;
    see ``agents/_ingest.py`` for the checking logic.
    """
    return require_field(obj, key, expected_type, error_cls=CritiqueSchemaError, context=context)


def _parse_finding(raw: object, index: int) -> CritiqueFinding:
    """Parse one finding dict from the agent response.

    Args:
        raw: Value from the findings list (must be a dict).
        index: Position in the findings list, for error messages.

    Returns:
        Constructed CritiqueFinding.

    Raises:
        CritiqueSchemaError: For type or field errors.
        CritiqueValueError: For invalid severity strings.
    """
    ctx = f"findings[{index}]"
    if not isinstance(raw, dict):
        raise CritiqueSchemaError(
            f"findings[{index}] must be an object, got {type(raw).__name__}"
        )
    extra = set(raw) - set(_FINDING_FIELDS)
    if extra:
        raise CritiqueSchemaError(
            f"findings[{index}] has unexpected fields: {sorted(extra)}"
        )
    section = str(_require_field(raw, "section", str, ctx))
    issue = str(_require_field(raw, "issue", str, ctx))
    sev_raw = str(_require_field(raw, "severity", str, ctx))
    suggestion = str(_require_field(raw, "suggestion", str, ctx))

    if sev_raw not in _VALID_SEVERITIES:
        raise CritiqueValueError(
            f"findings[{index}].severity must be one of {sorted(_VALID_SEVERITIES)}, "
            f"got: {sev_raw!r}"
        )
    return CritiqueFinding(
        section=section,
        issue=issue,
        severity=Severity(sev_raw),
        suggestion=suggestion,
    )


def _parse_contradiction(raw: object, index: int) -> Contradiction:
    """Parse one contradiction dict from the agent response.

    Args:
        raw: Value from the contradictions list (must be a dict).
        index: Position in the contradictions list, for error messages.

    Returns:
        Constructed Contradiction.

    Raises:
        CritiqueSchemaError: For type or field errors.
    """
    ctx = f"contradictions[{index}]"
    if not isinstance(raw, dict):
        raise CritiqueSchemaError(
            f"contradictions[{index}] must be an object, got {type(raw).__name__}"
        )
    extra = set(raw) - set(_CONTRADICTION_FIELDS)
    if extra:
        raise CritiqueSchemaError(
            f"contradictions[{index}] has unexpected fields: {sorted(extra)}"
        )
    return Contradiction(
        location_a=str(_require_field(raw, "location_a", str, ctx)),
        location_b=str(_require_field(raw, "location_b", str, ctx)),
        nature=str(_require_field(raw, "nature", str, ctx)),
    )


def parse_critique_response(raw: str) -> SemanticCritique:
    """Parse a raw agent response string into a SemanticCritique.

    Applies noise stripping before JSON parsing; see module docstring for the
    exact stripping rules.

    Args:
        raw: Raw string returned by the agent.

    Returns:
        Fully validated SemanticCritique.

    Raises:
        CritiqueJSONError: Response is not valid JSON after stripping. Message
            includes up to 200 characters of raw input and the decoder's error
            position.
        CritiqueSchemaError: JSON parsed but does not match the required schema.
            Message names the specific field and what was wrong.
        CritiqueValueError: Schema matches but a value is out of the allowed
            range. Message includes the offending value.
    """
    payload = decode_json_or_raise(raw, CritiqueJSONError)

    if not isinstance(payload, dict):
        raise CritiqueSchemaError(
            f"Agent response must be a JSON object, got: {type(payload).__name__}"
        )

    extra_top = set(payload) - set(_REQUIRED_FIELDS)
    if extra_top:
        raise CritiqueSchemaError(
            f"Response has unexpected top-level fields: {sorted(extra_top)}"
        )

    clarity_raw = _require_field(payload, "clarity_score", int)
    completeness_raw = _require_field(payload, "completeness_score", int)
    executability_raw = _require_field(payload, "executability_score", int)
    assert isinstance(clarity_raw, int)
    assert isinstance(completeness_raw, int)
    assert isinstance(executability_raw, int)
    clarity = clarity_raw
    completeness = completeness_raw
    executability = executability_raw

    for name, value in [
        ("clarity_score", clarity),
        ("completeness_score", completeness),
        ("executability_score", executability),
    ]:
        if value < 0 or value > 100:
            raise CritiqueValueError(
                f"Field '{name}' must be in range 0-100, got: {value}"
            )

    raw_findings = _require_field(payload, "findings", list)
    assert isinstance(raw_findings, list)
    enforce_list_cap(len(raw_findings), "findings", CritiqueSchemaError)
    findings = tuple(_parse_finding(item, i) for i, item in enumerate(raw_findings))

    raw_missing = _require_field(payload, "missing_context", list)
    assert isinstance(raw_missing, list)
    enforce_list_cap(len(raw_missing), "missing_context", CritiqueSchemaError)
    for i, item in enumerate(raw_missing):
        if not isinstance(item, str):
            raise CritiqueSchemaError(
                f"missing_context[{i}] must be str, got {type(item).__name__}: {item!r}"
            )
    missing_context = tuple(str(s) for s in raw_missing)

    raw_contradictions = _require_field(payload, "contradictions", list)
    assert isinstance(raw_contradictions, list)
    enforce_list_cap(len(raw_contradictions), "contradictions", CritiqueSchemaError)
    contradictions = tuple(
        _parse_contradiction(item, i) for i, item in enumerate(raw_contradictions)
    )

    return SemanticCritique(
        clarity_score=clarity,
        completeness_score=completeness,
        executability_score=executability,
        findings=findings,
        missing_context=missing_context,
        contradictions=contradictions,
    )
