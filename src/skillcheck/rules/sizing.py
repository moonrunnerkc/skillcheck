from __future__ import annotations

from typing import Callable

from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity
from skillcheck.tokenizer import estimate_tokens


def make_line_count_rule(max_lines: int) -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Return a rule function that warns when the total file line count exceeds max_lines."""

    def check_body_line_count(skill: ParsedSkill) -> list[Diagnostic]:
        total_lines = len(skill.raw_text.splitlines())
        if total_lines > max_lines:
            return [Diagnostic(
                rule="sizing.body.line-count",
                severity=Severity.WARNING,
                message=(
                    f"File exceeds the recommended {max_lines}-line limit "
                    f"(got {total_lines} lines). Consider splitting into smaller skills."
                ),
            )]
        return []

    check_body_line_count.__name__ = "check_body_line_count"
    return check_body_line_count


def make_token_estimate_rule(max_tokens: int) -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Return a rule function that warns when the estimated token count exceeds max_tokens."""

    def check_body_token_estimate(skill: ParsedSkill) -> list[Diagnostic]:
        token_count = estimate_tokens(skill.raw_text)
        if token_count > max_tokens:
            return [Diagnostic(
                rule="sizing.body.token-estimate",
                severity=Severity.WARNING,
                message=(
                    f"File exceeds the token budget of {max_tokens} "
                    f"(estimated {token_count} tokens). Consider trimming content."
                ),
            )]
        return []

    check_body_token_estimate.__name__ = "check_body_token_estimate"
    return check_body_token_estimate
