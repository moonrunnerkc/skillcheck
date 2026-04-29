"""Template detection rule (info-level signal)."""

from __future__ import annotations

from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity
from skillcheck.template_detection import is_template


def check_template_detected(skill: ParsedSkill) -> list[Diagnostic]:
    if not is_template(skill):
        return []
    return [Diagnostic(
        rule="template.detected",
        severity=Severity.INFO,
        message=(
            "Detected placeholder content; deployment-blocking checks "
            "(directory-name match, VS Code dirname, description quality) "
            "are skipped for template files. Copy this file and replace "
            "placeholders before deploying."
        ),
        line=None,
        context=None,
        source="advisory",
        confidence="medium",
    )]
