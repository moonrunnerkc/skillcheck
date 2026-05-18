"""Cross-agent compatibility warnings for SKILL.md.

The agentskills.io spec is consumed by Claude Code, VS Code/Copilot,
OpenAI Codex, Cursor, and other agents. Implementation-specific fields
work in one agent but are ignored or cause breakage in others.

This module flags fields with limited cross-agent support so authors
can make informed decisions about portability.

Provenance dates (``_CLAUDE_DATA_DATE``, ``_VSCODE_DATA_DATE``,
``_CURSOR_DATA_DATE``) record when the compatibility data was last
verified. The ``test_compat_data_freshness`` test asserts that these
dates are within 365 days of today; when the test fails, update the
constants and re-verify the agent behavior they encode.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from skillcheck import config
from skillcheck.parser import _FRONTMATTER_RE
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity
from skillcheck.template_detection import is_template

# ---------------------------------------------------------------------------
# Provenance dates for compatibility data
# ---------------------------------------------------------------------------

_CLAUDE_DATA_DATE = "2026-04-20"
_VSCODE_DATA_DATE = "2026-04-20"
_CURSOR_DATA_DATE = "2026-04-20"

# Detects a block scalar marker (>, >+, |, |+) on the description field.
# >- and |- strip trailing whitespace and render correctly in Cursor's UI,
# so they are deliberately excluded from the unsafe-marker group.
_CURSOR_UNSAFE_DESC_BLOCK_SCALAR = re.compile(
    r"^description\s*:\s*(?P<marker>[>|]\+?)\s*(?:#.*)?$",
    re.MULTILINE,
)


def check_claude_only_fields(skill: ParsedSkill) -> list[Diagnostic]:
    """Flag fields that only work in Claude Code."""
    diagnostics: list[Diagnostic] = []
    for field in skill.frontmatter:
        if field in config.CLAUDE_ONLY_FIELDS:
            diagnostics.append(Diagnostic(
                rule="compat.claude-only",
                severity=Severity.INFO,
                message=(
                    f"Field '{field}' is Claude Code-specific "
                    f"(as of {_CLAUDE_DATA_DATE}). "
                    f"It will be ignored by VS Code/Copilot and behavior in "
                    f"Codex and Cursor is unverified."
                ),
            ))
    return diagnostics


def _dirname_mismatch(skill: ParsedSkill) -> tuple[str, str] | None:
    """Return ``(name, parent_dir)`` if they differ, else *None*."""
    name = skill.frontmatter.get("name")
    if name is None:
        return None
    name = str(name)
    if not name:
        return None
    parent_dir = skill.path.parent.name
    if parent_dir and parent_dir != name:
        return name, parent_dir
    return None


def check_vscode_dirname(skill: ParsedSkill) -> list[Diagnostic]:
    """Info-level note when name does not match the parent directory.

    This complements the ERROR-level check in frontmatter.py (which can be
    skipped via --skip-dirname-check). This compat rule always runs as INFO
    unless --strict-vscode promotes it.
    """
    # Skip on templates: placeholder files are not meant to deploy.
    if is_template(skill):
        return []
    pair = _dirname_mismatch(skill)
    if pair is None:
        return []
    name, parent_dir = pair
    return [Diagnostic(
        rule="compat.vscode-dirname",
        severity=Severity.INFO,
        message=(
            f"VS Code requires the name field ('{name}') to match the "
            f"parent directory ('{parent_dir}'). This skill would not "
            f"load in VS Code/Copilot (as of {_VSCODE_DATA_DATE})."
        ),
    )]


def check_unverified_fields(skill: ParsedSkill) -> list[Diagnostic]:
    """Note fields whose behavior in Codex and Cursor is unverified."""
    diagnostics: list[Diagnostic] = []
    for field in skill.frontmatter:
        compat = config.COMPAT_MATRIX.get(field)
        if compat is None:
            continue
        unknown_agents = [
            agent for agent, status in compat.items()
            if status == "unknown"
        ]
        if unknown_agents:
            agents_str = ", ".join(sorted(unknown_agents))
            # Provenance: attach dates for agents with "unknown" status
            date_parts = []
            if "Codex" in agents_str:
                date_parts.append(f"Codex: {_CLAUDE_DATA_DATE}")
            if "Cursor" in agents_str:
                date_parts.append(f"Cursor: {_CURSOR_DATA_DATE}")
            date_suffix = ""
            if date_parts:
                date_suffix = f" (as of {'; '.join(date_parts)})"
            diagnostics.append(Diagnostic(
                rule="compat.unverified",
                severity=Severity.INFO,
                message=(
                    f"Behavior of field '{field}' in {agents_str} is unverified{date_suffix}."
                ),
            ))
    return diagnostics


def make_strict_vscode_rule() -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Return a rule that promotes VS Code compat issues to ERROR severity."""

    def check_strict_vscode(skill: ParsedSkill) -> list[Diagnostic]:
        # Skip on templates: placeholder files are not meant to deploy.
        if is_template(skill):
            return []
        pair = _dirname_mismatch(skill)
        if pair is None:
            return []
        name, parent_dir = pair
        return [Diagnostic(
            rule="compat.vscode-dirname",
            severity=Severity.ERROR,
            message=(
                f"VS Code requires the name field ('{name}') to match the "
                f"parent directory ('{parent_dir}'). This skill will not "
                f"load in VS Code/Copilot (as of {_VSCODE_DATA_DATE})."
            ),
        )]

    check_strict_vscode.__name__ = "check_strict_vscode"
    return check_strict_vscode


def _detect_cursor_unsafe_block_scalar(skill: ParsedSkill) -> str | None:
    """Return the offending block-scalar marker on description, else None.

    PyYAML's safe_load discards the scalar style indicator, so we re-scan the
    raw frontmatter block. The simpler regex path avoids switching the parser
    to yaml.compose() and reaches into node attributes from every rule.
    """
    match = _FRONTMATTER_RE.match(skill.raw_text)
    if match is None:
        return None
    block = match.group(1)
    marker_match = _CURSOR_UNSAFE_DESC_BLOCK_SCALAR.search(block)
    if marker_match is None:
        return None
    return marker_match.group("marker")


def _cursor_block_scalar_message(marker: str) -> str:
    """Return the diagnostic message for an unsafe Cursor block scalar."""
    return (
        f"description uses block scalar '{marker}' which Cursor's skills "
        f"UI renders as empty (got 'description: {marker}'). Use "
        f"'description: >-' (folded strip) instead "
        f"(as of {_CURSOR_DATA_DATE})."
    )


def check_cursor_description_block_scalar(skill: ParsedSkill) -> list[Diagnostic]:
    """Flag Cursor-unsafe block scalars on the description field at INFO."""
    marker = _detect_cursor_unsafe_block_scalar(skill)
    if marker is None:
        return []
    return [Diagnostic(
        rule="compat.cursor-description-block-scalar",
        severity=Severity.INFO,
        message=_cursor_block_scalar_message(marker),
    )]


def check_cursor_description_block_scalar_warning(skill: ParsedSkill) -> list[Diagnostic]:
    """WARNING-severity variant for --target-agent cursor."""
    marker = _detect_cursor_unsafe_block_scalar(skill)
    if marker is None:
        return []
    return [Diagnostic(
        rule="compat.cursor-description-block-scalar",
        severity=Severity.WARNING,
        message=_cursor_block_scalar_message(marker),
    )]


def make_strict_cursor_rule() -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Return a rule that promotes Cursor block-scalar issues to ERROR."""

    def check_strict_cursor(skill: ParsedSkill) -> list[Diagnostic]:
        marker = _detect_cursor_unsafe_block_scalar(skill)
        if marker is None:
            return []
        return [Diagnostic(
            rule="compat.cursor-description-block-scalar",
            severity=Severity.ERROR,
            message=_cursor_block_scalar_message(marker),
        )]

    check_strict_cursor.__name__ = "check_strict_cursor"
    return check_strict_cursor
