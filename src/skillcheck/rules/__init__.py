from __future__ import annotations

from typing import Callable

from skillcheck import config
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic
from skillcheck.rules.frontmatter import (
    check_description_max_length,
    check_description_no_xml_tags,
    check_description_non_empty,
    check_description_person_voice,
    check_description_required,
    check_name_charset,
    check_name_max_length,
    check_name_required,
    check_name_reserved_words,
    check_unknown_fields,
)
from skillcheck.rules.sizing import make_line_count_rule, make_token_estimate_rule

_FRONTMATTER_RULES: list[Callable[[ParsedSkill], list[Diagnostic]]] = [
    check_name_required,
    check_name_max_length,
    check_name_charset,
    check_name_reserved_words,
    check_description_required,
    check_description_non_empty,
    check_description_max_length,
    check_description_no_xml_tags,
    check_description_person_voice,
    check_unknown_fields,
]


def get_rules(
    max_lines: int | None = None,
    max_tokens: int | None = None,
) -> list[Callable[[ParsedSkill], list[Diagnostic]]]:
    """Build the full rule list, optionally overriding sizing thresholds."""
    sizing_rules = [
        make_line_count_rule(max_lines if max_lines is not None else config.MAX_BODY_LINES),
        make_token_estimate_rule(max_tokens if max_tokens is not None else config.MAX_TOKENS),
    ]
    return _FRONTMATTER_RULES + sizing_rules


# Default rule list using config thresholds; used by callers that do not need overrides.
ALL_RULES: list[Callable[[ParsedSkill], list[Diagnostic]]] = get_rules()
