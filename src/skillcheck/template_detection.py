"""Detect placeholder/template SKILL.md files to skip deployment-blocking checks."""

from __future__ import annotations

import re

from .parser import ParsedSkill

_PLACEHOLDER_PATTERNS = [
    re.compile(r"\b[Rr]eplace with\b"),
    re.compile(r"\b(TODO|FIXME)\b"),
    re.compile(r"\byour (skill|description|name|tool)\b", re.IGNORECASE),
    re.compile(r"<[a-z][a-z0-9_-]*>"),
    re.compile(r"\[(description|name|skill name|placeholder|TODO|...)\]", re.IGNORECASE),
    re.compile(r"\{[a-z][a-z0-9_]*\}"),
    re.compile(r"\b(lorem ipsum|placeholder|sample description)\b", re.IGNORECASE),
]


def is_template(skill: ParsedSkill) -> bool:
    """Return True if the skill appears to be a template/placeholder file.

    Recall-favoring: prefer false positives on placeholder-heavy real skills
    over missing real templates. Three signals, any one is sufficient:

    1. Explicit `template: true` in frontmatter.
    2. Description matches a placeholder pattern.
    3. Filename lives in a directory literally named `template` or `templates`.
    """
    if skill.frontmatter.get("template") is True:
        return True

    description = str(skill.frontmatter.get("description", ""))
    for pattern in _PLACEHOLDER_PATTERNS:
        if pattern.search(description):
            return True

    parent = skill.path.parent.name.lower()
    if parent in {"template", "templates"}:
        return True

    return False
