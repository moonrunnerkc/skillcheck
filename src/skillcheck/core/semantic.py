"""Semantic validation bridge: converts agent self-critique into Diagnostics.

This module is the glue between the prompt/parser contract established in
Phase 1A and the ValidationResult pipeline that already exists in the CLI.
No I/O happens here except inside `ingest_critique_response` where the raw
string is parsed. All three public functions are pure given their inputs.
"""

import re

from skillcheck.agents.base import SelfCritiquePrompt
from skillcheck.agents.parser import parse_critique_response
from skillcheck.agents.schema import SemanticCritique
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity, ValidationResult

# Score thresholds. Not configurable in Phase 1B; tune in Phase 2 after
# seeing real critique output.
WARNING_THRESHOLD = 70
INFO_THRESHOLD = 85

# Matches markdown section headings at ## or ### depth.
_HEADING_RE = re.compile(r"^#{2,3}\s+(.+)", re.MULTILINE)



def render_critique_prompt(skill: ParsedSkill) -> str:
    """Build the agent self-critique prompt for a parsed skill.

    Uses the Claude prompt template (hardcoded for Phase 1B; Phase 1C adds
    agent selection). Pure: no I/O, no side effects.

    Args:
        skill: Parsed skill file.

    Returns:
        Full prompt string ready to be pasted into an agent context.
    """
    return SelfCritiquePrompt().render(skill)


def _score_diagnostic(rule: str, score: int, label: str) -> Diagnostic | None:
    """Return a Diagnostic for a score field, or None if the score is healthy.

    Args:
        rule: Rule ID, e.g. ``semantic.clarity.low``.
        score: Numeric score 0-100.
        label: Human-readable label for the score dimension.

    Returns:
        Diagnostic with WARNING/INFO severity, or None if score >= INFO_THRESHOLD.
    """
    if score < WARNING_THRESHOLD:
        return Diagnostic(
            rule=rule,
            severity=Severity.WARNING,
            message=f"{label} score is {score} (below {WARNING_THRESHOLD}); review the skill for clarity.",
        )
    if score < INFO_THRESHOLD:
        return Diagnostic(
            rule=rule,
            severity=Severity.INFO,
            message=f"{label} score is {score} (below {INFO_THRESHOLD}); minor improvements possible.",
        )
    return None


def _find_section_line(body: str, section_name: str) -> int | None:
    """Return the 1-based line number of a section heading in the skill body.

    Scans for a markdown heading (## or ###) whose text matches *section_name*
    case-insensitively. Returns None if no match is found.

    Args:
        body: Skill body text (everything after the frontmatter).
        section_name: Heading text to search for.

    Returns:
        1-based line number, or None.
    """
    needle = section_name.strip().lower()
    for i, line in enumerate(body.splitlines(), start=1):
        m = _HEADING_RE.match(line)
        if m and m.group(1).strip().lower() == needle:
            return i
    return None


def ingest_critique_response(skill: ParsedSkill, raw: str) -> list[Diagnostic]:
    """Parse a raw agent critique response and convert it to Diagnostics.

    Calls ``parse_critique_response`` from the Phase 1A parser. Each parser
    exception bubbles up unchanged so the CLI can decide how to surface it.

    Score-derived diagnostics:
        - ``semantic.clarity.low``: WARNING if clarity_score < 70, INFO if 70-84.
        - ``semantic.completeness.low``: WARNING if completeness_score < 70, INFO if 70-84.
        - ``semantic.executability.low``: WARNING if executability_score < 70, INFO if 70-84.

    Other diagnostics:
        - ``semantic.context.missing``: one WARNING per ``missing_context`` item.
        - ``semantic.contradiction.detected``: one ERROR per ``Contradiction``.
        - ``semantic.finding.<severity>``: one diagnostic per ``CritiqueFinding``,
          severity inherited from the finding.

    The ``line`` field is None for score/context/contradiction diagnostics.
    Findings that name a recognizable section get a best-effort line number.

    Args:
        skill: Parsed skill, used for section-header line lookups.
        raw: Raw JSON string from the agent.

    Returns:
        List of Diagnostics derived from the critique. May be empty.

    Raises:
        CritiqueParseError: Re-raised directly from the parser on any failure.
    """
    critique: SemanticCritique = parse_critique_response(raw)
    diagnostics: list[Diagnostic] = []

    for rule, score, label in [
        ("semantic.clarity.low", critique.clarity_score, "Clarity"),
        ("semantic.completeness.low", critique.completeness_score, "Completeness"),
        ("semantic.executability.low", critique.executability_score, "Executability"),
    ]:
        d = _score_diagnostic(rule, score, label)
        if d is not None:
            diagnostics.append(d)

    for item in critique.missing_context:
        diagnostics.append(Diagnostic(
            rule="semantic.context.missing",
            severity=Severity.WARNING,
            message=f"Missing context: {item}",
        ))

    for contradiction in critique.contradictions:
        diagnostics.append(Diagnostic(
            rule="semantic.contradiction.detected",
            severity=Severity.ERROR,
            message=(
                f"Contradiction between '{contradiction.location_a}' and "
                f"'{contradiction.location_b}': {contradiction.nature}"
            ),
        ))

    for finding in critique.findings:
        line = _find_section_line(skill.body, finding.section)
        diagnostics.append(Diagnostic(
            rule=f"semantic.finding.{finding.severity.value}",
            severity=finding.severity,
            message=f"[{finding.section}] {finding.issue} — {finding.suggestion}",
            line=line,
        ))

    return diagnostics


def merge_critique_diagnostics(
    result: ValidationResult,
    critique_diagnostics: list[Diagnostic],
) -> ValidationResult:
    """Return a new ValidationResult with symbolic and semantic diagnostics merged.

    The original result is not mutated (it's a frozen dataclass). ``valid`` is
    recomputed from the merged list: True iff no ERROR-severity diagnostics are
    present.

    Args:
        result: Existing symbolic validation result.
        critique_diagnostics: Diagnostics from ``ingest_critique_response``.

    Returns:
        New ValidationResult combining both diagnostic lists.
    """
    merged = list(result.diagnostics) + critique_diagnostics
    return ValidationResult(path=result.path, diagnostics=merged)
