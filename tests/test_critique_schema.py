"""Tests for SemanticCritique, CritiqueFinding, and Contradiction dataclasses."""

from __future__ import annotations

import dataclasses

import pytest

from skillcheck.agents.schema import (
    Contradiction,
    CritiqueFinding,
    SemanticCritique,
)
from skillcheck.result import Severity


# ---------------------------------------------------------------------------
# CritiqueFinding
# ---------------------------------------------------------------------------


def test_critique_finding_construction() -> None:
    finding = CritiqueFinding(
        section="Overview",
        issue="Unclear trigger condition",
        severity=Severity.WARNING,
        suggestion="Add 'Use this skill when...' phrasing.",
    )
    assert finding.section == "Overview"
    assert finding.severity is Severity.WARNING


def test_critique_finding_invalid_severity() -> None:
    with pytest.raises(ValueError, match="severity"):
        CritiqueFinding(
            section="Overview",
            issue="x",
            severity="bad",  # type: ignore[arg-type]
            suggestion="y",
        )


def test_critique_finding_is_frozen() -> None:
    finding = CritiqueFinding(
        section="S", issue="I", severity=Severity.INFO, suggestion="X"
    )
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        finding.section = "other"  # type: ignore[misc]


def test_critique_finding_equality() -> None:
    a = CritiqueFinding(section="S", issue="I", severity=Severity.INFO, suggestion="X")
    b = CritiqueFinding(section="S", issue="I", severity=Severity.INFO, suggestion="X")
    assert a == b


def test_critique_finding_hashable() -> None:
    finding = CritiqueFinding(
        section="S", issue="I", severity=Severity.INFO, suggestion="X"
    )
    assert hash(finding) == hash(finding)
    s = {finding}
    assert finding in s


def test_critique_finding_asdict_roundtrip() -> None:
    finding = CritiqueFinding(
        section="Body",
        issue="Missing output definition",
        severity=Severity.ERROR,
        suggestion="State what the skill returns.",
    )
    d = dataclasses.asdict(finding)
    assert d["section"] == "Body"
    # Severity is a str-enum so asdict preserves the value; reconstruct manually.
    reconstructed = CritiqueFinding(
        section=d["section"],
        issue=d["issue"],
        severity=Severity(d["severity"]),
        suggestion=d["suggestion"],
    )
    assert reconstructed == finding


# ---------------------------------------------------------------------------
# Contradiction
# ---------------------------------------------------------------------------


def test_contradiction_construction() -> None:
    c = Contradiction(
        location_a="Section A says offline-only",
        location_b="Section B calls external API",
        nature="Cannot be offline-only and call a network API simultaneously.",
    )
    assert c.nature.startswith("Cannot")


def test_contradiction_is_frozen() -> None:
    c = Contradiction(location_a="a", location_b="b", nature="n")
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        c.nature = "other"  # type: ignore[misc]


def test_contradiction_hashable() -> None:
    c = Contradiction(location_a="a", location_b="b", nature="n")
    assert {c} == {c}


def test_contradiction_asdict_roundtrip() -> None:
    c = Contradiction(location_a="a", location_b="b", nature="n")
    d = dataclasses.asdict(c)
    assert Contradiction(**d) == c


# ---------------------------------------------------------------------------
# SemanticCritique (score validation)
# ---------------------------------------------------------------------------


def _valid_critique(**overrides: object) -> SemanticCritique:
    defaults: dict[str, object] = dict(
        clarity_score=80,
        completeness_score=70,
        executability_score=90,
        findings=(),
        missing_context=(),
        contradictions=(),
    )
    defaults.update(overrides)
    return SemanticCritique(**defaults)  # type: ignore[arg-type]


def test_semantic_critique_valid_construction() -> None:
    c = _valid_critique()
    assert c.clarity_score == 80
    assert c.findings == ()


def test_semantic_critique_score_zero_boundary() -> None:
    c = _valid_critique(clarity_score=0)
    assert c.clarity_score == 0


def test_semantic_critique_score_hundred_boundary() -> None:
    c = _valid_critique(completeness_score=100)
    assert c.completeness_score == 100


def test_semantic_critique_clarity_below_zero_raises() -> None:
    with pytest.raises(ValueError, match="clarity_score.*-1"):
        _valid_critique(clarity_score=-1)


def test_semantic_critique_clarity_above_hundred_raises() -> None:
    with pytest.raises(ValueError, match="clarity_score.*101"):
        _valid_critique(clarity_score=101)


def test_semantic_critique_completeness_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="completeness_score"):
        _valid_critique(completeness_score=200)


def test_semantic_critique_executability_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="executability_score"):
        _valid_critique(executability_score=-5)


def test_semantic_critique_score_type_error_includes_bad_value() -> None:
    with pytest.raises(ValueError, match="clarity_score.*str.*'high'"):
        _valid_critique(clarity_score="high")  # type: ignore[arg-type]


def test_semantic_critique_bool_rejected_as_score() -> None:
    # bool is int subclass; should still raise
    with pytest.raises(ValueError, match="clarity_score"):
        _valid_critique(clarity_score=True)


def test_semantic_critique_is_frozen() -> None:
    c = _valid_critique()
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        c.clarity_score = 50  # type: ignore[misc]


def test_semantic_critique_with_findings() -> None:
    finding = CritiqueFinding(
        section="Body",
        issue="Vague",
        severity=Severity.WARNING,
        suggestion="Be specific.",
    )
    c = _valid_critique(findings=(finding,))
    assert len(c.findings) == 1
    assert c.findings[0].section == "Body"


def test_semantic_critique_with_contradictions() -> None:
    contradiction = Contradiction(location_a="a", location_b="b", nature="conflict")
    c = _valid_critique(contradictions=(contradiction,))
    assert len(c.contradictions) == 1


def test_semantic_critique_asdict_roundtrip() -> None:
    finding = CritiqueFinding(
        section="S", issue="I", severity=Severity.INFO, suggestion="X"
    )
    c = _valid_critique(findings=(finding,), missing_context=("needs auth context",))
    d = dataclasses.asdict(c)
    assert d["clarity_score"] == 80
    assert d["findings"][0]["section"] == "S"
    assert d["missing_context"][0] == "needs auth context"
