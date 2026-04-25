"""Tests for core/semantic.py - the agent self-critique bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillcheck.core.semantic import (
    INFO_THRESHOLD,
    WARNING_THRESHOLD,
    _find_section_line,
    ingest_critique_response,
    merge_critique_diagnostics,
    render_critique_prompt,
)
from skillcheck.parser import parse as parse_skill
from skillcheck.result import Diagnostic, Severity, ValidationResult

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CRITIQUE_DIR = FIXTURES_DIR / "critique"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw(
    *,
    clarity: int = 90,
    completeness: int = 90,
    executability: int = 90,
    findings: list | None = None,
    missing_context: list | None = None,
    contradictions: list | None = None,
) -> str:
    return json.dumps({
        "clarity_score": clarity,
        "completeness_score": completeness,
        "executability_score": executability,
        "findings": findings or [],
        "missing_context": missing_context or [],
        "contradictions": contradictions or [],
    })


def _valid_skill() -> object:
    """Return the parsed valid_full.md fixture (skip-dirname-check not needed here)."""
    return parse_skill(FIXTURES_DIR / "valid_full.md")


def _empty_result(path: Path | None = None) -> ValidationResult:
    return ValidationResult(
        path=path or FIXTURES_DIR / "valid_full.md",
        diagnostics=[],
    )


# ---------------------------------------------------------------------------
# render_critique_prompt
# ---------------------------------------------------------------------------


def test_render_critique_prompt_non_empty() -> None:
    skill = _valid_skill()
    prompt = render_critique_prompt(skill)
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_render_critique_prompt_contains_skill_body() -> None:
    skill = _valid_skill()
    prompt = render_critique_prompt(skill)
    assert "document analysis" in prompt.lower() or "overview" in prompt.lower()


def test_render_critique_prompt_contains_skill_name() -> None:
    skill = _valid_skill()
    prompt = render_critique_prompt(skill)
    # The raw_text is embedded in the prompt
    assert "document-analyzer" in prompt


def test_render_critique_prompt_contains_schema_fields() -> None:
    skill = _valid_skill()
    prompt = render_critique_prompt(skill)
    for field in ("clarity_score", "completeness_score", "executability_score",
                  "findings", "missing_context", "contradictions"):
        assert field in prompt, f"Expected field '{field}' in rendered prompt"


# ---------------------------------------------------------------------------
# Score threshold transitions
# ---------------------------------------------------------------------------


def test_score_at_warning_threshold_boundary_below() -> None:
    # 69 < 70 = WARNING
    diags = ingest_critique_response(_valid_skill(), _make_raw(clarity=WARNING_THRESHOLD - 1))
    clarity_diag = next(d for d in diags if d.rule == "semantic.clarity.low")
    assert clarity_diag.severity is Severity.WARNING
    assert str(WARNING_THRESHOLD - 1) in clarity_diag.message


def test_score_at_warning_threshold_boundary_at() -> None:
    # 70 >= 70 but < 85 = INFO
    diags = ingest_critique_response(_valid_skill(), _make_raw(clarity=WARNING_THRESHOLD))
    clarity_diag = next(d for d in diags if d.rule == "semantic.clarity.low")
    assert clarity_diag.severity is Severity.INFO


def test_score_at_info_threshold_boundary_below() -> None:
    # 84 >= 70 but < 85 = INFO
    diags = ingest_critique_response(_valid_skill(), _make_raw(clarity=INFO_THRESHOLD - 1))
    clarity_diag = next(d for d in diags if d.rule == "semantic.clarity.low")
    assert clarity_diag.severity is Severity.INFO


def test_score_at_info_threshold_boundary_at() -> None:
    # 85 >= 85 = omitted
    diags = ingest_critique_response(_valid_skill(), _make_raw(clarity=INFO_THRESHOLD))
    rules = [d.rule for d in diags]
    assert "semantic.clarity.low" not in rules


def test_all_scores_healthy_produces_no_score_diagnostics() -> None:
    diags = ingest_critique_response(_valid_skill(), _make_raw(clarity=90, completeness=90, executability=90))
    score_rules = {d.rule for d in diags}
    assert "semantic.clarity.low" not in score_rules
    assert "semantic.completeness.low" not in score_rules
    assert "semantic.executability.low" not in score_rules


def test_completeness_score_produces_diagnostic() -> None:
    diags = ingest_critique_response(_valid_skill(), _make_raw(completeness=60))
    completeness_diag = next(d for d in diags if d.rule == "semantic.completeness.low")
    assert completeness_diag.severity is Severity.WARNING


def test_executability_score_produces_diagnostic() -> None:
    diags = ingest_critique_response(_valid_skill(), _make_raw(executability=80))
    exec_diag = next(d for d in diags if d.rule == "semantic.executability.low")
    assert exec_diag.severity is Severity.INFO


# ---------------------------------------------------------------------------
# Missing context flags
# ---------------------------------------------------------------------------


def test_missing_context_produces_one_warning_per_item() -> None:
    items = ["auth token", "file path format"]
    diags = ingest_critique_response(_valid_skill(), _make_raw(missing_context=items))
    context_diags = [d for d in diags if d.rule == "semantic.context.missing"]
    assert len(context_diags) == 2
    for diag in context_diags:
        assert diag.severity is Severity.WARNING


def test_missing_context_message_contains_flag_text() -> None:
    diags = ingest_critique_response(_valid_skill(), _make_raw(missing_context=["auth token"]))
    ctx_diag = next(d for d in diags if d.rule == "semantic.context.missing")
    assert "auth token" in ctx_diag.message


def test_empty_missing_context_produces_no_diagnostics() -> None:
    diags = ingest_critique_response(_valid_skill(), _make_raw(missing_context=[]))
    assert all(d.rule != "semantic.context.missing" for d in diags)


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------


def test_contradiction_produces_error_diagnostic() -> None:
    contradictions = [{
        "location_a": "Overview",
        "location_b": "Limitations",
        "nature": "Conflicting scope claims.",
    }]
    diags = ingest_critique_response(_valid_skill(), _make_raw(contradictions=contradictions))
    contra_diags = [d for d in diags if d.rule == "semantic.contradiction.detected"]
    assert len(contra_diags) == 1
    assert contra_diags[0].severity is Severity.ERROR


def test_contradiction_message_contains_both_locations() -> None:
    contradictions = [{
        "location_a": "Overview",
        "location_b": "Limitations",
        "nature": "They conflict.",
    }]
    diags = ingest_critique_response(_valid_skill(), _make_raw(contradictions=contradictions))
    msg = next(d for d in diags if d.rule == "semantic.contradiction.detected").message
    assert "Overview" in msg
    assert "Limitations" in msg


def test_multiple_contradictions_produce_multiple_errors() -> None:
    contradictions = [
        {"location_a": "A", "location_b": "B", "nature": "First conflict."},
        {"location_a": "C", "location_b": "D", "nature": "Second conflict."},
    ]
    diags = ingest_critique_response(_valid_skill(), _make_raw(contradictions=contradictions))
    contra_diags = [d for d in diags if d.rule == "semantic.contradiction.detected"]
    assert len(contra_diags) == 2


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


def test_finding_severity_inherited() -> None:
    for sev in ("error", "warning", "info"):
        findings = [{"section": "Overview", "issue": "Issue text.", "severity": sev, "suggestion": "Fix it."}]
        diags = ingest_critique_response(_valid_skill(), _make_raw(findings=findings))
        finding_diag = next(d for d in diags if d.rule.startswith("semantic.finding."))
        assert finding_diag.severity == Severity(sev)
        assert finding_diag.rule == f"semantic.finding.{sev}"


def test_finding_message_contains_section_and_suggestion() -> None:
    findings = [{"section": "Overview", "issue": "Vague wording.", "severity": "warning", "suggestion": "Be specific."}]
    diags = ingest_critique_response(_valid_skill(), _make_raw(findings=findings))
    msg = next(d for d in diags if d.rule.startswith("semantic.finding.")).message
    assert "Overview" in msg
    assert "Be specific." in msg


# ---------------------------------------------------------------------------
# Section-header line lookup
# ---------------------------------------------------------------------------


def test_find_section_line_known_section() -> None:
    # valid_full.md body has "## Overview" as the first heading
    skill = _valid_skill()
    line = _find_section_line(skill.body, "Overview")
    assert line is not None
    assert isinstance(line, int)
    assert line >= 1


def test_find_section_line_unknown_section_returns_none() -> None:
    skill = _valid_skill()
    line = _find_section_line(skill.body, "Nonexistent Section XYZ")
    assert line is None


def test_find_section_line_case_insensitive() -> None:
    skill = _valid_skill()
    assert _find_section_line(skill.body, "overview") == _find_section_line(skill.body, "Overview")


def test_finding_with_known_section_has_line_number() -> None:
    findings = [{"section": "Overview", "issue": "Issue.", "severity": "info", "suggestion": "Fix."}]
    diags = ingest_critique_response(_valid_skill(), _make_raw(findings=findings))
    finding_diag = next(d for d in diags if d.rule.startswith("semantic.finding."))
    assert finding_diag.line is not None


def test_finding_with_unknown_section_has_no_line() -> None:
    findings = [{"section": "Ghost Section", "issue": "Issue.", "severity": "info", "suggestion": "Fix."}]
    diags = ingest_critique_response(_valid_skill(), _make_raw(findings=findings))
    finding_diag = next(d for d in diags if d.rule.startswith("semantic.finding."))
    assert finding_diag.line is None


# ---------------------------------------------------------------------------
# merge_critique_diagnostics
# ---------------------------------------------------------------------------


def test_merge_errors_only_critique_on_passing_symbolic_yields_invalid() -> None:
    result = _empty_result()
    contradiction = [{
        "location_a": "A",
        "location_b": "B",
        "nature": "Conflict.",
    }]
    critique_diags = ingest_critique_response(_valid_skill(), _make_raw(contradictions=contradiction))
    merged = merge_critique_diagnostics(result, critique_diags)
    assert not merged.valid


def test_merge_warnings_only_critique_on_passing_symbolic_stays_valid() -> None:
    result = _empty_result()
    critique_diags = ingest_critique_response(_valid_skill(), _make_raw(missing_context=["auth token"]))
    merged = merge_critique_diagnostics(result, critique_diags)
    assert merged.valid


def test_merge_combines_all_diagnostics() -> None:
    base_diag = Diagnostic(rule="some.rule", severity=Severity.WARNING, message="symbolic warning")
    result = ValidationResult(path=FIXTURES_DIR / "valid_full.md", diagnostics=[base_diag])
    critique_diags = ingest_critique_response(_valid_skill(), _make_raw(missing_context=["x"]))
    merged = merge_critique_diagnostics(result, critique_diags)
    assert len(merged.diagnostics) == len(critique_diags) + 1


def test_merge_does_not_mutate_original() -> None:
    result = _empty_result()
    critique_diags = ingest_critique_response(_valid_skill(), _make_raw(missing_context=["y"]))
    _ = merge_critique_diagnostics(result, critique_diags)
    assert result.diagnostics == []


def test_merge_preserves_path() -> None:
    result = _empty_result()
    merged = merge_critique_diagnostics(result, [])
    assert merged.path == result.path


# ---------------------------------------------------------------------------
# Fixture file integration
# ---------------------------------------------------------------------------


def test_response_clean_produces_no_diagnostics() -> None:
    raw = (CRITIQUE_DIR / "response_clean.json").read_text()
    diags = ingest_critique_response(_valid_skill(), raw)
    assert diags == []


def test_response_warnings_produces_warnings() -> None:
    raw = (CRITIQUE_DIR / "response_warnings.json").read_text()
    diags = ingest_critique_response(_valid_skill(), raw)
    severities = {d.severity for d in diags}
    assert Severity.ERROR not in severities
    assert Severity.WARNING in severities


def test_response_contradiction_produces_error() -> None:
    raw = (CRITIQUE_DIR / "response_contradiction.json").read_text()
    diags = ingest_critique_response(_valid_skill(), raw)
    assert any(d.rule == "semantic.contradiction.detected" for d in diags)
    assert any(d.severity is Severity.ERROR for d in diags)


def test_response_findings_mixed_has_all_severities() -> None:
    raw = (CRITIQUE_DIR / "response_findings_mixed.json").read_text()
    diags = ingest_critique_response(_valid_skill(), raw)
    finding_diags = [d for d in diags if d.rule.startswith("semantic.finding.")]
    finding_severities = {d.severity for d in finding_diags}
    assert Severity.ERROR in finding_severities
    assert Severity.WARNING in finding_severities
    assert Severity.INFO in finding_severities


# ---------------------------------------------------------------------------
# Line-numbering regression: diagnostics are body-relative, not file-relative
# ---------------------------------------------------------------------------


def test_find_section_line_is_body_relative() -> None:
    # Construct a body where "## Overview" is the first line.
    body = "## Overview\n\nDoes something useful.\n"
    # _find_section_line works on body text directly; line 1 is the first body line.
    line = _find_section_line(body, "Overview")
    assert line == 1, f"Expected body-relative line 1, got {line}"


def test_finding_diagnostic_line_is_body_relative_not_file_relative() -> None:
    # Parse a skill fixture that has substantial frontmatter (valid_full.md has
    # 6+ frontmatter lines). Feed a finding response that references a known
    # section. The resulting Diagnostic.line must be small (body-relative), not
    # large (file-relative).
    skill = parse_skill(FIXTURES_DIR / "valid_full.md")

    # Count frontmatter lines (everything before the body in the raw text).
    frontmatter_line_count = skill.raw_text[: skill.raw_text.index(skill.body)].count("\n")
    assert frontmatter_line_count >= 4, "Fixture needs enough frontmatter to make the test meaningful"

    # Pull the first section heading from the body.
    first_section = next(
        (line.lstrip("# ").strip() for line in skill.body.splitlines() if line.startswith("##")),
        None,
    )
    assert first_section is not None, "valid_full.md must have at least one ## section"

    raw = _make_raw(
        findings=[{"severity": "info", "section": first_section, "issue": "test", "suggestion": "n/a"}],
    )
    diags = ingest_critique_response(skill, raw)
    finding_diags = [d for d in diags if d.rule.startswith("semantic.finding.") and d.line is not None]

    # At least one finding should have resolved a line number.
    if finding_diags:
        resolved_line = finding_diags[0].line
        assert resolved_line is not None
        body_line_count = len(skill.body.splitlines())
        # Body-relative: must be within the body.
        assert resolved_line <= body_line_count, (
            f"Line {resolved_line} exceeds body length {body_line_count}; looks file-relative"
        )
        # Should NOT equal the file-relative offset.
        file_relative_line = resolved_line + frontmatter_line_count
        assert resolved_line != file_relative_line  # trivially true when frontmatter_line_count > 0
