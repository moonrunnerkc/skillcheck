from __future__ import annotations

import re

from skillcheck import config
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity
from skillcheck.rules.frontmatter_common import (
    _field_line,
    _heading_for_field,
    _markdown_heading_hint,
)
from skillcheck.template_detection import is_template

_NAME_VALID_CHARS_RE = re.compile(r"^[a-z0-9-]+$")


def check_name_required(skill: ParsedSkill) -> list[Diagnostic]:
    if skill.frontmatter.get("name") is None:
        message = "Required field 'name' is missing from frontmatter."
        if _heading_for_field(skill.raw_text, "name"):
            message += _markdown_heading_hint("name")
        return [Diagnostic(
            rule="frontmatter.name.required",
            severity=Severity.ERROR,
            message=message,
        )]
    return []


def check_name_type(skill: ParsedSkill) -> list[Diagnostic]:
    """Ensure ``name`` is a string, not a YAML-coerced boolean/number/null."""
    name = skill.frontmatter.get("name")
    if name is None:
        return []
    if isinstance(name, str):
        return []
    yaml_type = type(name).__name__
    return [Diagnostic(
        rule="frontmatter.name.type",
        severity=Severity.ERROR,
        message=(
            f"Field 'name' must be a string but YAML parsed it as {yaml_type} "
            f"({name!r}). Quote the value: name: \"{name}\""
        ),
        line=_field_line(skill.raw_text, "name"),
    )]


def check_name_max_length(skill: ParsedSkill) -> list[Diagnostic]:
    name = skill.frontmatter.get("name")
    if name is None:
        return []
    name = str(name)
    if len(name) > config.NAME_MAX_LENGTH:
        return [Diagnostic(
            rule="frontmatter.name.max-length",
            severity=Severity.ERROR,
            message=(
                f"Name exceeds {config.NAME_MAX_LENGTH} characters "
                f"(got {len(name)}): '{name}'"
            ),
            line=_field_line(skill.raw_text, "name"),
            context=f"name: {name}",
        )]
    return []


def check_name_charset(skill: ParsedSkill) -> list[Diagnostic]:
    name = skill.frontmatter.get("name")
    if name is None:
        return []
    name = str(name)
    if not name:
        return [Diagnostic(
            rule="frontmatter.name.invalid-chars",
            severity=Severity.ERROR,
            message="Name is empty. Use lowercase letters, numbers, and hyphens only.",
            line=_field_line(skill.raw_text, "name"),
        )]
    if not _NAME_VALID_CHARS_RE.match(name):
        invalid = sorted(set(c for c in name if not re.match(r"[a-z0-9-]", c)))
        return [Diagnostic(
            rule="frontmatter.name.invalid-chars",
            severity=Severity.ERROR,
            message=(
                f"Name contains invalid characters {invalid}: '{name}'. "
                f"Use lowercase letters, numbers, and hyphens only."
            ),
            line=_field_line(skill.raw_text, "name"),
            context=f"name: {name}",
        )]
    return []


def check_name_leading_trailing_hyphen(skill: ParsedSkill) -> list[Diagnostic]:
    name = skill.frontmatter.get("name")
    if name is None:
        return []
    name = str(name)
    if not name:
        return []
    issues = []
    if name.startswith("-"):
        issues.append("starts with a hyphen")
    if name.endswith("-"):
        issues.append("ends with a hyphen")
    if issues:
        return [Diagnostic(
            rule="frontmatter.name.leading-trailing-hyphen",
            severity=Severity.ERROR,
            message=(
                f"Name {' and '.join(issues)}: '{name}'. "
                f"Hyphens are only allowed between characters."
            ),
            line=_field_line(skill.raw_text, "name"),
            context=f"name: {name}",
        )]
    return []


def check_name_consecutive_hyphens(skill: ParsedSkill) -> list[Diagnostic]:
    name = skill.frontmatter.get("name")
    if name is None:
        return []
    name = str(name)
    if "--" in name:
        return [Diagnostic(
            rule="frontmatter.name.consecutive-hyphens",
            severity=Severity.ERROR,
            message=(
                f"Name contains consecutive hyphens: '{name}'. "
                f"Use a single hyphen between words."
            ),
            line=_field_line(skill.raw_text, "name"),
            context=f"name: {name}",
        )]
    return []


def check_name_directory_match(skill: ParsedSkill) -> list[Diagnostic]:
    # Skip on templates: placeholder files are not meant to deploy.
    if is_template(skill):
        return []
    name = skill.frontmatter.get("name")
    if name is None:
        return []
    name = str(name)
    if not name:
        return []
    parent_dir = skill.path.parent.name
    if parent_dir and parent_dir != name:
        return [Diagnostic(
            rule="frontmatter.name.directory-mismatch",
            severity=Severity.ERROR,
            message=(
                f"Name '{name}' does not match parent directory '{parent_dir}'. "
                f"VS Code requires these to match or the skill will not load."
            ),
            line=_field_line(skill.raw_text, "name"),
            context=f"name: {name} | directory: {parent_dir}",
        )]
    return []


def check_name_reserved_words(skill: ParsedSkill) -> list[Diagnostic]:
    name = skill.frontmatter.get("name")
    if name is None:
        return []
    name = str(name)
    for word in ("anthropic", "claude"):
        if word in name:
            return [Diagnostic(
                rule="frontmatter.name.reserved-word",
                severity=Severity.WARNING,
                message=(
                    f"Name contains the term '{word}' which may collide with "
                    f"platform-reserved namespaces. Verify with the target "
                    f"agent's documentation."
                ),
                line=_field_line(skill.raw_text, "name"),
                context=f"name: {name}",
                source="advisory",
                confidence="low",
            )]
    return []
