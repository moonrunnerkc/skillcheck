from __future__ import annotations

from typing import Callable

from skillcheck import config
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic
from skillcheck.rules.compat import (
    check_claude_only_fields,
    check_unverified_fields,
    check_vscode_dirname,
    make_strict_vscode_rule,
)
from skillcheck.rules.description import (
    check_description_quality,
    make_min_score_rule,
)
from skillcheck.rules.disclosure import (
    check_body_bloat,
    check_body_budget,
    check_metadata_budget,
)
from skillcheck.rules.frontmatter import (
    check_description_max_length,
    check_description_no_xml_tags,
    check_description_non_empty,
    check_description_person_voice,
    check_description_required,
    check_name_charset,
    check_name_consecutive_hyphens,
    check_name_directory_match,
    check_name_leading_trailing_hyphen,
    check_name_max_length,
    check_name_required,
    check_name_reserved_words,
    check_unknown_fields,
    check_yaml_anchors,
)
from skillcheck.rules.references import (
    check_broken_references,
    check_reference_depth,
)
from skillcheck.rules.sizing import make_line_count_rule, make_token_estimate_rule

_FRONTMATTER_RULES: list[Callable[[ParsedSkill], list[Diagnostic]]] = [
    check_name_required,
    check_name_max_length,
    check_name_charset,
    check_name_leading_trailing_hyphen,
    check_name_consecutive_hyphens,
    check_name_reserved_words,
    check_description_required,
    check_description_non_empty,
    check_description_max_length,
    check_description_no_xml_tags,
    check_description_person_voice,
    check_unknown_fields,
    check_yaml_anchors,
]

_DESCRIPTION_RULES: list[Callable[[ParsedSkill], list[Diagnostic]]] = [
    check_description_quality,
]

_REFERENCE_RULES: list[Callable[[ParsedSkill], list[Diagnostic]]] = [
    check_broken_references,
    check_reference_depth,
]

_DISCLOSURE_RULES: list[Callable[[ParsedSkill], list[Diagnostic]]] = [
    check_metadata_budget,
    check_body_budget,
    check_body_bloat,
]

_COMPAT_RULES: list[Callable[[ParsedSkill], list[Diagnostic]]] = [
    check_claude_only_fields,
    check_vscode_dirname,
    check_unverified_fields,
]


def get_rules(
    max_lines: int | None = None,
    max_tokens: int | None = None,
    skip_dirname_check: bool = False,
    skip_ref_check: bool = False,
    min_desc_score: int | None = None,
    strict_vscode: bool = False,
    target_agent: str = "all",
) -> list[Callable[[ParsedSkill], list[Diagnostic]]]:
    """Build the full rule list, optionally overriding thresholds and toggling features."""

    rules: list[Callable[[ParsedSkill], list[Diagnostic]]] = list(_FRONTMATTER_RULES)

    # Directory-name matching (Feature 1)
    if not skip_dirname_check:
        rules.append(check_name_directory_match)

    # Sizing rules
    sizing_rules = [
        make_line_count_rule(max_lines if max_lines is not None else config.MAX_BODY_LINES),
        make_token_estimate_rule(max_tokens if max_tokens is not None else config.MAX_TOKENS),
    ]
    rules.extend(sizing_rules)

    # Description quality scoring (Feature 2)
    rules.extend(_DESCRIPTION_RULES)
    if min_desc_score is not None and min_desc_score > 0:
        rules.append(make_min_score_rule(min_desc_score))

    # File reference validation (Feature 3)
    if not skip_ref_check:
        rules.extend(_REFERENCE_RULES)

    # Progressive disclosure budget (Feature 4)
    rules.extend(_DISCLOSURE_RULES)

    # Cross-agent compatibility (Feature 5)
    _VALID_AGENTS = {"all", "claude", "vscode"}
    if target_agent not in _VALID_AGENTS:
        raise ValueError(
            f"Unknown target_agent '{target_agent}'. "
            f"Must be one of: {', '.join(sorted(_VALID_AGENTS))}"
        )

    if target_agent == "all":
        compat_rules = list(_COMPAT_RULES)
        if strict_vscode:
            # Replace the INFO-level dirname check with an ERROR-level one
            # so the same mismatch is not reported twice.
            compat_rules = [r for r in compat_rules if r is not check_vscode_dirname]
            compat_rules.append(make_strict_vscode_rule())
        rules.extend(compat_rules)
    elif target_agent == "vscode":
        if strict_vscode:
            rules.append(make_strict_vscode_rule())
        else:
            rules.append(check_vscode_dirname)
    elif target_agent == "claude":
        rules.append(check_claude_only_fields)

    return rules
