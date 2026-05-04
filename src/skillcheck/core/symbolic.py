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
    skip_dirname_check: bool = False,
    skip_ref_check: bool = False,
    min_desc_score: int | None = None,
    strict_vscode: bool = False,
    strict_cursor: bool = False,
    strict_all: bool = False,
    target_agent: str = "all",
) -> ValidationResult:
    """Validate a single SKILL.md file using deterministic symbolic rules.

    Args:
        path: Path to the SKILL.md file to validate.
        max_lines: Override the default line-count threshold.
        max_tokens: Override the default token-count threshold.
        ignore_prefixes: Suppress diagnostics whose rule IDs match these prefixes.
        skip_dirname_check: Skip directory-name matching.
        skip_ref_check: Skip file reference validation.
        min_desc_score: Minimum description quality score.
        strict_vscode: Promote VS Code compatibility issues to errors.
        strict_cursor: Promote Cursor compatibility issues to errors.
        strict_all: Enable all strict modes (warnings-as-errors + strict VS Code + strict Cursor).
        target_agent: Scope compatibility checks to an agent target.

    Returns:
        Validation result for the provided path.
    """
    try:
        skill = parse(path)
    except ParseError as exc:
        return ValidationResult(
            path=path,
            diagnostics=[
                Diagnostic(
                    rule="parse.error",
                    severity=Severity.ERROR,
                    message=str(exc),
                )
            ],
        )

    rules = get_rules(
        max_lines=max_lines,
        max_tokens=max_tokens,
        skip_dirname_check=skip_dirname_check,
        skip_ref_check=skip_ref_check,
        min_desc_score=min_desc_score,
        strict_vscode=strict_vscode or strict_all,
        strict_cursor=strict_cursor or strict_all,
        strict_all=strict_all,
        target_agent=target_agent,
    )
    diagnostics: list[Diagnostic] = [
        diagnostic for rule in rules for diagnostic in rule(skill)
    ]

    if ignore_prefixes:
        diagnostics = [
            d
            for d in diagnostics
            if not any(d.rule.startswith(prefix) for prefix in ignore_prefixes)
        ]

    return ValidationResult(path=path, diagnostics=diagnostics)