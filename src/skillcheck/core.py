from __future__ import annotations

from pathlib import Path

from skillcheck.parser import ParseError, parse
from skillcheck.result import Diagnostic, Severity, ValidationResult
from skillcheck.rules import get_rules


def validate(
    path: Path,
    *,
    max_lines: int | None = None,
    max_tokens: int | None = None,
    ignore_prefixes: list[str] | None = None,
) -> ValidationResult:
    """Validate a single SKILL.md file and return a ValidationResult.

    Args:
        path: Path to the SKILL.md file to validate.
        max_lines: Override the default line-count threshold.
        max_tokens: Override the default token-count threshold.
        ignore_prefixes: Suppress any diagnostic whose rule ID starts with one of these prefixes.
    """
    try:
        skill = parse(path)
    except ParseError as exc:
        return ValidationResult(
            path=path,
            diagnostics=[Diagnostic(
                rule="parse.error",
                severity=Severity.ERROR,
                message=str(exc),
            )],
        )

    rules = get_rules(max_lines=max_lines, max_tokens=max_tokens)
    diagnostics: list[Diagnostic] = [
        diagnostic
        for rule in rules
        for diagnostic in rule(skill)
    ]

    if ignore_prefixes:
        diagnostics = [
            d for d in diagnostics
            if not any(d.rule.startswith(prefix) for prefix in ignore_prefixes)
        ]

    return ValidationResult(path=path, diagnostics=diagnostics)
