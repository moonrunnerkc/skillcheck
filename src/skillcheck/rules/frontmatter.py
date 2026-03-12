from __future__ import annotations

import re

from skillcheck import config
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity

_XML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
_NAME_VALID_CHARS_RE = re.compile(r"^[a-z0-9-]+$")

# YAML anchor (&name) and alias (*name) patterns.
# Anchors define a reusable value; aliases reference it.  When safe_load
# resolves ``description: *anchor``, the description silently becomes
# whatever the anchor pointed to — a subtle semantic trap that bypasses
# all downstream description-quality checks.
_YAML_ANCHOR_RE = re.compile(r"&([A-Za-z_][A-Za-z0-9_-]*)")
_YAML_ALIAS_RE = re.compile(r"\*([A-Za-z_][A-Za-z0-9_-]*)")

# First-person patterns: "I can", "I will", "I'm", "My approach", etc.
# Catches subject "I" at sentence start, "I" before a verb, and possessive "My".
_FIRST_PERSON_RE = re.compile(
    r"(?:(?:^|(?<=\.\s))I\b)"
    r"|\bI (?:can|will|am|do|have|would|should|need|shall|won't|didn't|don't)\b"
    r"|\bMy\b",
    re.MULTILINE,
)

# Second-person patterns: "You can", "you will", "you should", etc.
_SECOND_PERSON_RE = re.compile(
    r"\b[Yy]ou (?:can|will|should|must|need|are|have|do|get|use)\b",
)


def _field_line(raw_text: str, field: str) -> int | None:
    """Return the 1-based line number where a frontmatter field appears.

    Only searches within the frontmatter block to avoid false positives from
    body content that happens to start with a field name.
    """
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    # Scan only until the closing --- delimiter.
    for i, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            break
        if line.lstrip().startswith(f"{field}:"):
            return i
    return None


def check_name_required(skill: ParsedSkill) -> list[Diagnostic]:
    if skill.frontmatter.get("name") is None:
        return [Diagnostic(
            rule="frontmatter.name.required",
            severity=Severity.ERROR,
            message="Required field 'name' is missing from frontmatter.",
        )]
    return []


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
                severity=Severity.ERROR,
                message=f"Name contains reserved word '{word}': '{name}'.",
                line=_field_line(skill.raw_text, "name"),
                context=f"name: {name}",
            )]
    return []


def check_description_required(skill: ParsedSkill) -> list[Diagnostic]:
    if "description" not in skill.frontmatter:
        return [Diagnostic(
            rule="frontmatter.description.required",
            severity=Severity.ERROR,
            message="Required field 'description' is missing from frontmatter.",
        )]
    return []


def check_description_non_empty(skill: ParsedSkill) -> list[Diagnostic]:
    if "description" not in skill.frontmatter:
        return []  # already covered by check_description_required
    desc = skill.frontmatter.get("description")
    # Treat null (description:) and whitespace-only strings as empty.
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
            severity=Severity.ERROR,
            message=(
                f"Description uses first-person voice ('{first_match.group().strip()}'). "
                f"Use third person, e.g., 'Generates...' or 'Analyzes...'"
            ),
            line=_field_line(skill.raw_text, "description"),
            context=f"description: {desc[:80]}{'...' if len(desc) > 80 else ''}",
        )]

    second_match = _SECOND_PERSON_RE.search(desc)
    if second_match:
        return [Diagnostic(
            rule="frontmatter.description.person-voice",
            severity=Severity.ERROR,
            message=(
                f"Description uses second-person voice ('{second_match.group()}'). "
                f"Use third person, e.g., 'Generates...' or 'Analyzes...'"
            ),
            line=_field_line(skill.raw_text, "description"),
            context=f"description: {desc[:80]}{'...' if len(desc) > 80 else ''}",
        )]

    return []


def check_unknown_fields(skill: ParsedSkill) -> list[Diagnostic]:
    diagnostics = []
    for field in skill.frontmatter:
        if field not in config.KNOWN_FRONTMATTER_FIELDS:
            diagnostics.append(Diagnostic(
                rule="frontmatter.field.unknown",
                severity=Severity.WARNING,
                message=(
                    f"Unknown frontmatter field '{field}'. "
                    f"Known fields: {', '.join(sorted(config.KNOWN_FRONTMATTER_FIELDS))}."
                ),
                line=_field_line(skill.raw_text, str(field)),
                context=f"{field}: ...",
            ))
    return diagnostics


def _extract_frontmatter_raw(raw_text: str) -> str:
    """Return the raw frontmatter text between ``---`` delimiters."""
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    fm_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)
    return "\n".join(fm_lines)


def check_yaml_anchors(skill: ParsedSkill) -> list[Diagnostic]:
    """Warn when YAML anchors or aliases are used in frontmatter.

    ``yaml.safe_load`` silently resolves anchors/aliases, which can cause
    a field like ``description: *name_anchor`` to inherit the name value.
    This bypasses description-quality checks and is almost always a mistake
    in SKILL.md files.
    """
    fm_raw = _extract_frontmatter_raw(skill.raw_text)
    if not fm_raw:
        return []

    diagnostics: list[Diagnostic] = []

    anchors = _YAML_ANCHOR_RE.findall(fm_raw)
    aliases = _YAML_ALIAS_RE.findall(fm_raw)

    if anchors or aliases:
        names = sorted(set(anchors + aliases))
        diagnostics.append(Diagnostic(
            rule="frontmatter.yaml-anchors",
            severity=Severity.WARNING,
            message=(
                f"YAML anchors/aliases detected in frontmatter ({', '.join(names)}). "
                f"Anchors silently copy values between fields, which can bypass "
                f"validation. Use explicit values instead."
            ),
        ))

    return diagnostics
