"""Parser for agent self-critique JSON responses.

Converts raw agent output into a SemanticCritique. Handles the three failure
modes that are realistically distinct: invalid JSON, schema mismatch, and
out-of-range values.

Stripping rules applied before JSON parsing (in order):
  1. Leading and trailing whitespace.
  2. A single markdown code fence block: ```json...``` or ```...``` wrapping
     the entire remaining content. Only one level of fencing is stripped; a
     fence inside the JSON object is left alone.
  3. Any prose before the first '{' on a standalone line. Specifically, the
     content is sliced to begin at the first occurrence of '{' that is either
     at the start of the string or preceded only by whitespace on its line.

These rules are deterministic and applied in sequence. No regex substitution
happens inside the JSON body itself.
"""

from __future__ import annotations

import json
import re

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

# Matches a full ```json ... ``` or ``` ... ``` fence wrapping the entire content.
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


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


def _strip_noise(raw: str) -> str:
    """Remove LLM response noise before attempting JSON parsing.

    Stripping steps (applied in order):
    1. Strip leading/trailing whitespace.
    2. Strip a single markdown code fence (```json or ```) wrapping the whole content.
    3. Strip any prose before the first '{'.
    """
    text = raw.strip()

    fence_match = _FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()

    brace_pos = text.find("{")
    if brace_pos > 0:
        text = text[brace_pos:]

    return text


def _require_field(obj: dict, key: str, expected_type: type | tuple[type, ...], context: str = "") -> object:
    """Extract a required field with type checking.

    Args:
        obj: Mapping to extract from.
        key: Required field name.
        expected_type: Acceptable Python type(s).
        context: Optional prefix for error messages, e.g. "findings[0]".

    Returns:
        The field value.

    Raises:
        CritiqueSchemaError: If field is missing, has wrong type, or (for int)
            is actually a bool (which is an int subclass but not a score).
    """
    full_key = f"{context}.{key}" if context else key
    if key not in obj:
        raise CritiqueSchemaError(f"Missing required field '{full_key}'")
    value = obj[key]
    # bool is a subclass of int; reject it for score fields
    if expected_type is int and isinstance(value, bool):
        raise CritiqueSchemaError(
            f"Field '{full_key}' must be int, got bool: {value!r}"
        )
    if not isinstance(value, expected_type):  # type: ignore[arg-type]
        type_name = (
            expected_type.__name__
            if isinstance(expected_type, type)
            else "/".join(t.__name__ for t in expected_type)
        )
        raise CritiqueSchemaError(
            f"Field '{full_key}' must be {type_name}, got {type(value).__name__}: {value!r}"
        )
    return value


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
    cleaned = _strip_noise(raw)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as err:
        preview = raw[:200]
        raise CritiqueJSONError(
            f"Agent response is not valid JSON (at position {err.pos}). "
            f"First 200 chars received: {preview!r}"
        ) from err

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
    findings = tuple(_parse_finding(item, i) for i, item in enumerate(raw_findings))

    raw_missing = _require_field(payload, "missing_context", list)
    assert isinstance(raw_missing, list)
    for i, item in enumerate(raw_missing):
        if not isinstance(item, str):
            raise CritiqueSchemaError(
                f"missing_context[{i}] must be str, got {type(item).__name__}: {item!r}"
            )
    missing_context = tuple(str(s) for s in raw_missing)

    raw_contradictions = _require_field(payload, "contradictions", list)
    assert isinstance(raw_contradictions, list)
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
