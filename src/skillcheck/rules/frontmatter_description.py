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

_XML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
_FIRST_PERSON_RE = re.compile(
    r"(?:(?:^|(?<=\.\s))I\b)"
    r"|\bI (?:can|will|am|do|have|would|should|need|shall|won't|didn't|don't)\b"
    r"|\bMy\b",
    re.MULTILINE,
)
_SECOND_PERSON_RE = re.compile(
    r"\b[Yy]ou (?:can|will|should|must|need|are|have|do|get|use)\b",
)


def check_description_type(skill: ParsedSkill) -> list[Diagnostic]:
    """Ensure ``description`` is a string, not a YAML-coerced type."""
    desc = skill.frontmatter.get("description")
    if desc is None:
        return []
    if isinstance(desc, str):
        return []
    yaml_type = type(desc).__name__
    return [Diagnostic(
        rule="frontmatter.description.type",
        severity=Severity.ERROR,
        message=(
            f"Field 'description' must be a string but YAML parsed it as {yaml_type} "
            f"({desc!r}). Quote the value: description: \"{desc}\""
        ),
        line=_field_line(skill.raw_text, "description"),
    )]


def check_description_required(skill: ParsedSkill) -> list[Diagnostic]:
    if "description" not in skill.frontmatter:
        message = "Required field 'description' is missing from frontmatter."
        if _heading_for_field(skill.raw_text, "description"):
            message += _markdown_heading_hint("description")
        return [Diagnostic(
            rule="frontmatter.description.required",
            severity=Severity.ERROR,
            message=message,
        )]
    return []


def check_description_non_empty(skill: ParsedSkill) -> list[Diagnostic]:
    if "description" not in skill.frontmatter:
        return []
    desc = skill.frontmatter.get("description")
    if not desc or (isinstance(desc, str) and not desc.strip()):
        return [Diagnostic(
            rule="frontmatter.description.empty",
            severity=Severity.ERROR,
            message="Description is empty. Provide a meaningful description of the skill.",
            line=_field_line(skill.raw_text, "description"),
            context="description: (empty)",
        )]
    return []


def check_description_max_length(skill: ParsedSkill) -> list[Diagnostic]:
    desc = skill.frontmatter.get("description")
    if not desc:
        return []
    desc = str(desc)
    if len(desc) > config.DESCRIPTION_MAX_LENGTH:
        return [Diagnostic(
            rule="frontmatter.description.max-length",
            severity=Severity.ERROR,
            message=(
                f"Description exceeds {config.DESCRIPTION_MAX_LENGTH} characters "
                f"(got {len(desc)})."
            ),
            line=_field_line(skill.raw_text, "description"),
        )]
    return []


def check_description_no_xml_tags(skill: ParsedSkill) -> list[Diagnostic]:
    desc = skill.frontmatter.get("description")
    if not desc:
        return []
    desc = str(desc)
    tags_found = _XML_TAG_RE.findall(desc)
    if tags_found:
        return [Diagnostic(
            rule="frontmatter.description.xml-tags",
            severity=Severity.ERROR,
            message=(
                f"Description contains XML tags: {tags_found}. "
                f"Remove markup from the description."
            ),
            line=_field_line(skill.raw_text, "description"),
        )]
    return []


def check_description_person_voice(skill: ParsedSkill) -> list[Diagnostic]:
    desc = skill.frontmatter.get("description")
    if not desc:
        return []
    desc = str(desc)

    first_match = _FIRST_PERSON_RE.search(desc)
    if first_match:
        return [Diagnostic(
            rule="frontmatter.description.person-voice",
            severity=Severity.WARNING,
            message=(
                f"Description appears to use first-person voice "
                f"('{first_match.group().strip()}'); the spec recommends "
                f"third-person for routing clarity."
            ),
            line=_field_line(skill.raw_text, "description"),
            context=f"description: {desc[:80]}{'...' if len(desc) > 80 else ''}",
        )]

    second_match = _SECOND_PERSON_RE.search(desc)
    if second_match:
        return [Diagnostic(
            rule="frontmatter.description.person-voice",
            severity=Severity.WARNING,
            message=(
                f"Description appears to use second-person voice "
                f"('{second_match.group()}'); the spec recommends "
                f"third-person for routing clarity. Verify the phrasing "
                f"addresses the agent, not the user."
            ),
            line=_field_line(skill.raw_text, "description"),
            context=f"description: {desc[:80]}{'...' if len(desc) > 80 else ''}",
        )]

    return []
